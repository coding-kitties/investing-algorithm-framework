"""Helper for loading and materialising a ranked ``top_selection``
folder of ``.obtf`` bundles — the load/rank/dedupe/recover-params
workflow shared by the param-sweep and out-of-sample notebooks.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from investing_algorithm_framework.cli.index_command import (
    build_index, rank_index,
)
from investing_algorithm_framework.domain import (
    Backtest, BacktestEvaluationFocus,
)
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
)


@dataclass
class TopSelection:
    """Result of :func:`load_top_selection`.

    Attributes:
        rows: Raw ranked rows from ``rank_index`` (SQLite dicts).
        backtests: Materialised, deduplicated ``Backtest`` objects for
            each ranked bundle with recoverable params, in rank order.
            Bundles with no recoverable params are excluded (see
            ``skipped_algorithm_ids``) so this list stays index-aligned
            with ``param_variations``.
        param_variations: The strategy param dict recovered from each
            backtest (via ``metadata["params"]``, falling back to
            ``.parameters`` for legacy bundles), aligned 1:1 with
            ``backtests``.
        skipped_algorithm_ids: ``algorithm_id``s of bundles with no
            recoverable params, excluded from both ``backtests`` and
            ``param_variations``.
    """

    rows: List[Dict[str, Any]] = field(default_factory=list)
    backtests: List[Backtest] = field(default_factory=list)
    param_variations: List[Dict[str, Any]] = field(default_factory=list)
    skipped_algorithm_ids: List[str] = field(default_factory=list)


def load_top_selection(
    top_selection_path: Union[str, Path],
    focus: Optional[Union["BacktestEvaluationFocus", str]] =
    BacktestEvaluationFocus.BALANCED,
    engine: Optional[str] = "vector",
    study: Optional[str] = None,
    limit: Optional[int] = None,
    rebuild_index: bool = True,
    show_progress: bool = True,
) -> TopSelection:
    """Rank, load and materialise a ``top_selection`` bundle folder.

    Combines the steps every param-sweep / OOS / event notebook
    repeats: refresh the Tier-1 SQLite index, rank it with a weighted
    focus, then open and deduplicate the winning bundles via
    ``LocalDirStore`` (by ``bundle_path``, so dual-engine/multi-study
    bundles aren't opened twice) while recovering each one's original
    strategy params.

    Args:
        top_selection_path: Folder of ``.obtf`` bundles to rank.
        focus: Weighted ranking focus (default ``BALANCED``); passed
            straight to ``rank_index``.
        engine: Engine slot to rank on (``"vector"`` or ``"event"``).
        study: Study name to scope the ranking to (e.g.
            ``"in_sample_param_sweep"``). ``None`` pools every
            study's rows together — usually not what you want on a
            multi-study bundle.
        limit: Maximum number of winners to keep. ``None`` keeps all.
        rebuild_index: (Re)build the Tier-1 index (incrementally)
            before ranking. Set ``False`` to use whatever index
            already exists on disk.
        show_progress: Show a progress bar while (re)building the
            index.

    Returns:
        TopSelection: ranked rows, deduplicated ``Backtest`` objects
            and their recovered param variations.
    """
    path_str = str(top_selection_path)

    if rebuild_index:
        build_index(path_str, show_progress=show_progress, incremental=True)

    rows = rank_index(
        path_str, focus=focus, engine=engine, study=study, limit=limit,
    )

    store = LocalDirStore(path_str)
    seen_bundle_paths = set()
    opened: List[Backtest] = []
    for row in rows:
        bundle_path = row["bundle_path"]
        if bundle_path in seen_bundle_paths:
            continue
        seen_bundle_paths.add(bundle_path)
        opened.append(store.open(bundle_path))

    # ``backtests`` and ``param_variations`` are kept index-aligned:
    # bundles with no recoverable params are dropped from *both* lists
    # (not just ``param_variations``), so ``backtests[i]`` is always
    # the backtest ``param_variations[i]`` was recovered from.
    backtests: List[Backtest] = []
    param_variations: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for bt in opened:
        metadata = bt.get_metadata() or {}
        variant = dict(metadata.get("params") or {})
        if not variant:
            # Legacy bundles without metadata["params"] fall back to
            # the canonical ``Backtest.parameters`` slot.
            variant = dict(bt.parameters or {})
        if not variant:
            skipped.append(bt.algorithm_id)
            continue
        backtests.append(bt)
        param_variations.append(variant)

    return TopSelection(
        rows=rows,
        backtests=backtests,
        param_variations=param_variations,
        skipped_algorithm_ids=skipped,
    )
