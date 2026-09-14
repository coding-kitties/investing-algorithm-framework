"""Market-order executor.

Routes long-side intents through ``context.create_market_order``
(which estimates the order amount from the latest price and
reconciles at fill time) and short-side intents through
``create_short_order`` / ``create_cover_order`` with
``order_type=MARKET``.

Use this executor when you want fills at the next-bar open price
(with optional slippage) instead of resting limit orders at the
signal-bar close.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import replace

from investing_algorithm_framework.domain import (
    RoundingService, OperationalException,
)
from investing_algorithm_framework.domain.models.signal import SignalSide

from investing_algorithm_framework.domain.models.order import OrderType
from investing_algorithm_framework.services.strategy_phases import phase_state

from .base import Executor


class MarketOrderExecutor(Executor):
    """Place market orders for every intent.

    ``precision=0`` rounds amounts down to whole units and skips amounts
    below one unit. ``fill_at_current_open=True`` selects native immediate
    open execution for long-only event backtests. The data provider must
    expose completed history and only the current open, never future HLCV.
    Unfilled remainders are canceled on the same tick.
    """

    short_order_type: OrderType = OrderType.MARKET

    def __init__(self, *, precision=None, fill_at_current_open=False):
        if precision is not None and (
            type(precision) is not int or precision < 0
        ):
            raise ValueError("precision must be a nonnegative integer")
        self.precision = precision
        self.fill_at_current_open = fill_at_current_open

    def execute(self, intent, context, metadata):
        if self.fill_at_current_open and intent.side in (
            SignalSide.OPEN_SHORT, SignalSide.CLOSE_SHORT,
        ):
            raise OperationalException(
                "Current-open execution supports long orders only"
            )
        if self.precision is not None:
            metadata = dict(metadata)
            metadata["amount_precision"] = self.precision
            amount = RoundingService.round_down(intent.amount, self.precision)
            if amount <= 0:
                return None
            intent = replace(
                intent, amount=amount, quote_amount=amount * intent.price
            )
        return super().execute(intent, context, metadata)

    def _long_buy(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        return context.create_market_order(
            target_symbol=intent.symbol,
            order_side=self._buy_side(),
            amount=intent.amount,
            execute=True,
            validate=not metadata.get("synthetic_flip_open", False),
            sync=True,
            metadata=metadata,
            fill_at_current_open=self.fill_at_current_open,
        )

    def _long_sell(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        return context.create_market_order(
            target_symbol=intent.symbol,
            order_side=self._sell_side(),
            amount=intent.amount,
            execute=True,
            validate=True,
            sync=True,
            metadata=metadata,
            fill_at_current_open=self.fill_at_current_open,
        )
