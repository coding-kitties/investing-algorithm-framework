"""EvaluatePipelinesPhase — Phase 0 of the v9.0 phase pipeline.

Computes any
:class:`~investing_algorithm_framework.domain.pipeline.pipeline.Pipeline`
subclasses attached to the strategy via the ``pipelines`` class
attribute and injects each output frame into :pyattr:`PhaseState.data`
under the key ``pipeline_cls.__name__``. Runs *before*
:class:`CollectSignalsPhase` so the strategy's ``generate_signals``
and any :py:meth:`Pipeline.to_signals` hooks see the materialised
factor frames.

Lifts the responsibility out of
``_EventLoopService._run_pipelines`` so the eventloop no longer
contains strategy-shaped logic; everything that happens for one
strategy on one tick is now expressed as an ordered sequence of
phases.

Features preserved from the legacy eventloop implementation:

* **Universe-refresh cache** — pipelines that declare a
  :pyattr:`Pipeline.refresh_universe_every` cadence reuse the last
  surviving symbol set within the cadence window. The cache is
  per-strategy state stored on ``strategy._pipeline_universe_cache``.
* **Live-mode resilience** — in non-backtest environments a single
  pipeline failure is logged and the iteration continues with an
  empty output frame, so one bad pipeline cannot kill live trading.
  Backtests still raise.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Type

from investing_algorithm_framework.domain import (
    ENVIRONMENT, DataType, Environment,
)

from .base import StrategyPhase
from .phase_state import PhaseState

logger = logging.getLogger(__name__)


class EvaluatePipelinesPhase(StrategyPhase):
    """Materialise the strategy's cross-sectional pipelines.

    For each pipeline class listed on ``strategy.pipelines``:

    1. Build a ``symbol → data_source_identifier`` mapping from the
       strategy's OHLCV data sources (first match wins per symbol).
    2. If the pipeline declares ``refresh_universe_every`` and we
       have an unexpired cached surviving symbol set, restrict the
       mapping to those symbols and skip the universe filter pass.
    3. Hand the mapping and ``PhaseState.data`` (the per-strategy
       data slice — sufficient because the mapping only references
       identifiers the strategy itself declared) to
       :class:`PipelineEngine`.
    4. Inject the resulting long-form ``polars.DataFrame`` into
       ``state.data[pipeline_cls.__name__]`` so downstream phases
       and ``generate_signals`` can read it.

    Strategies without ``pipelines`` skip the phase entirely (zero
    cost beyond a single ``getattr``).
    """

    name = "evaluate_pipelines"

    def __init__(self, engine: Optional[object] = None) -> None:
        # Lazy import to keep the strategy-phases package import-light;
        # ``PipelineEngine`` pulls in polars.
        if engine is None:
            from investing_algorithm_framework.services.pipeline import (
                PipelineEngine,
            )
            engine = PipelineEngine()
        self._engine = engine

    # ---- entry point ---------------------------------------------- #
    def run(self, state: PhaseState) -> None:
        strategy = state.strategy
        pipelines = getattr(strategy, "pipelines", None)
        if not pipelines:
            return

        symbol_to_identifier = self._build_symbol_to_identifier(strategy)
        if not symbol_to_identifier:
            logger.warning(
                "Strategy %s declares pipelines but has no OHLCV data "
                "sources to feed them; pipelines will be skipped.",
                strategy.strategy_id,
            )
            return

        as_of = state.current_datetime
        is_backtest = self._is_backtest(state)

        # Per-strategy universe cache. Created lazily so users that
        # do not use refresh_universe_every pay nothing.
        if not hasattr(strategy, "_pipeline_universe_cache"):
            strategy._pipeline_universe_cache = {}

        for pipeline_cls in pipelines:
            cached_mapping = self._filter_for_universe_cache(
                strategy=strategy,
                pipeline_cls=pipeline_cls,
                symbol_to_identifier=symbol_to_identifier,
                as_of=as_of,
            )
            mapping = (
                cached_mapping
                if cached_mapping is not None
                else symbol_to_identifier
            )

            try:
                output = self._engine.evaluate(
                    pipeline_cls=pipeline_cls,
                    data_object=state.data,
                    symbol_to_identifier=mapping,
                    as_of=as_of,
                )
            except Exception:
                logger.exception(
                    "Pipeline %s failed during evaluation at %s",
                    pipeline_cls.__name__,
                    as_of,
                )
                if is_backtest:
                    raise
                output = self._engine._empty_output(pipeline_cls)

            # Refresh the universe cache when we just did a full
            # evaluation (no cache hit) and the pipeline declares a
            # cadence.
            cadence: Optional[timedelta] = getattr(
                pipeline_cls, "refresh_universe_every", None
            )
            if (
                cadence is not None
                and cadence > timedelta(0)
                and cached_mapping is None
                and "symbol" in output.columns
            ):
                surviving = frozenset(output["symbol"].to_list())
                strategy._pipeline_universe_cache[pipeline_cls] = (
                    as_of, surviving,
                )

            state.data[pipeline_cls.__name__] = output

        state.trace("evaluate_pipelines.count", len(pipelines))

    # ---- helpers --------------------------------------------------- #
    @staticmethod
    def _build_symbol_to_identifier(strategy) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for ds in strategy.data_sources or []:
            if not DataType.OHLCV.equals(ds.data_type):
                continue
            if ds.symbol is None or ds.symbol in mapping:
                continue
            mapping[ds.symbol] = ds.get_identifier()
        return mapping

    @staticmethod
    def _is_backtest(state: PhaseState) -> bool:
        try:
            env = state.context.config[ENVIRONMENT]
        except Exception:  # pragma: no cover - defensive
            return False
        return Environment.BACKTEST.equals(env)

    @staticmethod
    def _filter_for_universe_cache(
        strategy,
        pipeline_cls: Type,
        symbol_to_identifier: Dict[str, str],
        as_of: datetime,
    ) -> Optional[Dict[str, str]]:
        cadence: Optional[timedelta] = getattr(
            pipeline_cls, "refresh_universe_every", None
        )
        if cadence is None or cadence <= timedelta(0):
            return None

        cache = getattr(strategy, "_pipeline_universe_cache", None)
        if not cache:
            return None
        cached = cache.get(pipeline_cls)
        if cached is None:
            return None

        last_refresh, symbols = cached
        # Normalise tz so naive backtest datetimes and aware live
        # datetimes compare cleanly.
        if last_refresh.tzinfo is None and as_of.tzinfo is not None:
            cmp_as_of = as_of.replace(tzinfo=None)
        elif last_refresh.tzinfo is not None and as_of.tzinfo is None:
            cmp_as_of = as_of.replace(tzinfo=last_refresh.tzinfo)
        else:
            cmp_as_of = as_of
        if cmp_as_of - last_refresh >= cadence:
            return None  # cadence elapsed → full refresh

        return {
            sym: ident
            for sym, ident in symbol_to_identifier.items()
            if sym in symbols
        }
