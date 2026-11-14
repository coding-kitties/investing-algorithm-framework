"""ApplyRiskBudgetPhase — proportionally scale *long-open* and
*scale-in* intents when their combined quote-currency notional
exceeds the portfolio's unallocated cash.

Closing intents (CLOSE_LONG, CLOSE_SHORT, SCALE_OUT) and short
opens are not scaled here — closes must always be free to fire, and
short opens credit cash rather than debit it. This mirrors the
legacy ``run_strategy``'s "Phase 2" cash check, which only ran over
``pending_buy_orders``.

If the strategy declares :class:`~investing_algorithm_framework.
domain.models.risk_rules.exposure_rule.ExposureRule`, this phase
also enforces it: cash-consuming intents are scaled down (or dropped)
to keep total invested value within
``exposure_rule.max_portfolio_percentage`` of the portfolio, on top
of the plain available-cash check.
"""
from __future__ import annotations

import logging
from typing import List

from investing_algorithm_framework.domain.models.signal import SignalSide

from .base import StrategyPhase
from .phase_state import PhaseState, SizedIntent

logger = logging.getLogger(__name__)


# Sides that *consume* unallocated cash and therefore participate
# in the risk-budget scaling pass.
_CASH_CONSUMING = frozenset({SignalSide.OPEN_LONG, SignalSide.SCALE_IN})


class ApplyRiskBudgetPhase(StrategyPhase):
    """Phase 4 — proportionally scale cash-consuming intents to
    fit ``context.get_unallocated()``.

    When :pyattr:`Signal.strength` differs across opens (set
    explicitly by the user or by a pipeline factor),
    :class:`SizePositionsPhase` has already ordered opens by
    strength descending. This phase therefore keeps stronger
    signals at fuller size when the scaling factor bites.

    Below a minimum execution amount of ``0.01`` quote currency the
    intent is dropped with a warning — mirrors today's
    ``Skipping buy order for ...: amount too small after scaling``
    behaviour, but here we drop earlier so the executor never sees
    sub-dust intents.
    """

    name = "apply_risk_budget"

    #: Minimum quote-currency notional below which a scaled intent
    #: is dropped instead of emitted.
    min_quote_notional: float = 0.01

    def run(self, state: PhaseState) -> None:
        if not state.sized_intents:
            return

        consuming = [
            it for it in state.sized_intents
            if it.side in _CASH_CONSUMING
        ]
        if not consuming:
            return

        available = state.context.get_unallocated()

        # An ExposureRule caps total invested value portfolio-wide
        # (e.g. "never more than 80% invested") on top of the plain
        # available-cash check below — tighten `available` to
        # whatever headroom remains under the cap before scaling.
        exposure_rule = getattr(state.strategy, "exposure_rule", None)
        if exposure_rule is not None:
            portfolio_value = state.context.get_portfolio_value()
            max_allocatable = exposure_rule.get_max_allocatable(
                portfolio_value
            )
            already_allocated = max(0.0, portfolio_value - available)
            exposure_budget = max(0.0, max_allocatable - already_allocated)
            if exposure_budget < available:
                logger.info(
                    "Exposure cap (%.0f%% of portfolio) limits new "
                    "allocation to %.2f (already invested %.2f of "
                    "%.2f portfolio value).",
                    exposure_rule.max_portfolio_percentage,
                    exposure_budget, already_allocated, portfolio_value,
                )
                state.trace(
                    "apply_risk_budget.exposure_budget", exposure_budget
                )
                available = exposure_budget

        total = sum(it.quote_amount for it in consuming)
        if total <= available or total <= 0:
            return  # nothing to scale

        scale_factor = available / total
        logger.warning(
            "Total allocation (%.2f) exceeds available funds (%.2f). "
            "Scaling all cash-consuming intents by %.2f%% to maintain "
            "proportional allocation.",
            total, available, scale_factor * 100,
        )
        state.trace("apply_risk_budget.scale_factor", scale_factor)

        scaled: List[SizedIntent] = []
        for it in state.sized_intents:
            if it.side not in _CASH_CONSUMING:
                scaled.append(it)
                continue
            new_intent = it.scaled(scale_factor)
            if new_intent.quote_amount <= self.min_quote_notional:
                logger.warning(
                    "Skipping %s for %s: amount too small after "
                    "scaling (%.4f)",
                    it.side.value, it.symbol, new_intent.quote_amount,
                )
                state.trace("apply_risk_budget.dropped_dust", new_intent)
                continue
            scaled.append(new_intent)

        state.sized_intents = scaled
