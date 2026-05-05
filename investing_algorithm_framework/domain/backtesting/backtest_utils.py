import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed, \
    wait, FIRST_COMPLETED
from logging import getLogger
from pathlib import Path
from random import Random
from typing import List, Union, Callable, Optional

from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.utils.custom_tqdm import tqdm

from .backtest import Backtest
from .bundle import (
    BUNDLE_EXT,
    is_bundle_file,
    open_bundle as _open_bundle,
    save_bundle as _save_bundle,
)

logger = getLogger("investing_algorithm_framework")


# ``format`` literal for save/load functions.
FORMAT_BUNDLE = "bundle"
FORMAT_DIRECTORY = "directory"
_VALID_FORMATS = {FORMAT_BUNDLE, FORMAT_DIRECTORY}


def _resolve_workers(workers: Optional[int]) -> int:
    if workers is None:
        return min(8, (os.cpu_count() or 1))
    return max(1, int(workers))


def resolve_backtest_path(
    storage_directory: Union[str, Path], algorithm_id: str
) -> Optional[str]:
    """Return the on-disk path for a stored backtest, or ``None``.

    Prefers ``<storage>/<algorithm_id>.iafbt`` (issue #487 bundle
    format) and falls back to the legacy directory at
    ``<storage>/<algorithm_id>``.
    """
    bundle = os.path.join(
        str(storage_directory), f"{algorithm_id}{BUNDLE_EXT}"
    )
    if os.path.isfile(bundle):
        return bundle
    legacy = os.path.join(str(storage_directory), algorithm_id)
    if os.path.isdir(legacy):
        return legacy
    return None


# --- worker entry points (must be top-level so they pickle) -------------


def _save_one_bundle(args):
    backtest, target, include_ohlcv, ohlcv_store = args
    return str(_save_bundle(
        backtest, target,
        include_ohlcv=include_ohlcv,
        ohlcv_store=ohlcv_store,
    ))


def _load_one_bundle(path: str):
    return _open_bundle(path)


def _load_one_directory(path: str):
    return Backtest.open(path)


def _load_one_dispatch(item):
    path, kind = item
    if kind == "bundle":
        return _load_one_bundle(path)
    return _load_one_directory(path)


