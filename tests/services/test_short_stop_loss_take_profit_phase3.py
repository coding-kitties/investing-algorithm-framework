"""#434 phase 3 — SL/TP inversion for SHORT trades.

Covers:
- ``TradeStopLoss`` math/trigger inversion for ``is_short=True``.
- ``TradeTakeProfit`` math/trigger inversion for ``is_short=True``.
- ``trade_service.add_stop_loss`` / ``add_take_profit`` copy
  ``trade.is_short`` onto the SL/TP record.
- SL/TP triggers on an open SHORT trade emit a COVER order (not
  a SELL) and close the right trade with realized P&L.
- Pending SL/TP attached to a SHORT order are materialized onto
  the resulting short trade at fill time.
"""

import unittest

from investing_algorithm_framework import (
    PortfolioConfiguration,
    MarketCredential,
    OrderStatus,
    TradeStatus,
)
from investing_algorithm_framework.domain import (
    OrderSide,
    TradeStopLoss,
    TradeTakeProfit,
)
from tests.resources import TestBase


class TestShortStopLossDomain(unittest.TestCase):
    """Pure-domain math/trigger tests on TradeStopLoss."""

    def test_short_fixed_stop_loss_price(self):
        sl = TradeStopLoss(
            trade_id=1,
            percentage=5,
            open_price=100,
            total_amount_trade=10,
            is_short=True,
        )
        # Short: SL sits ABOVE entry — losses come from price rising.
        self.assertEqual(105, sl.stop_loss_price)

    def test_short_fixed_stop_loss_triggers_on_rise(self):
        sl = TradeStopLoss(
            trade_id=1,
            percentage=5,
            open_price=100,
            total_amount_trade=10,
            is_short=True,
        )
        self.assertFalse(sl.has_triggered(104))
        self.assertTrue(sl.has_triggered(105))
        self.assertTrue(sl.has_triggered(110))

    def test_short_trailing_stop_loss_follows_price_down(self):
        sl = TradeStopLoss(
            trade_id=1,
            percentage=10,
            open_price=100,
            total_amount_trade=10,
            trailing=True,
            is_short=True,
        )
        # Initial trailing SL: 100 * 1.10 = 110.
        self.assertAlmostEqual(110, sl.stop_loss_price)

        # Price drops to 90 → low water mark moves; SL tightens to 99.
        sl.update_with_last_reported_price(90, None)
        self.assertEqual(90, sl.high_water_mark)
        self.assertAlmostEqual(99, sl.stop_loss_price)

        # A small uptick to 95 does NOT trigger.
        self.assertFalse(sl.has_triggered(95))

        # A rebound past the trailing SL DOES trigger.
        self.assertTrue(sl.has_triggered(99.5))


class TestShortTakeProfitDomain(unittest.TestCase):

    def test_short_fixed_take_profit_price(self):
        tp = TradeTakeProfit(
            trade_id=1,
            percentage=5,
            open_price=100,
            total_amount_trade=10,
            is_short=True,
        )
        # Short: TP sits BELOW entry — profit comes from price dropping.
        self.assertEqual(95, tp.take_profit_price)

    def test_short_fixed_take_profit_triggers_on_drop(self):
        tp = TradeTakeProfit(
            trade_id=1,
            percentage=5,
            open_price=100,
            total_amount_trade=10,
            is_short=True,
        )
        self.assertFalse(tp.has_triggered(96))
        self.assertTrue(tp.has_triggered(95))
        self.assertTrue(tp.has_triggered(90))

    def test_short_trailing_take_profit_arms_then_triggers_on_rebound(self):
        tp = TradeTakeProfit(
            trade_id=1,
            percentage=5,
            open_price=100,
            total_amount_trade=10,
            trailing=True,
            is_short=True,
        )
        # Not yet armed.
        self.assertIsNone(tp.take_profit_price)
        # Below the initial threshold (100 * 0.95 = 95) arms it.
        self.assertFalse(tp.has_triggered(94))
        self.assertEqual(94, tp.high_water_mark)
        # Trailing TP for shorts sits 5% ABOVE the low water mark.
        self.assertAlmostEqual(94 * 1.05, tp.take_profit_price)

        # Further drop tightens the TP (closer to current price).
        tp.update_with_last_reported_price(90, None)
        self.assertEqual(90, tp.high_water_mark)
        self.assertAlmostEqual(90 * 1.05, tp.take_profit_price)

        # A small rebound that stays below TP does not trigger.
        self.assertFalse(tp.has_triggered(93))
        # A rebound above the TP triggers.
        self.assertTrue(tp.has_triggered(95))


