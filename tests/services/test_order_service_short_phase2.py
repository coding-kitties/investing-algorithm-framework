"""Tests for #434 phase 2 \u2014 SHORT / COVER event-engine sync.

Covers the full execute=True / sync=True lifecycle:

- SHORT order creation reserves collateral on the trading-symbol
  position and on portfolio unallocated.
- SHORT fill drives the target position negative, credits proceeds
  back to unallocated, and creates an open ``is_short=True`` Trade.
- COVER order creation reserves cover cash.
- COVER fill moves the position back toward zero, debits the cover
  cost, realizes ``net_gain = (open_price - cover_fill) * amount``
  on the matched short trade, and closes it when fully covered.
- Cancellation / expiry / rejection on SHORT/COVER refunds the
  unfilled reservation \u2014 mirrors BUY refund semantics.
- Round-trip P&L: SHORT@10 \u2192 COVER@8 of 100 units leaves the
  portfolio with +200 EUR net (proceeds 1000 \u2212 cover cost 800).
"""

from investing_algorithm_framework import (
    PortfolioConfiguration,
    MarketCredential,
    OrderStatus,
    TradeStatus,
)
from investing_algorithm_framework.domain import OrderSide
from tests.resources import TestBase


class TestShortCoverLifecycle(TestBase):
    """End-to-end SHORT/COVER lifecycle with the default test
    executor (no auto-fill).
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

    # ------------------------------------------------------------------
    # SHORT creation \u2014 collateral reservation
    # ------------------------------------------------------------------

    def test_short_creation_reserves_collateral(self):
        # 100 units * 5 EUR = 500 collateral; unallocated 1000 \u2192 500.
        order = self.app.context.create_short_order(
            target_symbol="ADA",
            price=5,
            amount=100,
        )
        self.assertIsNotNone(order)
        self.assertTrue(OrderSide.SHORT.equals(order.get_order_side()))

        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(500, portfolio.get_unallocated())

        position_service = self.app.container.position_service()
        eur_position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "EUR"}
        )
        self.assertEqual(500, eur_position.get_amount())

        # Target position exists but is still zero \u2014 the short only
        # opens negative on fill.
        ada_position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        self.assertEqual(0, ada_position.get_amount() or 0)

    # ------------------------------------------------------------------
    # SHORT fill \u2014 position goes negative, proceeds credited
    # ------------------------------------------------------------------

    def test_short_fill_creates_open_short_trade(self):
        order = self.app.context.create_short_order(
            target_symbol="ADA",
            price=5,
            amount=100,
        )

        order_service = self.app.container.order_service()
        # Simulate full fill at the limit price.
        order_service.update(
            order.id,
            {
                "filled": 100,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        portfolio = self.app.container.portfolio_service().get(1)
        # Cash flow at fill: refund reservation (500) + credit
        # proceeds (500) = +1000 to unallocated. Net change from
        # creation \u2192 fill: +500 (proceeds added).
        self.assertEqual(1000 + 500, portfolio.get_unallocated())

        position_service = self.app.container.position_service()
        ada_position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        # Target position is now negative.
        self.assertEqual(-100, ada_position.get_amount())

        # A SHORT trade was created.
        trade_service = self.app.container.trade_service()
        trades = trade_service.get_all({"target_symbol": "ADA"})
        self.assertEqual(1, len(trades))
        trade = trades[0]
        self.assertTrue(trade.is_short)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(100, trade.amount)
        self.assertEqual(100, trade.available_amount)
        self.assertEqual(5, trade.open_price)

    # ------------------------------------------------------------------
    # COVER full round-trip \u2014 P&L realization
    # ------------------------------------------------------------------

    def test_short_then_cover_round_trip_realizes_pnl(self):
        # SHORT 100 @ 10  \u2192 proceeds 1000 added on fill.
        short_order = self.app.context.create_short_order(
            target_symbol="ADA",
            price=10,
            amount=100,
        )
        order_service = self.app.container.order_service()
        order_service.update(
            short_order.id,
            {
                "filled": 100,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        portfolio = self.app.container.portfolio_service().get(1)
        # Pre-cover: unallocated = 1000 (start) \u2212 1000 (reservation)
        #            + 1000 (refund) + 1000 (proceeds) = 2000.
        self.assertEqual(2000, portfolio.get_unallocated())

        # COVER 100 @ 8  \u2192 reserve 800, fill at 8, cost 800.
        cover_order = self.app.context.create_cover_order(
            target_symbol="ADA",
            price=8,
            amount=100,
        )
        # After COVER creation: unallocated 2000 \u2212 800 = 1200.
        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(1200, portfolio.get_unallocated())

        order_service.update(
            cover_order.id,
            {
                "filled": 100,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        portfolio = self.app.container.portfolio_service().get(1)
        # Post-cover-fill: refund reservation (+800) \u2212 cover cost
        # (\u22128 * 100 = \u2212800) \u2192 net 0 change at fill.
        # Total = 1200 + 0 = 1200. P&L = 1000 (proceeds) \u2212 800
        # (cover cost) = +200 relative to starting 1000.
        self.assertEqual(1200, portfolio.get_unallocated())

        # Position is back to flat.
        position_service = self.app.container.position_service()
        ada_position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        self.assertEqual(0, ada_position.get_amount())

        # The short trade is closed with realized P&L = (10 \u2212 8) * 100 = 200.
        trade_service = self.app.container.trade_service()
        trades = trade_service.get_all({"target_symbol": "ADA"})
        self.assertEqual(1, len(trades))
        trade = trades[0]
        self.assertTrue(trade.is_short)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(200, trade.net_gain)
        self.assertEqual(0, trade.available_amount)

    # ------------------------------------------------------------------
    # COVER realizes a LOSS when fill price is above entry
    # ------------------------------------------------------------------

    def test_short_then_cover_round_trip_realizes_loss(self):
        short_order = self.app.context.create_short_order(
            target_symbol="ADA", price=5, amount=100,
        )
        order_service = self.app.container.order_service()
        order_service.update(
            short_order.id,
            {
                "filled": 100, "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )
        # SHORT@5 fills: proceeds 500. unallocated = 1000 \u2212 500 + 500 +
        # 500 = 1500.

        cover_order = self.app.context.create_cover_order(
            target_symbol="ADA", price=7, amount=100,
        )
        # Reserve 700: unallocated = 1500 \u2212 700 = 800.
        order_service.update(
            cover_order.id,
            {
                "filled": 100, "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )
        # Cover fills at 7: refund 700, debit 700 \u2192 net 0. Final
        # unallocated = 800. P&L = 500 \u2212 700 = \u2212200.

        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(800, portfolio.get_unallocated())

        trade_service = self.app.container.trade_service()
        trades = trade_service.get_all({"target_symbol": "ADA"})
        trade = trades[0]
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(-200, trade.net_gain)

    # ------------------------------------------------------------------
    # Partial cover
    # ------------------------------------------------------------------

    def test_partial_cover_leaves_short_open(self):
        short_order = self.app.context.create_short_order(
            target_symbol="ADA", price=10, amount=100,
        )
        order_service = self.app.container.order_service()
        order_service.update(
            short_order.id,
            {
                "filled": 100, "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        cover_order = self.app.context.create_cover_order(
            target_symbol="ADA", price=8, amount=40,
        )
        order_service.update(
            cover_order.id,
            {
                "filled": 40, "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )

        position_service = self.app.container.position_service()
        portfolio = self.app.container.portfolio_service().get(1)
        ada_position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        # 100 short, 40 covered \u2192 60 still short.
        self.assertEqual(-60, ada_position.get_amount())

        trade_service = self.app.container.trade_service()
        trades = trade_service.get_all({"target_symbol": "ADA"})
        trade = trades[0]
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        # Partial realized P&L: (10 \u2212 8) * 40 = 80.
        self.assertEqual(80, trade.net_gain)
        self.assertEqual(60, trade.available_amount)


class TestShortCoverCancellation(TestBase):
    """Cancellation / rejection refund the unfilled reservation."""

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

    def test_short_cancellation_refunds_reservation(self):
        order = self.app.context.create_short_order(
            target_symbol="ADA", price=5, amount=100,
        )
        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(500, portfolio.get_unallocated())

        order_service = self.app.container.order_service()
        order_service.update(
            order.id, {"status": OrderStatus.CANCELED.value}
        )

        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(1000, portfolio.get_unallocated())

    def test_short_rejection_refunds_reservation(self):
        order = self.app.context.create_short_order(
            target_symbol="ADA", price=5, amount=100,
        )
        order_service = self.app.container.order_service()
        order_service.update(
            order.id, {"status": OrderStatus.REJECTED.value}
        )

        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(1000, portfolio.get_unallocated())

    def test_cover_cancellation_refunds_reservation(self):
        short_order = self.app.context.create_short_order(
            target_symbol="ADA", price=10, amount=100,
        )
        order_service = self.app.container.order_service()
        order_service.update(
            short_order.id,
            {
                "filled": 100, "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            }
        )
        # Post short fill: unallocated = 2000.

        cover_order = self.app.context.create_cover_order(
            target_symbol="ADA", price=8, amount=100,
        )
        portfolio = self.app.container.portfolio_service().get(1)
        self.assertEqual(1200, portfolio.get_unallocated())

        order_service.update(
            cover_order.id, {"status": OrderStatus.CANCELED.value}
        )
        portfolio = self.app.container.portfolio_service().get(1)
        # Reservation (800) refunded \u2192 back to 2000.
        self.assertEqual(2000, portfolio.get_unallocated())

        # Short position still open.
        position_service = self.app.container.position_service()
        ada_position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        self.assertEqual(-100, ada_position.get_amount())