def save_backtests_to_directory(
    backtests: List[Backtest],
    directory_path: Union[str, Path],
    backtest_date_range=None,
    dir_name_generation_function: Callable[[Backtest], str] = None,
    number_of_backtests_to_save: int = None,
    filter_function: Callable[[Backtest], bool] = None,
    show_progress: bool = False,
    format: str = FORMAT_BUNDLE,
    workers: Optional[int] = None,
    include_ohlcv: bool = False,
    write_index: bool = True,
) -> None:
    """
    Saves a list of Backtest objects to the specified directory.

    Args:
        backtests (List[Backtest]): List of Backtest objects to save.
        directory_path (str): Path to the directory where backtests
            will be saved.
        backtest_date_range (BacktestDateRange, optional): Date range
            to filter backtests before saving. If provided, only backtest runs
            with this date range will be saved. Defaults to None.
        dir_name_generation_function (Callable[[Backtest], str], optional):
            A function that takes a Backtest object as input and returns
            a string to be used as the **bundle base name** (or directory
            name in legacy ``directory`` format). If not provided, the
            backtest's ``algorithm_id`` is used.
        number_of_backtests_to_save (int, optional): Maximum number of
            backtests to save. If None, all backtests will be saved.
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be saved. Defaults to None.
        show_progress (bool, optional): Whether to display a progress bar
            while saving backtests. Defaults to False.
        format: Persistence layout. ``"bundle"`` (default, issue #487)
            writes one ``.iafbt`` file per backtest. ``"directory"``
            keeps the legacy human-readable per-file JSON layout.
        workers: Process pool size for parallel saves. Only used in
            ``bundle`` mode. Defaults to ``min(8, os.cpu_count())``.
            Pass ``1`` to disable parallelism.
        include_ohlcv: Forward to :py:func:`save_bundle`. Only used in
            ``bundle`` mode.
        write_index: When True (the default) and ``format='bundle'``,
            write a top-level ``index.parquet`` containing one row per
            saved backtest with its summary metrics, parameters and the
            relative bundle path. Loaders can use this to filter
            without opening any bundle.

    Returns:
        None
    """
    if format not in _VALID_FORMATS:
        raise OperationalException(
            f"Unknown format '{format}'. Expected one of {_VALID_FORMATS}."
        )

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    # Filter + cap up front so progress / parallel scheduling sees the
    # real workload.
    selected: List[tuple] = []
    for backtest in backtests:
        if number_of_backtests_to_save is not None and \
                len(selected) >= number_of_backtests_to_save:
            break
        if filter_function is not None and not filter_function(backtest):
            continue

        if dir_name_generation_function is not None:
            base_name = dir_name_generation_function(backtest)
        else:
            base_name = getattr(backtest, "algorithm_id", None)
        if base_name is None:
            logger.warning(
                "Backtest algorithm_id is None. "
                "Generating a random name."
            )
            base_name = str(Random().randint(100000, 999999))
        selected.append((backtest, base_name))

    iterator = selected
    if show_progress:
        iterator = tqdm(selected, desc="Saving backtests")

    saved_paths: List[str] = []

    if format == FORMAT_DIRECTORY:
        # Legacy serial path — directory format keeps full backwards
        # compatibility (parallelising it adds little value because the
        # bottleneck is the per-file syscalls, not CPU).
        for backtest, base_name in iterator:
            path = os.path.join(directory_path, base_name)
            backtest.save(
                path,
                backtest_date_ranges=[backtest_date_range]
                if backtest_date_range else None,
            )
            saved_paths.append(path)
    else:
        # Bundle format — fan out across a process pool.
        ohlcv_store = (
            os.path.join(str(directory_path), "ohlcv")
            if include_ohlcv else None
        )
        n_workers = _resolve_workers(workers)

        if n_workers <= 1 or len(selected) <= 1:
            for backtest, base_name in iterator:
                target = os.path.join(
                    str(directory_path), f"{base_name}{BUNDLE_EXT}"
                )
                p = _save_bundle(
                    backtest, target,
                    include_ohlcv=include_ohlcv,
                    ohlcv_store=ohlcv_store,
                )
                saved_paths.append(str(p))
        else:
            tasks = [
                (
                    bt,
                    os.path.join(
                        str(directory_path), f"{name}{BUNDLE_EXT}"
                    ),
                    include_ohlcv,
                    ohlcv_store,
                )
                for bt, name in selected
            ]
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                futures = [ex.submit(_save_one_bundle, t) for t in tasks]
                pbar = (
                    tqdm(
                        total=len(futures),
                        desc="Saving backtests",
                    )
                    if show_progress
                    else None
                )
                for fut in as_completed(futures):
                    saved_paths.append(fut.result())
                    if pbar is not None:
                        pbar.update(1)
                if pbar is not None:
                    pbar.close()

        if write_index and selected:
            try:
                _write_index(directory_path, [bt for bt, _ in selected])
            except Exception as e:  # pragma: no cover - non-fatal
                logger.warning(f"Failed to write index.parquet: {e}")


