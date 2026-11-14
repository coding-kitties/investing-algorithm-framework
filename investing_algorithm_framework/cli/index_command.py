"""``iaf index`` CLI \u2014 build a SQLite Tier-1 index over a folder of
``.obtf`` bundles (epic #540 phase 2).

Walks the directory, opens each bundle with ``summary_only=True`` (no
Parquet metric-blob decode), derives a :class:`BacktestIndexRow` via
:meth:`Backtest.index_rows`, and upserts into a
:class:`SqliteBacktestIndex`.
"""

from __future__ import annotations

import logging
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from investing_algorithm_framework.domain import BacktestEvaluationFocus

from investing_algorithm_framework.domain import (
    Backtest,
    BUNDLE_EXT,
)
from investing_algorithm_framework.domain.backtesting \
    .backtest_summary_metrics import BacktestSummaryMetrics
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)

logger = logging.getLogger(__name__)


DEFAULT_INDEX_NAME = "index.sqlite"


def _iter_bundle_paths(
    directory: Path,
    exclude_dirs: Optional[List[str]] = None,
) -> Iterable[Path]:
    """Yield every ``*.obtf`` file under *directory* (sorted).

    Args:
        directory: Root folder to scan.
        exclude_dirs: Subdirectory names (not full paths) to skip.
            E.g. ``["top_selection"]`` prevents promoted-bundle folders
            from being included in the sweep index.
    """
    excluded = set(exclude_dirs) if exclude_dirs else set()
    results = []
    for path in directory.rglob(f"*{BUNDLE_EXT}"):
        relative_parts = path.relative_to(directory).parts[:-1]
        if excluded and any(part in excluded for part in relative_parts):
            continue
        results.append(path)
    return sorted(results)


def build_index(
    directory: str,
    output: Optional[str] = None,
    relative_paths: bool = True,
    show_progress: bool = False,
    incremental: bool = True,
    exclude_dirs: Optional[List[str]] = None,
) -> str:
    """Build (or refresh) a SQLite Tier-1 index over *directory*.

    Args:
        directory: Folder to scan for ``.obtf`` bundles.
        output: Path to the SQLite file. Defaults to
            ``<directory>/index.sqlite``.
        relative_paths: if True, store ``bundle_path`` relative to
            *directory* so the index file stays portable when the
            folder is moved/renamed.
        show_progress: emit a tqdm progress bar.
        incremental: if True (default), open the existing index (if
            any) and skip bundles whose ``(mtime, size)`` already
            match the on-disk file. Pass ``False`` to force a full
            rebuild.
        exclude_dirs: Subdirectory names to skip when scanning.
            E.g. ``["top_selection"]`` prevents promoted-bundle
            folders from polluting the sweep index. Matched against
            each path component, so nested directories are also
            excluded.

    Returns:
        Absolute path of the SQLite file that was written.
    """
    src = Path(directory).resolve()
    if not src.is_dir():
        raise NotADirectoryError(f"Not a directory: {src}")

    out = Path(output).resolve() if output else src / DEFAULT_INDEX_NAME
    paths: List[Path] = list(
        _iter_bundle_paths(src, exclude_dirs=exclude_dirs)
    )

    pbar = None
    if show_progress:
        try:
            from tqdm import tqdm
            pbar = tqdm(total=len(paths), desc="Indexing bundles")
        except ImportError:  # pragma: no cover - tqdm is a dep
            pbar = None

    if incremental and out.is_file():
        index = SqliteBacktestIndex.open(out)
    else:
        index = SqliteBacktestIndex.create(out)
    n_ok = 0
    n_err = 0
    n_skipped = 0
    try:
        for path in paths:
            try:
                stat = path.stat()
                bundle_path = (
                    str(path.relative_to(src)) if relative_paths
                    else str(path)
                )
                if incremental and index.is_up_to_date(
                    bundle_path, stat.st_mtime_ns, stat.st_size,
                ):
                    n_skipped += 1
                    continue

                bt = Backtest.open(str(path), summary_only=True)
                # v9.0: ``index_rows`` returns one row per populated
                # engine (vector and/or event). A dual-engine bundle
                # produces two upserts under the same bundle_path with
                # different ``engine_type`` values; the SQLite index's
                # composite primary key ``(bundle_path, engine_type)``
                # keeps them distinct.
                rows = bt.index_rows(bundle_path=bundle_path)
                for row in rows:
                    index.upsert(
                        row,
                        bundle_mtime_ns=stat.st_mtime_ns,
                        bundle_size=stat.st_size,
                    )
                n_ok += 1
            except Exception as exc:  # noqa: BLE001 — best-effort scan
                logger.warning("failed to index %s: %s", path, exc)
                n_err += 1
            finally:
                if pbar is not None:
                    pbar.update(1)
    finally:
        if pbar is not None:
            pbar.close()
        index.close()

    logger.info(
        "Indexed %d bundle(s) into %s (%d skipped, %d failed)",
        n_ok, out, n_skipped, n_err,
    )
    return str(out)


