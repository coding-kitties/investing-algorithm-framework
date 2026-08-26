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

from investing_algorithm_framework.domain.models.order import OrderType
from investing_algorithm_framework.services.strategy_phases import phase_state

from .base import Executor


class MarketOrderExecutor(Executor):
    """Place market orders for every intent."""

    short_order_type: OrderType = OrderType.MARKET

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
        )
