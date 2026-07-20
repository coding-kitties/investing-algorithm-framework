"""Helpers for stamping ``study_name`` / ``study_description`` and
matching strategies to :class:`Universe` definitions on
:class:`Backtest` objects.

These helpers are pure (no I/O) so the runner can call them in-process
before checkpoints are flushed to disk, ensuring on-disk bundles
already carry the correct top-level study/universe fields even if a
sweep is interrupted mid-run.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)  # noqa: E501

from .backtest import Backtest
from .universe import Universe


def build_strategy_universe_map(
    strategies: Iterable[Any],
    universes: Optional[List[Universe]],
) -> Dict[str, Universe]:
    """Match each strategy to exactly one ``Universe`` by symbol subset.

    Returns a ``{algorithm_id: Universe}`` mapping. Each
    ``strategy.symbols`` must be a non-empty subset of exactly one
    universe's ``symbols`` list. When a strategy declares no symbols
    and exactly one universe is provided, that universe is used.

    Raises:
        OperationalException: if any universe key is missing or
            duplicated, if a strategy's symbols match no universe, or
            if a strategy declares no symbols while multiple universes
            are provided.
    """
    if not universes:
        return {}

    seen_keys = set()
    for u in universes:
        key = getattr(u, "key", None)
        if not key:
            raise OperationalException(
                "Every Universe passed to run_*_backtests must have a "
                "non-empty 'key'."
            )
        if key in seen_keys:
            raise OperationalException(
                f"Duplicate Universe key {key!r} \u2014 keys must be unique "
                "within a single run."
            )
        seen_keys.add(key)

    mapping: Dict[str, Universe] = {}
    for s in strategies:
        s_syms = set(getattr(s, "symbols", None) or [])
        if not s_syms:
            if len(universes) == 1:
                mapping[s.algorithm_id] = universes[0]
                continue
            raise OperationalException(
                f"Strategy {s.algorithm_id!r} declares no 'symbols' "
                "but multiple universes were provided. Either declare "
                "symbols on the strategy or pass exactly one universe."
            )

        matches = [
            u for u in universes
            if not u.symbols or s_syms.issubset(set(u.symbols))
        ]
        if len(matches) == 0:
            raise OperationalException(
                f"Strategy {s.algorithm_id!r} symbols {sorted(s_syms)} "
                "are not a subset of any provided universe. Universes: "
                + ", ".join(
                    f"{u.key}={list(u.symbols or [])}" for u in universes
                )
            )
        if len(matches) > 1:
            # Smallest matching universe wins (most specific).
            matches.sort(key=lambda u: len(u.symbols or []))
        mapping[s.algorithm_id] = matches[0]
    return mapping


def stamp_backtest(
    backtest: Backtest,
    *,
    study_name: Optional[str] = None,
    study_description: Optional[str] = None,
    universe: Optional[Universe] = None,
    anchor_algorithm_id: Optional[str] = None,
) -> None:
    """Stamp study fields and a single matched ``Universe`` on a
    backtest in place.

    - Sets the default study's ``name`` / ``description`` if
      provided (``None`` leaves the existing value untouched).
    - When ``universe`` is provided, sets ``backtest.universes =
      [universe]``, tags every run with ``universe.key`` (without
      overwriting an existing tag) and regenerates the per-universe
      summaries.
    - Sets ``backtest.anchor_algorithm_id`` when provided (lineage
      edge to the in-sample winner this OOS run derives from).

    Pure mutation, no I/O.
    """
    if study_name is not None:
        _ds = backtest.get_study()
        if _ds and _ds.name != study_name:
            backtest.rename_study(_ds.name, study_name)
    if study_description is not None:
        _ds = backtest.get_study()
        if _ds:
            _ds.description = study_description
    if universe is not None:
        backtest.universes = [universe]
        backtest.tag_runs_universe(universe.key, overwrite=False)
        backtest.regenerate_summaries_by_universe()
    if anchor_algorithm_id is not None:
        backtest.anchor_algorithm_id = anchor_algorithm_id


def stamp_backtests(
    backtests: Iterable[Backtest],
    *,
    study_name: Optional[str] = None,
    study_description: Optional[str] = None,
    universe_map: Optional[Dict[str, Universe]] = None,
    anchor_algorithm_id: Optional[str] = None,
) -> None:
    """Apply :func:`stamp_backtest` to every backtest in an iterable.

    ``universe_map`` is keyed by ``algorithm_id``. Backtests whose id
    is not in the map are stamped with ``universe=None`` (study fields
    only). ``anchor_algorithm_id`` is applied uniformly to every
    backtest in the iterable.
    """
    if (
        study_name is None
        and study_description is None
        and not universe_map
        and anchor_algorithm_id is None
    ):
        return
    for bt in backtests:
        u = universe_map.get(bt.algorithm_id) if universe_map else None
        stamp_backtest(
            bt,
            study_name=study_name,
            study_description=study_description,
            universe=u,
            anchor_algorithm_id=anchor_algorithm_id,
        )
