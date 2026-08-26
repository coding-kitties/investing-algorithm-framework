"""AttachRiskRulesPhase — attach :class:`StopLossRule` /
:class:`TakeProfitRule` to freshly-emitted opening orders.

Mirrors the SL/TP attachment that used to be inlined in the
legacy ``run_strategy`` Phase-3 and Phase-5 blocks: when an
opening order has been emitted for a symbol with a configured
rule, the rule's parameters are pushed onto the order via
:py:meth:`Context.add_stop_loss` / :py:meth:`Context.add_take_profit`
(the ``order=`` branch). The framework's trade-creation path then
materialises the rule onto every trade produced at fill time
(see ``orders.md`` §8 and ``trades.md`` §5).

Note: the v9.0 design extends this to ``OPEN_SHORT`` orders too,
matching the existing short-side behaviour in legacy
``run_strategy`` (rules are propagated with ``is_short=True``).
``SCALE_IN`` orders also receive SL/TP — each scale-in fill creates
its own trade with its own rule, mirroring legacy behaviour.
"""
from __future__ import annotations

import logging

from investing_algorithm_framework.domain import PositionMode
from investing_algorithm_framework.domain.models.signal import SignalSide

from .base import StrategyPhase
from .phase_state import PhaseState

logger = logging.getLogger(__name__)


# Sides that *open* (or add to) a position — these are the only
# ones that benefit from an attached SL/TP rule.
_OPENING_SIDES = frozenset({
    SignalSide.OPEN_LONG,
    SignalSide.SCALE_IN,
    SignalSide.OPEN_SHORT,
})


class AttachRiskRulesPhase(StrategyPhase):
    """Phase 6 — attach SL/TP to opening orders."""

    name = "attach_risk_rules"

    def run(self, state: PhaseState) -> None:
        if not state.emitted_orders:
            return

        strategy = state.strategy
        index_datetime = state.current_datetime

        for emitted in state.emitted_orders:
            if emitted.side not in _OPENING_SIDES:
                continue

            symbol = emitted.symbol
            order = emitted.order
            position_side = (
                "short" if emitted.side is SignalSide.OPEN_SHORT else "long"
            )
            if state.position_mode == PositionMode.HEDGE:
                sl_rule = strategy.get_stop_loss_rule(symbol, position_side)
                tp_rule = strategy.get_take_profit_rule(symbol, position_side)
            else:
                sl_rule = strategy.get_stop_loss_rule(symbol)
                tp_rule = strategy.get_take_profit_rule(symbol)

            if sl_rule is not None:
                try:
                    state.context.add_stop_loss(
                        order=order,
                        percentage=sl_rule.percentage_threshold,
                        trailing=sl_rule.trailing,
                        sell_percentage=sl_rule.sell_percentage,
                        created_at=index_datetime,
                    )
                except Exception as exc:  # pragma: no cover
                    logger.exception(
                        "Failed to attach stop-loss to order %r: %s",
                        order, exc,
                    )

            if tp_rule is not None:
                try:
                    state.context.add_take_profit(
                        order=order,
                        percentage=tp_rule.percentage_threshold,
                        trailing=tp_rule.trailing,
                        sell_percentage=tp_rule.sell_percentage,
                        created_at=index_datetime,
                    )
                except Exception as exc:  # pragma: no cover
                    logger.exception(
                        "Failed to attach take-profit to order %r: %s",
                        order, exc,
                    )