# ---------------------------------------------------------------------------
# list / rank helpers
# ---------------------------------------------------------------------------
DEFAULT_LIST_COLUMNS: Sequence[str] = (
    "algorithm_id",
    "tag",
    "summary_sharpe_ratio",
    "summary_total_net_gain_percentage",
    "summary_max_drawdown",
    "summary_number_of_trades",
    "bundle_path",
)

DEFAULT_RANK_COLUMNS: Sequence[str] = (
    "algorithm_id",
    "tag",
    "summary_sharpe_ratio",
    "summary_sortino_ratio",
    "summary_calmar_ratio",
    "summary_total_net_gain_percentage",
    "summary_max_drawdown",
    "bundle_path",
)

_SUMMARY_FIELD_NAMES = frozenset(
    f.name for f in dc_fields(BacktestSummaryMetrics)
)


def _resolve_index_path(path: str) -> Path:
    """Accept either a directory (look for ``index.sqlite`` inside) or
    a SQLite file path; return the resolved file path."""
    p = Path(path)
    if p.is_dir():
        candidate = p / DEFAULT_INDEX_NAME
        if not candidate.is_file():
            raise FileNotFoundError(
                f"No {DEFAULT_INDEX_NAME} in {p}. Run `iaf index {p}` "
                f"first or pass the SQLite file directly."
            )
        return candidate
    if not p.is_file():
        raise FileNotFoundError(f"Index file not found: {p}")
    return p


def _resolve_metric_column(name: str) -> str:
    """Map a user-friendly metric name to a real SQL column.

    Accepts both ``sharpe_ratio`` and ``summary_sharpe_ratio``; bare
    column names (``algorithm_id``, ``tag``, ...) are returned as-is.
    """
    if name.startswith("summary_"):
        return name
    if name in _SUMMARY_FIELD_NAMES:
        return f"summary_{name}"
    return name


def _row_to_flat_dict(row, columns: Sequence[str]) -> Dict[str, Any]:
    """Project a :class:`BacktestIndexRow` onto the requested columns."""
    out: Dict[str, Any] = {}
    summary = row.summary_metrics
    for col in columns:
        if col.startswith("summary_"):
            field = col[len("summary_"):]
            out[col] = (
                getattr(summary, field, None) if summary is not None
                else None
            )
        else:
            out[col] = getattr(row, col, None)
    return out