def retag_backtests(
    tag: str,
    directory_path: Optional[Union[str, Path]] = None,
    strategy_id: Optional[str] = None,
) -> int:
    """
    Retag backtests with a new tag value.

    Supports two modes:
    - **By directory**: provide ``directory_path`` to retag every
      backtest found in that directory (or a single backtest if the
      path itself is a backtest directory).
    - **By strategy_id**: provide both ``directory_path`` *and*
      ``strategy_id`` to retag only the backtest whose
      ``algorithm_id`` matches.

    The tag is written to ``tag.json`` inside each matching backtest
    directory so it persists across subsequent loads.

    Args:
        tag: The new tag string to assign.
        directory_path: Path to a directory containing backtests, or
            the path to a single backtest directory.
        strategy_id: When given together with ``directory_path``,
            only the backtest with this ``algorithm_id`` is retagged.

    Returns:
        int: The number of backtests that were retagged.

    Raises:
        OperationalException: If neither ``directory_path`` nor
            ``strategy_id`` is provided, or if the directory does
            not exist.
    """
    if directory_path is None:
        raise OperationalException(
            "directory_path is required for retag_backtests."
        )

    directory_path = str(directory_path)

    if not os.path.isdir(directory_path):
        raise OperationalException(
            f"Directory {directory_path} does not exist."
        )

    count = 0

    # Check if directory_path itself is a single backtest
    if _is_backtest_dir(directory_path):
        if _retag_single(directory_path, tag, strategy_id):
            count += 1
        return count

    # Walk sub-directories looking for backtest dirs
    for name in os.listdir(directory_path):
        sub = os.path.join(directory_path, name)
        if os.path.isdir(sub) and _is_backtest_dir(sub):
            if _retag_single(sub, tag, strategy_id):
                count += 1

    return count


def _is_backtest_dir(path: str) -> bool:
    """Return True if *path* looks like a saved backtest."""
    return (
        os.path.isfile(os.path.join(path, "algorithm_id.json"))
        and os.path.isdir(os.path.join(path, "runs"))
    )


def _retag_single(
    backtest_dir: str, tag: str, strategy_id: Optional[str]
) -> bool:
    """Write ``tag.json`` into *backtest_dir*.

    If *strategy_id* is given, only write when the backtest's
    algorithm_id matches.  Returns True when a write happened.
    """
    if strategy_id is not None:
        id_file = os.path.join(backtest_dir, "algorithm_id.json")
        if not os.path.isfile(id_file):
            return False
        try:
            with open(id_file, 'r') as f:
                aid = json.load(f).get('algorithm_id')
        except (json.JSONDecodeError, OSError):
            return False
        if aid != strategy_id:
            return False

    tag_file = os.path.join(backtest_dir, "tag.json")
    with open(tag_file, 'w') as f:
        json.dump({'tag': tag}, f, indent=4)
    return True


def load_backtests_from_directory(
    directory_path: Union[str, Path],
    filter_function: Callable[[Backtest], bool] = None,
    number_of_backtests_to_load: int = None,
    show_progress: bool = False,
    workers: Optional[int] = None,
) -> List[Backtest]:
    """
    Loads Backtest objects from the specified directory.

    Auto-detects each entry: ``.iafbt`` bundle files (issue #487) and
    legacy backtest directories are both supported and may coexist in
    the same parent directory.

    Args:
        directory_path (str): Path to the directory from which backtests
            will be loaded.
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be included in the result. Defaults to None.
        number_of_backtests_to_load (int, optional): Maximum number of
            backtests to load. If None, all backtests will be loaded.
        show_progress (bool, optional): Whether to display a progress bar
            while loading backtests. Defaults to False.
        workers: Process pool size for parallel loads. Defaults to
            ``min(8, os.cpu_count())``. Pass ``1`` to disable.

    Returns:
        List[Backtest]: List of loaded Backtest objects.
    """
    backtests: List[Backtest] = []

    if not os.path.exists(directory_path):
        logger.warning(
            f"Directory {directory_path} does not exist. "
            "No backtests loaded."
        )
        return backtests

    # Build the load list: a list of (path, kind) tuples.
    sources: List[tuple] = []
    for entry in sorted(os.listdir(directory_path)):
        if entry == "checkpoints.json" or entry.endswith(".py"):
            continue
        if entry == "index.parquet" or entry == "ohlcv":
            continue
        full = os.path.join(directory_path, entry)
        if os.path.isfile(full):
            if entry.endswith(BUNDLE_EXT) or is_bundle_file(full):
                sources.append((full, "bundle"))
        elif os.path.isdir(full):
            sources.append((full, "directory"))

    if number_of_backtests_to_load is not None:
        sources = sources[: max(0, int(number_of_backtests_to_load))]

    n_workers = _resolve_workers(workers)

    pbar = None
    if show_progress:
        pbar = tqdm(total=len(sources), desc="Loading backtests")

    if n_workers <= 1 or len(sources) <= 1:
        for item in sources:
            try:
                backtests.append(_load_one_dispatch(item))
            except Exception as e:
                logger.error(
                    f"Failed to load backtest from {item[0]}: {e}"
                )
            finally:
                if pbar is not None:
                    pbar.update(1)
    else:
        # Process pool only handles bundle loads efficiently; loading
        # legacy directories from workers also works but the win is
        # smaller. We still parallelise both for simplicity.
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futures = {
                ex.submit(_load_one_dispatch, it): it for it in sources
            }
            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    backtests.append(fut.result())
                except Exception as e:
                    logger.error(
                        f"Failed to load backtest from {src[0]}: {e}"
                    )
                finally:
                    if pbar is not None:
                        pbar.update(1)

    if pbar is not None:
        pbar.close()

    if filter_function is not None:
        try:
            backtests = [bt for bt in backtests if filter_function(bt)]
        except Exception as fe:  # pragma: no cover - defensive
            logger.error(f"Error in filter_function: {fe}")

    return backtests