class TestShortRiskRuleIntegration(TestBase):
    """Integration: add_stop_loss / add_take_profit on a SHORT
    trade persist ``is_short=True``, and triggers emit COVER orders.
    """

    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 1000}

    def _open_short_trade(self, amount=100, price=10):
        order = self.app.context.create_short_order(
            target_symbol="ADA",
            price=price,
            amount=amount,
        )
        order_service = self.app.container.order_service()
        order_service.update(
            order.id,
            {
                "filled": amount,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )
        trade_service = self.app.container.trade_service()
        # Return the most recently opened short trade for the symbol.
        trades = trade_service.get_all({"target_symbol": "ADA"})
        return sorted(trades, key=lambda t: t.opened_at)[-1]

    def test_add_stop_loss_to_short_trade_persists_is_short(self):
        trade = self._open_short_trade()
        trade_service = self.app.container.trade_service()
        sl = trade_service.add_stop_loss(
            trade=trade, percentage=5, trailing=False,
        )
        self.assertTrue(sl.is_short)
        # SL sits above the entry.
        self.assertEqual(10.5, sl.stop_loss_price)

    def test_add_take_profit_to_short_trade_persists_is_short(self):
        trade = self._open_short_trade()
        trade_service = self.app.container.trade_service()
        tp = trade_service.add_take_profit(
            trade=trade, percentage=20, trailing=False,
        )
        self.assertTrue(tp.is_short)
        # TP sits below the entry.
        self.assertEqual(8, tp.take_profit_price)

    def test_short_stop_loss_trigger_emits_cover_order(self):
        trade = self._open_short_trade()
        trade_service = self.app.container.trade_service()
        trade_service.add_stop_loss(
            trade=trade, percentage=10, trailing=False,
        )
        # Push the last reported price above the SL trigger (11).
        from datetime import datetime, timezone
        trade.last_reported_price = 12
        trade.last_reported_price_datetime = datetime.now(tz=timezone.utc)
        trade_service.save(trade)

        triggered = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(1, len(triggered))
        self.assertEqual(OrderSide.COVER.value, triggered[0]["order_side"])
        self.assertEqual(100, triggered[0]["amount"])
        self.assertEqual(trade.id, triggered[0]["trades"][0]["trade_id"])

    def test_short_take_profit_trigger_emits_cover_order(self):
        trade = self._open_short_trade()
        trade_service = self.app.container.trade_service()
        trade_service.add_take_profit(
            trade=trade, percentage=20, trailing=False,
        )
        from datetime import datetime, timezone
        trade.last_reported_price = 7
        trade.last_reported_price_datetime = datetime.now(tz=timezone.utc)
        trade_service.save(trade)

        triggered = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(1, len(triggered))
        self.assertEqual(OrderSide.COVER.value, triggered[0]["order_side"])
        self.assertEqual(100, triggered[0]["amount"])

    def test_pending_stop_loss_on_short_order_materializes_at_fill(self):
        # Create a SHORT order, attach a pending SL spec to it
        # before the simulated fill, then fill it. The trade
        # materialized by the fill handler should carry the SL
        # with ``is_short=True``.
        order = self.app.context.create_short_order(
            target_symbol="ADA",
            price=10,
            amount=100,
        )
        trade_service = self.app.container.trade_service()
        trade_service.add_stop_loss(
            order=order, percentage=5, trailing=False,
        )

        order_service = self.app.container.order_service()
        order_service.update(
            order.id,
            {
                "filled": 100,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        trades = trade_service.get_all({"target_symbol": "ADA"})
        self.assertEqual(1, len(trades))
        trade = trades[0]
        self.assertTrue(trade.is_short)
        self.assertEqual(1, len(trade.stop_losses))
        sl = trade.stop_losses[0]
        self.assertTrue(sl.is_short)
        self.assertEqual(10.5, sl.stop_loss_price)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)

    def test_cover_fill_with_trade_allocation_closes_targeted_trade(self):
        # Open two short trades; SL/TP-style targeted cover should
        # close the specifically targeted one even if it isn't FIFO.
        trade_a = self._open_short_trade(amount=50, price=10)
        trade_b = self._open_short_trade(amount=50, price=12)

        # Manually drive the triggered-order path: build the COVER
        # order data with explicit ``trades`` allocation pointing at
        # trade_b (the NEWER one).
        position_service = self.app.container.position_service()
        portfolio = self.app.container.portfolio_service().get(1)
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        order_service = self.app.container.order_service()
        cover_data = {
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 50,
            "price": 9,
            "order_type": "LIMIT",
            "order_side": OrderSide.COVER.value,
            "portfolio_id": position.portfolio_id,
            "status": OrderStatus.CREATED.value,
            "trades": [{"trade_id": trade_b.id, "amount": 50}],
        }
        cover_order = order_service.create(cover_data)
        order_service.update(
            cover_order.id,
            {
                "filled": 50,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        trade_service = self.app.container.trade_service()
        trade_a_after = trade_service.get(trade_a.id)
        trade_b_after = trade_service.get(trade_b.id)
        self.assertEqual(TradeStatus.OPEN.value, trade_a_after.status)
        self.assertEqual(TradeStatus.CLOSED.value, trade_b_after.status)
        # Realized P&L on trade_b: (12 - 9) * 50 = 150.
        self.assertEqual(150, trade_b_after.net_gain)