def list_index(
    index_path: str,
    sort_by: Optional[str] = None,
    ascending: bool = False,
    limit: Optional[int] = None,
    where: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    engine: Optional[str] = None,
    universe_key: Optional[str] = "",
    study: Optional[str] = None,
    anchor_algorithm_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query an index file and return matching rows as plain dicts.

    Args:
        index_path: Path to ``index.sqlite`` or a directory holding it.
        sort_by: Column to sort by (e.g. ``"sharpe_ratio"`` or
            ``"summary_sharpe_ratio"``). ``None`` keeps insertion order.
        ascending: Sort direction; default descending (best-first).
        limit: Maximum number of rows to return.
        where: Optional raw SQL ``WHERE`` fragment (no leading
            ``WHERE`` keyword). Use ``?`` placeholders only via
            :meth:`SqliteBacktestIndex.query` directly if you need
            bind parameters.
        columns: Columns to project; defaults to
            :data:`DEFAULT_LIST_COLUMNS`.
        engine: Optional engine filter, ``"vector"`` or ``"event"``.
            When set, only rows whose ``engine_type`` column matches
            are returned. Combined with ``where`` via ``AND``.
        universe_key: Filter on the ``universe_key`` column. The
            default ``""`` selects only the pooled cross-universe
            rows — the legacy single-row-per-engine shape — so
            existing reports keep their pre-multi-universe semantics.
            Pass an explicit universe key (e.g. ``"majors"``) to
            select only that universe's rows, or ``None`` to disable
            the filter and include every row (pooled + per-universe).
        study: Filter on the ``study_name`` column (Phase 3d). The
            default ``None`` includes every study side-by-side —
            unchanged from pre-Phase-3d behaviour for legacy
            single-study bundles. Pass an explicit study name (e.g.
            ``"in_sample"`` or ``"default"``) to restrict the
            report to that study slot.

    Returns:
        A list of column-name → value dicts, ready for tabulation.
    """
    if engine is not None and engine not in ("vector", "event"):
        raise ValueError(
            f"list_index: engine must be 'vector' or 'event', "
            f"got {engine!r}"
        )

    cols = list(columns) if columns else list(DEFAULT_LIST_COLUMNS)
    resolved = _resolve_index_path(index_path)

    clauses = []
    if where:
        clauses.append(f"({where})")
    if engine is not None:
        clauses.append(f"engine_type = '{engine}'")
    if universe_key is not None:
        # Quote-double to neutralise embedded single quotes; universe
        # keys are arbitrary user strings (e.g. "us-large-cap").
        safe = str(universe_key).replace("'", "''")
        clauses.append(f"universe_key = '{safe}'")
    if study is not None:
        # Accept either a Study object or a bare name string.
        study_name_str = (
            study.name if hasattr(study, "name") else str(study)
        )
        safe_study = study_name_str.replace("'", "''")
        clauses.append(f"study_name = '{safe_study}'")
    if anchor_algorithm_id is not None:
        # Lineage filter (v5+). Pass an explicit anchor's
        # ``algorithm_id`` to pull only its sibling-bundle
        # neighbourhood (param-robustness perturbations,
        # cooldown-stress runs, etc.). Pass the literal string
        # ``"<none>"`` to match anchor bundles only
        # (``anchor_algorithm_id IS NULL``).
        if anchor_algorithm_id == "<none>":
            clauses.append("anchor_algorithm_id IS NULL")
        else:
            safe_anchor = str(anchor_algorithm_id).replace("'", "''")
            clauses.append(f"anchor_algorithm_id = '{safe_anchor}'")
    base_where = " AND ".join(clauses) if clauses else "1=1"
    fragment = base_where
    if sort_by:
        sort_col = _resolve_metric_column(sort_by)
        direction = "ASC" if ascending else "DESC"
        # NULLs always come last regardless of direction so the table
        # is useful even when some bundles are missing the metric.
        fragment += (
            f' ORDER BY "{sort_col}" IS NULL, "{sort_col}" {direction}'
        )
    if limit is not None:
        fragment += f" LIMIT {int(limit)}"

    with SqliteBacktestIndex.open(resolved) as idx:
        rows = idx.query(where=fragment)
    return [_row_to_flat_dict(r, cols) for r in rows]


def rank_index(
    index_path: str,
    by: Optional[str] = None,
    limit: Optional[int] = None,
    where: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    ascending: bool = False,
    focus: Optional["BacktestEvaluationFocus | str"] = None,
    weights: Optional[Dict[str, float]] = None,
    engine: Optional[str] = None,
    universe_key: Optional[str] = "",
    study: Optional[str] = None,
    anchor_algorithm_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Rank bundles by a single metric or a weighted combination.

    **Single-metric mode** (original behaviour):
        Pass ``by="sharpe_ratio"`` to sort by one column.

    **Weighted-score mode**:
        Pass ``focus`` (a :class:`BacktestEvaluationFocus` or its
        string name, e.g. ``"balanced"``) and/or ``weights`` to rank
        by a normalised weighted score across many metrics.

        When both ``focus`` and ``weights`` are given, ``weights``
        entries override those from the focus preset.  A ``_score``
        column is added to each result dict.

    Args:
        index_path: Path to ``index.sqlite`` or its parent directory.
        by: Column to sort by (single-metric mode).  Ignored when
            *focus* or *weights* is set.
        limit: Maximum rows to return.
        where: Optional SQL ``WHERE`` fragment.
        columns: Columns to project.
        ascending: Sort direction (default best-first / descending).
        focus: A :class:`BacktestEvaluationFocus` value or string
            (e.g. ``"balanced"``).
        weights: Custom ``{metric: weight}`` dict.  Metric names
            without a ``summary_`` prefix are accepted (they are
            mapped automatically).
        engine: Optional engine filter, ``"vector"`` or ``"event"``.
            When set, only rows for that engine slot participate in
            the ranking. To produce separate vector- and event-only
            rankings, call this function twice.
        universe_key: Filter on the ``universe_key`` column. The
            default ``""`` ranks only the pooled cross-universe rows
            so existing reports keep their pre-multi-universe
            semantics. Pass an explicit universe key to rank only
            that universe's rows, or ``None`` to rank across every
            row (pooled + per-universe — usually not what you want).
        study: Filter on the ``study_name`` column (Phase 3d). The
            default ``None`` ranks across every study side-by-side.
            Pass an explicit study name (e.g. ``"in_sample"``) to
            rank only that study's rows — the recommended setup
            when comparing backtests of the same algorithm across
            multiple studies (e.g. in-sample vs out-of-sample).
    """
    cols = list(columns) if columns else list(DEFAULT_RANK_COLUMNS)

    if focus is not None or weights is not None:
        return _rank_index_weighted(
            index_path,
            focus=focus,
            weights=weights,
            limit=limit,
            where=where,
            columns=cols,
            ascending=ascending,
            engine=engine,
            universe_key=universe_key,
            study=study,
            anchor_algorithm_id=anchor_algorithm_id,
        )

    if by is None:
        raise ValueError(
            "Either 'by' (single metric) or 'focus'/'weights' "
            "(weighted score) must be provided."
        )

    return list_index(
        index_path,
        sort_by=by,
        ascending=ascending,
        limit=limit,
        where=where,
        columns=cols,
        engine=engine,
        universe_key=universe_key,
        study=study,
        anchor_algorithm_id=anchor_algorithm_id,
    )


def _rank_index_weighted(
    index_path: str,
    *,
    focus=None,
    weights: Optional[Dict[str, float]] = None,
    limit: Optional[int] = None,
    where: Optional[str] = None,
    columns: Sequence[str] = (),
    ascending: bool = False,
    engine: Optional[str] = None,
    universe_key: Optional[str] = "",
    study: Optional[str] = None,
    anchor_algorithm_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Score every row in the index using normalised weighted metrics.

    Mirrors the logic in :func:`rank_results` /
    :func:`compute_score` but works directly on the flat SQLite
    index — no Parquet decode, no :class:`Backtest` instantiation.
    """
    import math
    from investing_algorithm_framework.analysis.ranking import (
        create_weights, normalize,
    )

    effective_weights = create_weights(
        focus=focus, custom_weights=weights,
    )

    # Map bare metric names → summary_ prefixed column names so we
    # can read them from the flat row dicts.
    col_weights: Dict[str, float] = {}
    for metric, w in effective_weights.items():
        col = _resolve_metric_column(metric)
        col_weights[col] = w

    # Ensure every weighted column is included in the projection so
    # we can compute the score.
    all_cols = list(dict.fromkeys(list(columns) + list(col_weights)))

    rows = list_index(
        index_path,
        sort_by=None,
        limit=None,
        where=where,
        columns=all_cols,
        engine=engine,
        universe_key=universe_key,
        study=study,
        anchor_algorithm_id=anchor_algorithm_id,
    )

    if not rows:
        return []

    # Compute per-metric normalisation ranges.
    ranges: Dict[str, tuple] = {}
    for col in col_weights:
        values = [
            r[col] for r in rows
            if isinstance(r.get(col), (int, float))
            and r[col] is not None
            and not math.isnan(r[col])
            and not math.isinf(r[col])
        ]
        if values:
            ranges[col] = (min(values), max(values))

    # Score each row.
    for row in rows:
        score = 0.0
        for col, w in col_weights.items():
            v = row.get(col)
            if not isinstance(v, (int, float)):
                continue
            if v is None or math.isnan(v) or math.isinf(v):
                continue
            if col in ranges:
                v = normalize(v, ranges[col][0], ranges[col][1])
            score += w * v
        row["_score"] = round(score, 6)

    rows.sort(key=lambda r: r["_score"], reverse=not ascending)

    if limit is not None:
        rows = rows[:limit]

    # Project back to requested columns + _score.
    out_cols = list(columns) + ["_score"]
    return [
        {k: r.get(k) for k in out_cols}
        for r in rows
    ]


def format_table(
    rows: List[Dict[str, Any]],
    columns: Optional[Sequence[str]] = None,
) -> str:
    """Render rows as a fixed-width text table (no external deps)."""
    if not rows:
        return "(no rows)"
    cols = list(columns) if columns else list(rows[0].keys())

    def _fmt(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    cells = [[_fmt(r.get(c)) for c in cols] for r in rows]
    widths = [
        max(len(c), *(len(row[i]) for row in cells))
        for i, c in enumerate(cols)
    ]
    sep = "  "
    header = sep.join(c.ljust(widths[i]) for i, c in enumerate(cols))
    rule = sep.join("-" * w for w in widths)
    body = "\n".join(
        sep.join(row[i].ljust(widths[i]) for i in range(len(cols)))
        for row in cells
    )
    return f"{header}\n{rule}\n{body}"


# ---------------------------------------------------------------------------
# prune helpers
# ---------------------------------------------------------------------------

def prune_backtests(
    directory: str,
    keep: List[Dict[str, Any]],
    *,
    archive_dir: Optional[str] = None,
    dry_run: bool = False,
    show_progress: bool = False,
    flatten: bool = False,
) -> Dict[str, Any]:
    """Move or delete bundles that are **not** in *keep*.

    Args:
        directory: Folder containing the ``.obtf`` bundles (same
            path you passed to :func:`build_index`).
        keep: List of row dicts (as returned by :func:`rank_index`)
            whose ``"bundle_path"`` values identify bundles to keep.
        archive_dir: If given, pruned bundles are *moved* here
            (preserving relative sub-paths) instead of deleted.
            Created if it does not exist.
        dry_run: When True, report what *would* happen without
            touching the file system.
        show_progress: Show a tqdm progress bar.
        flatten: When True and *archive_dir* is set, place all
            pruned bundles directly into *archive_dir* instead of
            preserving the original sub-directory structure.

    Returns:
        ``{"kept": int, "pruned": int, "archive_dir": str | None}``
    """
    import shutil

    src = Path(directory).resolve()
    if not src.is_dir():
        raise NotADirectoryError(f"Not a directory: {src}")

    keep_set = frozenset(
        r["bundle_path"] for r in keep if "bundle_path" in r
    )

    all_bundles = list(_iter_bundle_paths(src))

    archive = Path(archive_dir).resolve() if archive_dir else None
    if archive is not None and not dry_run:
        archive.mkdir(parents=True, exist_ok=True)

    pbar = None
    if show_progress:
        try:
            from tqdm import tqdm
            pbar = tqdm(total=len(all_bundles), desc="Pruning bundles")
        except ImportError:
            pbar = None

    n_kept = 0
    n_pruned = 0

    try:
        for bundle_path in all_bundles:
            rel = str(bundle_path.relative_to(src))
            if rel in keep_set:
                n_kept += 1
            else:
                if not dry_run:
                    if archive is not None:
                        if flatten:
                            dest = archive / bundle_path.name
                        else:
                            dest = archive / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(bundle_path), str(dest))
                    else:
                        bundle_path.unlink()
                n_pruned += 1
            if pbar is not None:
                pbar.update(1)
    finally:
        if pbar is not None:
            pbar.close()

    # Refresh the index to remove pruned entries.
    if not dry_run and n_pruned > 0:
        build_index(
            str(src),
            show_progress=False,
            incremental=False,
        )

    return {
        "kept": n_kept,
        "pruned": n_pruned,
        "archive_dir": str(archive) if archive else None,
    }


def promote_backtests(
    directory: str,
    keep: List[Dict[str, Any]],
    dest_dir: str,
    *,
    mode: str = "copy",
    clear_dest: bool = True,
    flatten: bool = True,
    dry_run: bool = False,
    show_progress: bool = False,
    refresh_index: bool = True,
) -> Dict[str, Any]:
    """Promote the bundles in ``keep`` into a separate folder.

    This is the dual of :func:`prune_backtests`. Where ``prune``
    removes (or archives) the bundles *not* in ``keep``,
    ``promote_backtests`` collects the bundles *that are* in
    ``keep`` into a dedicated destination folder — useful for
    tutorial workflows that want a clean "top-N" directory to feed
    into a downstream notebook (e.g. an out-of-sample run) without
    touching the original sweep results.

    Args:
        directory: Folder containing the source ``.obtf`` bundles
            (the directory passed to :func:`build_index`).
        keep: List of row dicts (as returned by :func:`rank_index`)
            whose ``"bundle_path"`` values identify bundles to
            promote.
        dest_dir: Destination folder for the promoted bundles.
            Created if it does not exist.
        mode: ``"copy"`` (default) duplicates each bundle into
            ``dest_dir`` so the source remains intact. ``"move"``
            relocates them, leaving ``directory`` with only the
            non-promoted bundles (the inverse of ``prune``).
        clear_dest: When True (default), wipe ``dest_dir`` before
            promoting so the folder reflects exactly the current
            ``keep`` selection — no leakage from earlier runs.
        flatten: When True (default), all promoted bundles land
            directly in ``dest_dir``. When False, the source's
            sub-directory structure is preserved relative to
            ``directory``.
        dry_run: When True, report what would happen without
            touching the file system.
        show_progress: Show a tqdm progress bar.
        refresh_index: When True (default) and not dry-run, rebuild
            the Tier-1 SQLite index inside ``dest_dir`` after the
            promotion completes. Disable when callers prefer to
            control index refresh themselves.

    Returns:
        ``{"promoted": int, "missing": int, "dest_dir": str,
        "mode": str}`` where ``missing`` counts ``keep`` rows whose
        bundle was not found on disk under ``directory``.
    """
    import shutil

    if mode not in ("copy", "move"):
        raise ValueError(
            f"mode must be 'copy' or 'move', got {mode!r}"
        )

    src = Path(directory).resolve()
    if not src.is_dir():
        raise NotADirectoryError(f"Not a directory: {src}")

    dest = Path(dest_dir).resolve()

    # Deduplicate by bundle_path so a dual-engine row pair (same
    # bundle indexed for both engines) doesn't trigger two copies
    # of the same file.
    seen: set = set()
    bundle_rels: List[str] = []
    for row in keep:
        rel = row.get("bundle_path")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        bundle_rels.append(rel)

    if not dry_run:
        if clear_dest and dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)

    pbar = None
    if show_progress:
        try:
            from tqdm import tqdm
            pbar = tqdm(total=len(bundle_rels), desc="Promoting bundles")
        except ImportError:
            pbar = None

    n_promoted = 0
    n_missing = 0

    try:
        for rel in bundle_rels:
            source_path = src / rel
            if not source_path.exists():
                n_missing += 1
                if pbar is not None:
                    pbar.update(1)
                continue

            if flatten:
                target = dest / source_path.name
            else:
                target = dest / rel
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)

            if not dry_run:
                if mode == "copy":
                    shutil.copy2(str(source_path), str(target))
                else:  # move
                    shutil.move(str(source_path), str(target))

            n_promoted += 1
            if pbar is not None:
                pbar.update(1)
    finally:
        if pbar is not None:
            pbar.close()

    if not dry_run and refresh_index and n_promoted > 0:
        build_index(
            str(dest),
            show_progress=False,
            incremental=False,
        )
        if mode == "move":
            # Source lost the promoted bundles; refresh its index too.
            build_index(
                str(src),
                show_progress=False,
                incremental=False,
            )

    return {
        "promoted": n_promoted,
        "missing": n_missing,
        "dest_dir": str(dest),
        "mode": mode,
    }
