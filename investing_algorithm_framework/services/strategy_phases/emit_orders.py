"""EmitOrdersPhase — turn each :class:`SizedIntent` into an
:class:`Order` by delegating to the strategy's :class:`Executor`.

The executor is read from ``state.strategy.executor``. When unset
(``None``) the phase falls back to
:class:`~investing_algorithm_framework.services.executors.LimitOrderExecutor`
— the v9.0 default that preserves legacy ``run_strategy``
behaviour (limit orders pegged at the signal-bar price).

The phase itself is dispatch-free: routing decisions live in the
executor so user code can swap behaviours (LIMIT / MARKET /
bracket / OCO / iceberg) without touching the pipeline.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .base import StrategyPhase
from .phase_state import EmittedOrder, PhaseState, SizedIntent

logger = logging.getLogger(__name__)


class EmitOrdersPhase(StrategyPhase):
    """Phase 5 — emit one order per :class:`SizedIntent`."""

    name = "emit_orders"

    def run(self, state: PhaseState) -> None:
        if not state.sized_intents:
            return

        executor = self._resolve_executor(state)

        for intent in state.sized_intents:
            metadata = self._build_metadata(intent)
            try:
                order = executor.execute(intent, state.context, metadata)
            except Exception as exc:  # pragma: no cover - executor errors
                logger.exception(
                    "Order emission failed for intent %r: %s",
                    intent, exc,
                )
                state.trace("emit_orders.error", (intent, repr(exc)))
                continue

            if order is None:
                state.trace("emit_orders.declined", intent)
                continue

            state.emitted_orders.append(
                EmittedOrder(intent=intent, order=order),
            )

        state.trace("emit_orders.count", len(state.emitted_orders))

    # ---- helpers --------------------------------------------------- #
    @staticmethod
    def _resolve_executor(state: PhaseState):
        executor = getattr(state.strategy, "executor", None)
        if executor is None:
            # Local import to avoid an import cycle at module load.
            from investing_algorithm_framework.services.executors import (
                LimitOrderExecutor,
            )
            executor = LimitOrderExecutor()
        return executor

    @staticmethod
    def _build_metadata(intent: SizedIntent) -> Dict[str, Any]:
        meta: Dict[str, Any] = {"order_reason": intent.order_reason}
        if intent.signal.source:
            meta["signal_source"] = intent.signal.source
        meta.update(intent.extra_metadata or {})
        return meta
