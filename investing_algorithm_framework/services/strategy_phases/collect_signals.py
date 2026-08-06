"""CollectSignalsPhase — turn strategy & pipeline emissions into a
:class:`~investing_algorithm_framework.domain.models.signal.Signal`
list.

This phase is the entry point to the v9.0 pipeline. It performs the
per-iteration bookkeeping that used to live at the top of
``run_strategy`` (cooldown timer tick, bar-index advance), invokes
:py:meth:`TradingStrategy.generate_signals` to obtain the user-emitted
signal stream, and then merges in any signals emitted by pipelines
that override :py:meth:`Pipeline.to_signals` (#503).
"""
from __future__ import annotations

from typing import Iterable, List

from investing_algorithm_framework.domain.models.signal import Signal

from .base import StrategyPhase
from .phase_state import PhaseState


class CollectSignalsPhase(StrategyPhase):
    """Phase 1 — collect every :class:`Signal` the strategy wishes
    to emit this iteration.

    Side-effects performed on the parent :class:`TradingStrategy`:

    * Decrements ``_cooldown_remaining`` per symbol; drops keys at
      zero. (One-line port of the legacy "tick down cooldown
      counters" block.)
    * Increments ``_cooldown_bar_index`` and writes it to
      :pyattr:`PhaseState.bar_index`.

    Signal sources merged into :pyattr:`PhaseState.raw_signals`:

    1. :py:meth:`TradingStrategy.generate_signals` — the primary
       user-facing hook.
    2. :py:meth:`Pipeline.to_signals` for each pipeline class on
       ``strategy.pipelines`` that overrides the default empty
       implementation. The phase looks up each pipeline's evaluated
       frame in ``state.data[pipeline_cls.__name__]`` (injected by
       :class:`EvaluatePipelinesPhase`) and hands it to
       :meth:`to_signals` together with the strategy's context.

    User signals appear first in the merged list; pipeline signals
    follow in pipeline-declaration order. Order matters for
    :class:`ResolveConflictsPhase` when ``ConflictResolution.PRIORITY``
    is used.
    """

    name = "collect_signals"

    def run(self, state: PhaseState) -> None:
        strategy = state.strategy

        # Tick down cooldown counters for all symbols. Mirrors the
        # legacy implementation byte-for-byte so a strategy that
        # relies on the exact post-tick state still works.
        for symbol in list(strategy.symbols):
            if symbol in strategy._cooldown_remaining:
                strategy._cooldown_remaining[symbol] -= 1
                if strategy._cooldown_remaining[symbol] <= 0:
                    del strategy._cooldown_remaining[symbol]

        # Advance the bar index used by :class:`CooldownRule` /
        # :class:`CooldownTracker` evaluation. Each ``run_strategy``
        # call counts as one bar from the rule engine's point of
        # view, matching the legacy ``cooldown_in_bars`` model.
        strategy._cooldown_bar_index += 1
        state.bar_index = strategy._cooldown_bar_index

        # Drive the user-facing signal generator. The default
        # implementation on :class:`TradingStrategy` raises; user
        # subclasses must override (default-empty handling guards
        # against ``None`` returns from no-op overrides).
        emitted: Iterable[Signal] = (
            strategy.generate_signals(state.context, state.data) or ()
        )
        merged: List[Signal] = self._collect(emitted)

        # Phase 5 (#503): collect signals from any pipelines that
        # override Pipeline.to_signals. Pure factor pipelines (RSI,
        # SMA, ...) return the default empty iterable and add nothing.
        for pipeline_cls in getattr(strategy, "pipelines", None) or []:
            frame = state.data.get(pipeline_cls.__name__)
            if frame is None:
                continue
            instance = self._instantiate_pipeline(pipeline_cls)
            pipeline_signals = instance.to_signals(frame, state.context)
            for sig in self._collect(pipeline_signals or ()):
                merged.append(sig)

        state.raw_signals = merged
        state.trace("collect_signals.count", len(state.raw_signals))

    # ---- helpers --------------------------------------------------- #
    @staticmethod
    def _collect(emitted: Iterable[Signal]) -> List[Signal]:
        """Materialise the emitted iterable into a list, with a
        helpful error if a non-Signal slips in."""
        out: List[Signal] = []
        for item in emitted:
            if not isinstance(item, Signal):
                raise TypeError(
                    f"generate_signals / Pipeline.to_signals must yield "
                    f"Signal instances, got {type(item).__name__}: "
                    f"{item!r}"
                )
            out.append(item)
        return out

    @staticmethod
    def _instantiate_pipeline(pipeline_cls):
        """Return a (possibly cached) instance of the pipeline.

        Pipelines are declared as classes on
        ``TradingStrategy.pipelines``; ``to_signals`` is an instance
        method. We construct once per process and cache on the class
        so successive iterations do not pay the construction cost.
        """
        cache_attr = "_v9_signal_instance"
        instance = getattr(pipeline_cls, cache_attr, None)
        if instance is None:
            instance = pipeline_cls()
            setattr(pipeline_cls, cache_attr, instance)
        return instance
