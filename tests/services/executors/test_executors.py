"""Executor unit tests — verify per-side routing for the v9.0
:class:`LimitOrderExecutor` / :class:`MarketOrderExecutor`.

These tests are pure-Python and use minimal stub contexts; the
parity test against the legacy ``run_strategy`` lives in
``tests/app/strategy/test_pipeline_parity.py`` (added in Turn 8).
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework import Signal, SignalSide
from investing_algorithm_framework.domain.models.order import (
    OrderSide,
    OrderType,
)
from investing_algorithm_framework.services.executors import (
    Executor,
    LimitOrderExecutor,
    MarketOrderExecutor,
)
from investing_algorithm_framework.services.strategy_phases import (
    SizedIntent,
)


class _RecordingContext:
    """Tiny stand-in for :class:`Context` that records every order
    call so we can assert routing decisions."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def _record(self, route: str, **kwargs):
        kwargs["__route__"] = route
        self.calls.append(kwargs)
        order = MagicMock(name=route)
        order.kwargs = kwargs
        return order

    def create_limit_order(self, **kwargs):
        return self._record("limit", **kwargs)

    def create_market_order(self, **kwargs):
        return self._record("market", **kwargs)

    def create_short_order(self, **kwargs):
        return self._record("short", **kwargs)

    def create_cover_order(self, **kwargs):
        return self._record("cover", **kwargs)


def _intent(side: SignalSide, *, symbol="BTC", amount=1.0, price=100.0):
    return SizedIntent(
        signal=Signal(symbol, side, source="ema"),
        amount=amount,
        price=price,
        quote_amount=amount * price,
        full_symbol=f"{symbol}/EUR",
        order_reason=side.value,
    )


# --------------------------------------------------------------------- #
# LimitOrderExecutor
# --------------------------------------------------------------------- #
class TestLimitOrderExecutor(TestCase):

    def setUp(self) -> None:
        self.ctx = _RecordingContext()
        self.exec = LimitOrderExecutor()
        self.meta = {"order_reason": "buy_signal"}

    def test_open_long_routes_limit_buy(self):
        self.exec.execute(_intent(SignalSide.OPEN_LONG), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "limit")
        self.assertEqual(call["order_side"], OrderSide.BUY)
        self.assertEqual(call["amount"], 1.0)
        self.assertEqual(call["price"], 100.0)
        self.assertTrue(call["execute"])
        self.assertTrue(call["validate"])
        self.assertTrue(call["sync"])

    def test_scale_in_routes_limit_buy(self):
        self.exec.execute(_intent(SignalSide.SCALE_IN), self.ctx, self.meta)
        self.assertEqual(self.ctx.calls[0]["order_side"], OrderSide.BUY)

    def test_close_long_routes_limit_sell(self):
        self.exec.execute(_intent(SignalSide.CLOSE_LONG), self.ctx, self.meta)
        self.assertEqual(self.ctx.calls[0]["order_side"], OrderSide.SELL)

    def test_scale_out_routes_limit_sell(self):
        self.exec.execute(_intent(SignalSide.SCALE_OUT), self.ctx, self.meta)
        self.assertEqual(self.ctx.calls[0]["order_side"], OrderSide.SELL)

    def test_open_short_routes_via_create_short_order_with_limit(self):
        self.exec.execute(_intent(SignalSide.OPEN_SHORT), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "short")
        self.assertIs(call["order_type"], OrderType.LIMIT)

    def test_close_short_routes_via_create_cover_order_with_limit(self):
        self.exec.execute(_intent(SignalSide.CLOSE_SHORT), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "cover")
        self.assertIs(call["order_type"], OrderType.LIMIT)

    def test_metadata_passed_through(self):
        meta = {"order_reason": "buy_signal", "signal_source": "ema"}
        self.exec.execute(_intent(SignalSide.OPEN_LONG), self.ctx, meta)
        self.assertEqual(self.ctx.calls[0]["metadata"], meta)


# --------------------------------------------------------------------- #
# MarketOrderExecutor
# --------------------------------------------------------------------- #
class TestMarketOrderExecutor(TestCase):

    def setUp(self) -> None:
        self.ctx = _RecordingContext()
        self.exec = MarketOrderExecutor()
        self.meta = {"order_reason": "buy_signal"}

    def test_open_long_routes_market_buy(self):
        self.exec.execute(_intent(SignalSide.OPEN_LONG), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "market")
        self.assertEqual(call["order_side"], OrderSide.BUY)
        # Market orders don't carry a price.
        self.assertNotIn("price", call)

    def test_close_long_routes_market_sell(self):
        self.exec.execute(_intent(SignalSide.CLOSE_LONG), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "market")
        self.assertEqual(call["order_side"], OrderSide.SELL)

    def test_open_short_routes_via_create_short_order_with_market(self):
        self.exec.execute(_intent(SignalSide.OPEN_SHORT), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "short")
        self.assertIs(call["order_type"], OrderType.MARKET)

    def test_close_short_routes_via_create_cover_order_with_market(self):
        self.exec.execute(_intent(SignalSide.CLOSE_SHORT), self.ctx, self.meta)
        call = self.ctx.calls[0]
        self.assertEqual(call["__route__"], "cover")
        self.assertIs(call["order_type"], OrderType.MARKET)


# --------------------------------------------------------------------- #
# Custom subclass — verify the dispatch contract
# --------------------------------------------------------------------- #
class TestCustomExecutor(TestCase):
    """A user-defined :class:`Executor` only needs to override
    ``_long_buy`` / ``_long_sell``. Short routes default to
    ``create_short_order`` / ``create_cover_order`` with the
    configured ``short_order_type``."""

    def test_subclass_with_market_short_only(self):
        class BuyLimitShortMarket(Executor):
            short_order_type = OrderType.MARKET

            def _long_buy(self, intent, context, metadata):
                return context.create_limit_order(
                    target_symbol=intent.symbol,
                    order_side=OrderSide.BUY,
                    amount=intent.amount,
                    price=intent.price,
                    execute=True, validate=True, sync=True,
                    metadata=metadata,
                )

            def _long_sell(self, intent, context, metadata):
                return context.create_limit_order(
                    target_symbol=intent.symbol,
                    order_side=OrderSide.SELL,
                    amount=intent.amount,
                    price=intent.price,
                    execute=True, validate=True, sync=True,
                    metadata=metadata,
                )

        ctx = _RecordingContext()
        ex = BuyLimitShortMarket()
        ex.execute(_intent(SignalSide.OPEN_LONG), ctx, {})
        ex.execute(_intent(SignalSide.OPEN_SHORT), ctx, {})

        self.assertEqual(ctx.calls[0]["__route__"], "limit")
        self.assertEqual(ctx.calls[1]["__route__"], "short")
        self.assertIs(ctx.calls[1]["order_type"], OrderType.MARKET)