# ---------------------------------------------------------------------------
# Index helpers (#487 step 4)
# ---------------------------------------------------------------------------


def _backtest_to_index_row(bt: Backtest, bundle_path: Optional[str] = None):
    """Flatten a backtest's summary + identity into a single row."""
    summary = (
        bt.backtest_summary.to_dict() if bt.backtest_summary else {}
    )
    row = {
        "algorithm_id": getattr(bt, "algorithm_id", None),
        "tag": getattr(bt, "tag", None),
        "risk_free_rate": getattr(bt, "risk_free_rate", None),
        "bundle_path": bundle_path,
        "number_of_runs": len(bt.backtest_runs or []),
    }
    # Include scalar summary metrics only (no nested structures).
    for k, v in summary.items():
        if isinstance(v, (int, float, str, bool)) or v is None:
            row[f"summary.{k}"] = v
    # Parameters as JSON for round-trippability without exploding columns.
    if getattr(bt, "parameters", None):
        try:
            row["parameters"] = json.dumps(bt.parameters, default=str)
        except (TypeError, ValueError):
            row["parameters"] = None
    return row


def _write_index(directory_path: Union[str, Path], backtests: List[Backtest]):
    """Write ``<directory_path>/index.parquet`` with one row per backtest.

    Uses pandas + pyarrow. Failures are non-fatal — the caller logs them.
    """
    import pandas as pd  # local import keeps top of module light

    rows = []
    for bt in backtests:
        base = getattr(bt, "algorithm_id", None) or "backtest"
        rel = f"{base}{BUNDLE_EXT}"
        rows.append(_backtest_to_index_row(bt, bundle_path=rel))

    df = pd.DataFrame(rows)
    target = Path(directory_path) / "index.parquet"
    df.to_parquet(target, index=False, compression="zstd")


