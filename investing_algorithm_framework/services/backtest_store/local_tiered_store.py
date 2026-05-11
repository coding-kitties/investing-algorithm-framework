"""``LocalTieredStore`` — Tier-1 SQLite + Tier-2 Parquet + canonical
``.iafbt`` bundles on a local filesystem (epic #540 phase 3b).

Layout under *root*::

    <root>/
        index.sqlite               # Tier-1, kept in sync on every write
        bundles/<handle>.iafbt     # canonical bytes (source of truth)
        parquet/
            portfolio_snapshots/run_id=<handle>/part-0.parquet
            trades/run_id=<handle>/part-0.parquet
            orders/run_id=<handle>/part-0.parquet

The bundle file is the canonical representation. The Tier-1 index and
the Tier-2 Parquet datasets are derived, eagerly maintained, and
best-effort: a malformed sidecar never blocks a write or read against
the bundle. This keeps Phase 3b's invariants simple and trivially
preserves byte-identical round-trips through ``Backtest.save_bundle``
/ ``Backtest.open``. Byte-identical *Tier-2 → Backtest* reassembly is
Phase 3d.

The Parquet datasets are hive-partitioned on ``run_id`` (which is the
store handle), so cross-run analytics is one DuckDB / Polars scan::

    duckdb.sql(\"\"\"
        SELECT run_id, total_value
        FROM read_parquet('store/parquet/portfolio_snapshots/**/*.parquet',
                          hive_partitioning=True)
        WHERE run_id IN (SELECT bundle_path FROM
                         read_csv('top20.csv'))
    \"\"\")
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Optional, Union

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestIndexRow,
    BUNDLE_EXT,
)
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)

from .base import (
    BacktestStore,
    StoreError,
    StoreHandle,
    StoreHandleNotFoundError,
)
from . import decompose as _decompose

logger = logging.getLogger(__name__)


INDEX_FILENAME = "index.sqlite"
BUNDLES_SUBDIR = "bundles"
PARQUET_SUBDIR = "parquet"


def _records_to_table(records: List[dict]) -> Optional[Any]:
    """Convert ``to_dict()``-shaped records to a pyarrow Table.

    Returns ``None`` when there are no records, the table cannot be
    built (heterogeneous schema, unsupported types, …), or pyarrow is
    not importable. Callers must treat the absence of a sidecar as
    valid — the bundle is canonical.
    """
    if not records:
        return None
    try:
        import pyarrow as pa
        import pandas as pd
    except ImportError:  # pragma: no cover - dependency missing
        return None
    try:
        df = pd.DataFrame.from_records(records)
        # Object columns containing dicts/lists can blow up Parquet
        # schema inference. Stringify them so the analytics path stays
        # usable; the bundle still has the original structured data.
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].map(
                    lambda v: (
                        v if v is None
                        or isinstance(v, (str, int, float, bool))
                        else str(v)
                    )
                )
        return pa.Table.from_pandas(df, preserve_index=False)
    except Exception as exc:  # pragma: no cover - logged
        logger.warning(
            "Tier-2 Parquet table build failed: %s", exc,
        )
        return None


class LocalTieredStore(BacktestStore):
    """Tier-1 + Tier-2 + canonical-bundle store on a local filesystem.

    The store is fully self-contained: a single root directory holds
    every artefact, so it can be copied, symlinked, or rsync'd with
    a single ``cp -r``. Concurrent readers are safe; concurrent
    writers from different processes may race on the SQLite index
    (WAL handles it) but per-handle write atomicity is the caller's
    responsibility.

    Phase 3b deliberately keeps the .iafbt bundle as the canonical
    representation. Reads always go through the bundle so the
    Backtest round-trip is bit-for-bit identical to today's
    behaviour. Tier-2 sidecars are *auxiliary* — used only for
    cross-run analytics — and are rebuilt from the bundle on demand.
    """

    def __init__(self, root: Union[str, Path]) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._bundles_dir = self.root / BUNDLES_SUBDIR
        self._parquet_dir = self.root / PARQUET_SUBDIR
        self._index_path = self.root / INDEX_FILENAME
        self._bundles_dir.mkdir(parents=True, exist_ok=True)
        self._parquet_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_handle(handle: StoreHandle) -> str:
        """Strip the .iafbt suffix; handles are stored bare in Tier-1."""
        if handle.endswith(BUNDLE_EXT):
            return handle[: -len(BUNDLE_EXT)]
        return handle

    def _bundle_path(self, handle: StoreHandle) -> Path:
        bare = self._normalize_handle(handle)
        candidate = (self._bundles_dir / (bare + BUNDLE_EXT)).resolve()
        try:
            candidate.relative_to(self._bundles_dir)
        except ValueError as exc:
            raise StoreError(
                f"handle {handle!r} resolves outside the bundles "
                f"directory {self._bundles_dir}"
            ) from exc
        return candidate

    def _partition_dir(self, dataset: str, handle: StoreHandle) -> Path:
        bare = self._normalize_handle(handle)
        return self._parquet_dir / dataset / f"run_id={bare}"

    def _default_handle(self, backtest: Backtest) -> StoreHandle:
        if backtest.algorithm_id:
            return str(backtest.algorithm_id)
        from datetime import datetime, timezone
        return "backtest_" + datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S%f"
        )

    def _open_index(self) -> SqliteBacktestIndex:
        if self._index_path.is_file():
            return SqliteBacktestIndex.open(self._index_path)
        return SqliteBacktestIndex.create(self._index_path)

    # ------------------------------------------------------------------
    # BacktestStore: write / open / exists / delete
    # ------------------------------------------------------------------
    def write(
        self,
        backtest: Backtest,
        *,
        handle: Optional[StoreHandle] = None,
    ) -> StoreHandle:
        if handle is None:
            handle = self._default_handle(backtest)
        bare = self._normalize_handle(handle)
        bundle_path = self._bundle_path(bare)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Canonical bytes — bundle.
        backtest.save_bundle(bundle_path)

        # 2. Tier-1 — SQLite row.
        stat = bundle_path.stat()
        row = backtest.index_row(bundle_path=bare)
        index = self._open_index()
        try:
            index.upsert(
                row,
                bundle_mtime_ns=stat.st_mtime_ns,
                bundle_size=stat.st_size,
            )
        finally:
            index.close()

        # 3. Tier-2 — Parquet sidecars (best-effort).
        self._write_parquet_sidecars(backtest, bare)

        return bare

    def _write_parquet_sidecars(
        self, backtest: Backtest, handle: str,
    ) -> None:
        try:
            import pyarrow.parquet as pq
        except ImportError:  # pragma: no cover - pyarrow missing
            logger.debug("pyarrow unavailable, skipping Tier-2 sidecars")
            return
        for name, decomposer in _decompose.DATASETS:
            try:
                records = decomposer(backtest, handle)
                table = _records_to_table(records)
                if table is None:
                    # Always overwrite empties so deletion of all
                    # snapshots leaves no stale data.
                    target_dir = self._partition_dir(name, handle)
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    continue
                target_dir = self._partition_dir(name, handle)
                target_dir.mkdir(parents=True, exist_ok=True)
                pq.write_table(
                    table,
                    target_dir / "part-0.parquet",
                    compression="zstd",
                )
            except Exception as exc:  # pragma: no cover - logged
                logger.warning(
                    "Tier-2 sidecar write failed for %s/%s: %s",
                    name, handle, exc,
                )

    def open(
        self,
        handle: StoreHandle,
        *,
        summary_only: bool = False,
    ) -> Backtest:
        path = self._bundle_path(handle)
        if not path.is_file():
            raise StoreHandleNotFoundError(handle)
        return Backtest.open(str(path), summary_only=summary_only)

    def exists(self, handle: StoreHandle) -> bool:
        try:
            return self._bundle_path(handle).is_file()
        except StoreError:
            return False

    def delete(self, handle: StoreHandle) -> None:
        bare = self._normalize_handle(handle)
        try:
            path = self._bundle_path(bare)
        except StoreError:
            return
        if path.is_file():
            path.unlink()
        # Tier-2 partitions.
        for name, _ in _decompose.DATASETS:
            part = self._partition_dir(name, bare)
            if part.exists():
                shutil.rmtree(part, ignore_errors=True)
        # Tier-1 row.
        if self._index_path.is_file():
            index = self._open_index()
            try:
                index._conn.execute(
                    'DELETE FROM "backtest_index" WHERE bundle_path = ?',
                    (bare,),
                )
                index._conn.commit()
            finally:
                index.close()

    # ------------------------------------------------------------------
    # BacktestStore: listing
    # ------------------------------------------------------------------
    def iter_handles(self) -> Iterator[StoreHandle]:
        if not self._bundles_dir.is_dir():
            return
        for p in sorted(self._bundles_dir.rglob(f"*{BUNDLE_EXT}")):
            if p.is_file():
                yield p.stem  # handle is the bare basename

    def iter_index_rows(self) -> Iterator[BacktestIndexRow]:
        if not self._index_path.is_file():
            return
        index = self._open_index()
        try:
            yield from index.iter_rows()
        finally:
            index.close()

    def __len__(self) -> int:
        if not self._index_path.is_file():
            return sum(1 for _ in self.iter_handles())
        index = self._open_index()
        try:
            return len(index)
        finally:
            index.close()

    def __contains__(self, handle: object) -> bool:
        if not isinstance(handle, str):
            return False
        return self.exists(handle)

    # ------------------------------------------------------------------
    # SupportsCopyFrom
    # ------------------------------------------------------------------
    def copy_from(
        self,
        src: BacktestStore,
        *,
        handles: Optional[Iterable[StoreHandle]] = None,
    ) -> int:
        chosen = list(handles) if handles is not None else list(
            src.iter_handles()
        )
        n = 0
        for h in chosen:
            try:
                bt = src.open(h)
            except StoreHandleNotFoundError:
                logger.warning("copy_from: handle %r missing in src", h)
                continue
            self.write(bt, handle=h)
            n += 1
        return n

    # ------------------------------------------------------------------
    # Tier-2 cross-run analytics helpers
    # ------------------------------------------------------------------
    def scan(self, dataset: str) -> Any:
        """Return a :class:`pyarrow.dataset.Dataset` over *dataset*.

        ``dataset`` must be one of ``"portfolio_snapshots"``,
        ``"trades"``, ``"orders"``. The returned object is
        hive-partitioned on ``run_id`` and can be filtered /
        materialised with the standard Arrow / DuckDB APIs.

        Example::

            ds = store.scan("trades")
            df = ds.to_table(filter=ds.field("run_id") == "abc").to_pandas()

        Returns ``None`` if the dataset directory does not exist yet.
        """
        known = {name for name, _ in _decompose.DATASETS}
        if dataset not in known:
            raise ValueError(
                f"unknown dataset {dataset!r}; expected one of {sorted(known)}"
            )
        root = self._parquet_dir / dataset
        if not root.is_dir():
            return None
        import pyarrow.dataset as ds  # local import: pyarrow optional
        return ds.dataset(
            str(root), format="parquet", partitioning="hive",
        )

    def scan_snapshots(self) -> Any:
        return self.scan("portfolio_snapshots")

    def scan_trades(self) -> Any:
        return self.scan("trades")

    def scan_orders(self) -> Any:
        return self.scan("orders")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def rebuild_index(self) -> int:
        """Drop the Tier-1 SQLite and rebuild it from the bundles.

        Useful when sidecars were edited out-of-band or after a
        software upgrade adds new index columns. Returns the number of
        rows written.
        """
        if self._index_path.is_file():
            self._index_path.unlink()
        n = 0
        index = self._open_index()
        try:
            for handle in self.iter_handles():
                bundle = self._bundle_path(handle)
                stat = bundle.stat()
                try:
                    bt = Backtest.open(str(bundle), summary_only=True)
                except Exception as exc:  # pragma: no cover - logged
                    logger.warning(
                        "rebuild_index: skipping %s: %s", handle, exc,
                    )
                    continue
                index.upsert(
                    bt.index_row(bundle_path=handle),
                    bundle_mtime_ns=stat.st_mtime_ns,
                    bundle_size=stat.st_size,
                )
                n += 1
        finally:
            index.close()
        return n

    def __repr__(self) -> str:
        return f"LocalTieredStore(root={str(self.root)!r})"
