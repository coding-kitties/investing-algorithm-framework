"""``iaf index`` CLI \u2014 build a SQLite Tier-1 index over a folder of
``.iafbt`` bundles (epic #540 phase 2).

Walks the directory, opens each bundle with ``summary_only=True`` (no
Parquet metric-blob decode), derives a :class:`BacktestIndexRow` via
:meth:`Backtest.index_row`, and upserts into a
:class:`SqliteBacktestIndex`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional

from investing_algorithm_framework.domain import (
    Backtest,
    BUNDLE_EXT,
)
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

    index = SqliteBacktestIndex.create(out)
    n_ok = 0
    n_err = 0
    try:
        for path in paths:
            try:
                bt = Backtest.open(str(path), summary_only=True)
                bundle_path = (
                    str(path.relative_to(src)) if relative_paths
                    else str(path)
                )
                row = bt.index_row(bundle_path=bundle_path)
                index.upsert(row)
                n_ok += 1
            except Exception as exc:  # noqa: BLE001 \u2014 best-effort scan
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
        "Indexed %d bundle(s) into %s (%d failed)", n_ok, out, n_err,
    )
    return str(out)