class BacktestIndex:
    """Lightweight reader for the ``index.parquet`` produced by
    :py:func:`save_backtests_to_directory` (issue #487).

    Lets analysis code filter on summary metrics / parameters
    *without opening any bundle*. Bundles for surviving rows can then
    be loaded explicitly via :py:meth:`load_backtests`.
    """

    def __init__(self, directory: Union[str, Path], dataframe):
        self.directory = Path(directory)
        self.df = dataframe

    @classmethod
    def open(cls, directory: Union[str, Path]) -> "BacktestIndex":
        import pandas as pd

        path = Path(directory) / "index.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"No index.parquet at {directory}; pass write_index=True "
                "to save_backtests_to_directory to generate one."
            )
        return cls(directory, pd.read_parquet(path))

    def __len__(self) -> int:
        return len(self.df)

    def filter(self, predicate: Callable) -> "BacktestIndex":
        """Return a new index restricted to rows where *predicate(row)*
        is True.  ``predicate`` receives a pandas Series.
        """
        mask = self.df.apply(predicate, axis=1).astype(bool)
        return BacktestIndex(self.directory, self.df.loc[mask].copy())

    def load_backtests(
        self,
        workers: Optional[int] = None,
        show_progress: bool = False,
    ) -> List[Backtest]:
        """Load all backtest bundles referenced by the current rows."""
        n_workers = _resolve_workers(workers)
        paths = [
            str(self.directory / p) for p in self.df["bundle_path"].tolist()
            if isinstance(p, str)
        ]
        out: List[Backtest] = []
        pbar = (
            tqdm(total=len(paths), desc="Loading backtests")
            if show_progress else None
        )
        if n_workers <= 1 or len(paths) <= 1:
            for p in paths:
                try:
                    out.append(_load_one_bundle(p))
                except Exception as e:
                    logger.error(f"Failed to load {p}: {e}")
                finally:
                    if pbar is not None:
                        pbar.update(1)
        else:
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                futs = {ex.submit(_load_one_bundle, p): p for p in paths}
                for fut in as_completed(futs):
                    try:
                        out.append(fut.result())
                    except Exception as e:
                        logger.error(f"Failed to load {futs[fut]}: {e}")
                    finally:
                        if pbar is not None:
                            pbar.update(1)
        if pbar is not None:
            pbar.close()
        return out


# ---------------------------------------------------------------------------
# Migration helper (#487 step 5)
# ---------------------------------------------------------------------------


def _migrate_one(args):
    """Worker entry point: open *src* (legacy dir or bundle), write
    *dst* as a bundle, optionally delete *src*, return the
    destination path together with a flat index row.

    Doing load+save (and optionally delete) in one worker call keeps
    each backtest's data in a single process — avoiding the cost of
    pickling fully-decoded Backtest objects back to the parent
    process. We also build the index row here, while the backtest is
    still in memory, so the parent never has to re-open the migrated
    bundles just to build ``index.parquet``.
    """
    src, dst, include_ohlcv, ohlcv_store, delete_source = args
    bt = _open_bundle(src) if is_bundle_file(src) else Backtest.open(src)
    out = str(_save_bundle(
        bt, dst,
        include_ohlcv=include_ohlcv,
        ohlcv_store=ohlcv_store,
    ))
    rel = os.path.basename(out)
    row = _backtest_to_index_row(bt, bundle_path=rel)
    # Drop the heavy backtest before returning so the worker process's
    # RSS can be reclaimed before it picks up the next task.
    del bt
    if delete_source and os.path.abspath(src) != os.path.abspath(out):
        import shutil
        if os.path.isdir(src):
            shutil.rmtree(src, ignore_errors=True)
        elif os.path.isfile(src):
            try:
                os.remove(src)
            except OSError:
                pass
    return out, row


