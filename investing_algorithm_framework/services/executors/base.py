"""Executor base class with side dispatch.

Concrete executors override :meth:`_long_buy` and :meth:`_long_sell`
to choose between LIMIT and MARKET order types for the long side.
Short / cover routing goes through :meth:`_short_open` /
:meth:`_short_close` which use a class-level
:pyattr:`short_order_type` to keep the limit/market split symmetric.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from investing_algorithm_framework.domain.models.order import (
    OrderSide,
    OrderType,
)
from investing_algorithm_framework.domain.models.signal import SignalSide
from investing_algorithm_framework.services.strategy_phases import phase_state


class Executor(ABC):
    """Abstract base for v9.0 order executors.

    Implementations must define :meth:`_long_buy` and
    :meth:`_long_sell` (long-side routing) and may override
    :pyattr:`short_order_type` to flip short/cover between LIMIT and
    MARKET. For fully custom routing (e.g. OCO, bracket, iceberg)
    override :meth:`execute` directly.
    """

    #: Order type used for SHORT / COVER routes when the default
    #: dispatcher is used. Subclasses may override.
    short_order_type: OrderType = OrderType.LIMIT

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def execute(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        """Dispatch *intent* to the appropriate broker call.

        Returns the created :class:`Order` (or ``None`` when the
        executor declines — e.g. zero amount). Exceptions propagate
        to :class:`EmitOrdersPhase` which records them as traces.
        """
        side = intent.side

        if side in (SignalSide.OPEN_LONG, SignalSide.SCALE_IN):
            return self._long_buy(intent, context, metadata)
        if side in (SignalSide.CLOSE_LONG, SignalSide.SCALE_OUT):
            return self._long_sell(intent, context, metadata)
        if side is SignalSide.OPEN_SHORT:
            return self._short_open(intent, context, metadata)
        if side is SignalSide.CLOSE_SHORT:
            return self._short_close(intent, context, metadata)
        return None  # pragma: no cover - exhaustive

    # ------------------------------------------------------------------
    # Long side — subclasses must implement
    # ------------------------------------------------------------------
    @abstractmethod
    def _long_buy(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        """Route an OPEN_LONG / SCALE_IN intent."""

    @abstractmethod
    def _long_sell(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        """Route a CLOSE_LONG / SCALE_OUT intent."""

    # ------------------------------------------------------------------
    # Short side — shared dispatcher; subclasses tune via
    # ``short_order_type`` or override entirely.
    # ------------------------------------------------------------------
    def _short_open(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        return context.create_short_order(
            target_symbol=intent.symbol,
            amount=intent.amount,
            price=intent.price,
            order_type=self.short_order_type,
            metadata=metadata,
        )

    def _short_close(
        self,
        intent: phase_state.SizedIntent,
        context: Any,
        metadata: Dict[str, Any],
    ) -> Optional[Any]:
        return context.create_cover_order(
            target_symbol=intent.symbol,
            amount=intent.amount,
            price=intent.price,
            order_type=self.short_order_type,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Helper for subclasses that need OrderSide constants without
    # re-importing
    # ------------------------------------------------------------------
    @staticmethod
    def _buy_side() -> OrderSide:
        return OrderSide.BUY

    @staticmethod
    def _sell_side() -> OrderSide:
        return OrderSide.SELL
