"""``iaf index`` CLI \u2014 build a SQLite Tier-1 index over a folder of
``.iafbt`` bundles (epic #540 phase 2).

Walks the directory, opens each bundle with ``summary_only=True`` (no
Parquet metric-blob decode), derives a :class:`BacktestIndexRow` via
:meth:`Backtest.index_row`, and upserts into a
:class:`SqliteBacktestIndex`.
"""

from __future__ import annotations

import logging
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

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


def _iter_bundle_paths(directory: Path) -> Iterable[Path]:
    """Yield every ``*.iafbt`` file under *directory* (sorted)."""
    return sorted(directory.rglob(f"*{BUNDLE_EXT}"))


def build_index(
    directory: str,
    output: Optional[str] = None,
    relative_paths: bool = True,
    show_progress: bool = False,
    incremental: bool = True,
) -> str:
    """Build (or refresh) a SQLite Tier-1 index over *directory*.

    Args:
        directory: Folder to scan for ``.iafbt`` bundles.
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

    Returns:
        Absolute path of the SQLite file that was written.
    """
    src = Path(directory).resolve()
    if not src.is_dir():
        raise NotADirectoryError(f"Not a directory: {src}")

    out = Path(output).resolve() if output else src / DEFAULT_INDEX_NAME
    paths: List[Path] = list(_iter_bundle_paths(src))

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
                row = bt.index_row(bundle_path=bundle_path)
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

    Returns:
        A list of column-name → value dicts, ready for tabulation.
    """
    cols = list(columns) if columns else list(DEFAULT_LIST_COLUMNS)
    resolved = _resolve_index_path(index_path)

    base_where = f"({where})" if where else "1=1"
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
    by: str,
    limit: int = 10,
    where: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    ascending: bool = False,
) -> List[Dict[str, Any]]:
    """Rank bundles by a metric. Thin wrapper around :func:`list_index`
    with a different default column set and a required ``by`` arg."""
    cols = list(columns) if columns else list(DEFAULT_RANK_COLUMNS)
    return list_index(
        index_path,
        sort_by=by,
        ascending=ascending,
        limit=limit,
        where=where,
        columns=cols,
    )


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