def migrate_backtests(
    src_dir: Union[str, Path],
    dst_dir: Union[str, Path],
    *,
    workers: Optional[int] = None,
    show_progress: bool = False,
    write_index: bool = True,
    include_ohlcv: bool = False,
    skip_existing: bool = True,
    delete_source: bool = False,
) -> int:
    """Rewrite a directory of legacy backtest folders (or existing
    ``.iafbt`` bundles) as ``.iafbt`` bundles in *dst_dir*.

    The migration is streamed: each backtest is loaded and re-saved
    inside a single worker process, so memory usage stays roughly
    constant regardless of how many backtests are being migrated.

    Args:
        src_dir: Source directory containing legacy backtest folders
            and/or ``.iafbt`` bundles. Walked recursively.
        dst_dir: Destination directory. Created if it does not exist.
        workers: Number of parallel workers. ``None`` picks
            ``min(8, cpu_count)``. Pass ``1`` to force serial.
        show_progress: Display a progress bar.
        write_index: Write a sibling ``index.parquet`` summarising the
            destination bundles for fast filtering with
            :class:`BacktestIndex`.
        include_ohlcv: Include OHLCV data in the destination bundles.
        skip_existing: Skip backtests whose destination bundle already
            exists. Allows resuming an interrupted migration.
        delete_source: If True, delete each source directory / bundle
            **after** its destination bundle has been written
            successfully. The source is left intact when it is the
            same path as the destination. Use with care.

    Returns:
        Number of backtests migrated (excluding skipped ones).
    """
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Discover sources: any *.iafbt file or any directory shaped like
    # a legacy backtest (algorithm_id.json + runs/).
    sources: List[str] = []
    for root, dirs, files in os.walk(src_dir):
        for fname in files:
            if fname.endswith(BUNDLE_EXT):
                sources.append(os.path.join(root, fname))
        for dname in list(dirs):
            d = os.path.join(root, dname)
            if (
                os.path.isfile(os.path.join(d, "algorithm_id.json"))
                and os.path.isdir(os.path.join(d, "runs"))
            ):
                sources.append(d)
                # Don't descend into a recognised backtest dir.
                dirs.remove(dname)

    if not sources:
        return 0

    # Build (src, dst) pairs, optionally skipping ones that already
    # exist in dst_dir.
    ohlcv_store = (
        str(dst_dir / "ohlcv") if include_ohlcv else None
    )
    plan = []
    for src in sources:
        base = os.path.basename(os.path.normpath(src))
        if base.endswith(BUNDLE_EXT):
            base = base[: -len(BUNDLE_EXT)]
        dst = str(dst_dir / f"{base}{BUNDLE_EXT}")
        if skip_existing and os.path.isfile(dst):
            continue
        plan.append((src, dst, include_ohlcv, ohlcv_store, delete_source))

    if not plan:
        return 0

    n = len(plan)
    resolved_workers = min(_resolve_workers(workers), n)

    rows: List[dict] = []
    pbar = tqdm(
        total=n,
        desc="Migrating backtests",
        disable=not show_progress,
    )
    try:
        if resolved_workers > 1:
            # Bound in-flight tasks to ``resolved_workers`` so we don't
            # buffer the full plan inside the executor's feeder, and
            # consume results as they finish to keep memory flat.
            plan_iter = iter(plan)
            with ProcessPoolExecutor(max_workers=resolved_workers) as ex:
                inflight = {}
                for _ in range(resolved_workers):
                    try:
                        args = next(plan_iter)
                    except StopIteration:
                        break
                    inflight[ex.submit(_migrate_one, args)] = args

                while inflight:
                    done_set, _unused = wait(
                        inflight.keys(), return_when=FIRST_COMPLETED
                    )
                    for fut in done_set:
                        args = inflight.pop(fut)
                        try:
                            _out, row = fut.result()
                            if write_index:
                                rows.append(row)
                        except Exception as e:
                            logger.error(
                                f"Failed to migrate {args[0]}: {e}"
                            )
                        finally:
                            pbar.update(1)
                        try:
                            nxt = next(plan_iter)
                        except StopIteration:
                            continue
                        inflight[ex.submit(_migrate_one, nxt)] = nxt
        else:
            for args in plan:
                try:
                    _out, row = _migrate_one(args)
                    if write_index:
                        rows.append(row)
                except Exception as e:
                    logger.error(f"Failed to migrate {args[0]}: {e}")
                finally:
                    pbar.update(1)
    finally:
        pbar.close()

    if write_index and rows:
        import pandas as pd  # local import keeps top of module light
        df = pd.DataFrame(rows)
        df.to_parquet(
            Path(dst_dir) / "index.parquet",
            index=False,
            compression="zstd",
        )

    return n
