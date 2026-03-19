from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus, TradeStatus
from tests.resources import TestBase


class TestTradeServiceNetGain(TestBase):
    """
    Regression tests for portfolio net_gain accumulation bug (#397).

    Bug 1 (PRIMARY): In create_order_metadata_with_trade_context, the
    ``cost`` variable accumulated across loop iterations and was
    subtracted fully on each iteration, understating
    portfolio.total_net_gain when a sell order closed multiple trades.

    Bug 2 (SECONDARY): In _create_trade_metadata_with_sell_order_and_trades,
    ``sell_amount`` (total order amount) was used instead of
    ``trade_data["amount"]`` (per-trade portion), overstating individual
    trade net_gain values.
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
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 100000}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _create_filled_buy_order(
        self, target_symbol, amount, price, portfolio_id
    ):
        """Create a BUY order and immediately fill it, producing an
        OPEN trade."""
        order_service = self.app.container.order_service()
        order = order_service.create({
            "target_symbol": target_symbol,
            "trading_symbol": "EUR",
            "amount": amount,
            "order_side": "BUY",
            "price": price,
            "order_type": "LIMIT",
            "portfolio_id": portfolio_id,
        })
        order_service.update(order.id, {
            "status": OrderStatus.CLOSED.value,
            "filled": amount,
            "remaining": 0,
        })
        return order

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_net_gain_correct_single_trade(self):
        """Baseline: sell order that closes ONE trade.

        net_gain = (sell_price * amount) - (open_price * amount).
        """
        portfolio = self.app.context.get_portfolio()
        portfolio_id = portfolio.id
        trade_service = self.app.container.trade_service()
        order_service = self.app.container.order_service()

        # Buy 100 ADA at 10 EUR
        buy = self._create_filled_buy_order("ADA", 100, 10, portfolio_id)
        trade = trade_service.find({"order_id": buy.id})
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(100, trade.available_amount)

        # Sell 100 ADA at 15 EUR
        order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 100,
            "order_side": "SELL",
            "price": 15,
            "order_type": "LIMIT",
            "portfolio_id": portfolio_id,
        })

        # Verify trade net_gain: (15 * 100) - (10 * 100) = 500
        trade = trade_service.get(trade.id)
        self.assertAlmostEqual(500, trade.net_gain)

        # Verify portfolio total_net_gain
        portfolio = self.app.container.portfolio_repository() \
            .get(portfolio_id)
        self.assertAlmostEqual(500, portfolio.total_net_gain)

    def test_net_gain_correct_multiple_trades(self):
        """Regression for bug #1 — cost accumulation.

        Two buy orders at different prices, then one sell order that
        closes both.  The old code accumulated ``cost`` across loop
        iterations, causing portfolio.total_net_gain = -200 instead of
        the correct 800.

        trade1: buy 100 @ 10, trade2: buy 100 @ 12, sell 200 @ 15.
        Expected: total_net_gain = (15-10)*100 + (15-12)*100 = 800.
        """
        portfolio = self.app.context.get_portfolio()
        portfolio_id = portfolio.id
        trade_service = self.app.container.trade_service()
        order_service = self.app.container.order_service()

        # Trade 1: buy 100 ADA at 10
        buy1 = self._create_filled_buy_order("ADA", 100, 10, portfolio_id)
        trade1 = trade_service.find({"order_id": buy1.id})

        # Trade 2: buy 100 ADA at 12
        buy2 = self._create_filled_buy_order("ADA", 100, 12, portfolio_id)
        trade2 = trade_service.find({"order_id": buy2.id})

        self.assertEqual(TradeStatus.OPEN.value, trade1.status)
        self.assertEqual(TradeStatus.OPEN.value, trade2.status)

        # Sell 200 ADA at 15 — closes both trades
        order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 200,
            "order_side": "SELL",
            "price": 15,
            "order_type": "LIMIT",
            "portfolio_id": portfolio_id,
        })

        # Verify individual trade net_gains
        trade1 = trade_service.get(trade1.id)
        trade2 = trade_service.get(trade2.id)
        expected_gain_1 = (15 * 100) - (10 * 100)   # 500
        expected_gain_2 = (15 * 100) - (12 * 100)   # 300

        self.assertAlmostEqual(expected_gain_1, trade1.net_gain)
        self.assertAlmostEqual(expected_gain_2, trade2.net_gain)

        # Verify portfolio total_net_gain — the key regression check
        portfolio = self.app.container.portfolio_repository() \
            .get(portfolio_id)
        expected_total = expected_gain_1 + expected_gain_2   # 800
        self.assertAlmostEqual(
            expected_total,
            portfolio.total_net_gain,
            msg=(
                f"portfolio.total_net_gain should be {expected_total}, "
                f"got {portfolio.total_net_gain}. "
                "Bug #397: cost accumulation gave -200 instead of 800."
            ),
        )

    def test_net_gain_correct_with_explicit_trades_list(self):
        """Regression for bug #2 — sell_amount vs per-trade amount.

        When a sell order is created with an explicit ``trades`` list
        (e.g. from stop-loss / take-profit), the per-trade net_gain must
        use ``trade_data["amount"]``, not ``sell_amount``.

        trade1: buy 100 @ 10, trade2: buy 50 @ 12, sell 150 @ 15.
        With the bug each trade's net_gain was computed against
        sell_amount=150 instead of per-trade amounts 100/50.
        """
        portfolio = self.app.context.get_portfolio()
        portfolio_id = portfolio.id
        trade_service = self.app.container.trade_service()
        order_service = self.app.container.order_service()

        # Trade 1: buy 100 ADA at 10
        buy1 = self._create_filled_buy_order("ADA", 100, 10, portfolio_id)
        trade1 = trade_service.find({"order_id": buy1.id})

        # Trade 2: buy 50 ADA at 12
        buy2 = self._create_filled_buy_order("ADA", 50, 12, portfolio_id)
        trade2 = trade_service.find({"order_id": buy2.id})

        # Sell 150 ADA at 15 with explicit trades in data
        order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 150,
            "order_side": "SELL",
            "price": 15,
            "order_type": "LIMIT",
            "portfolio_id": portfolio_id,
            "trades": [
                {"trade_id": trade1.id, "amount": 100},
                {"trade_id": trade2.id, "amount": 50},
            ],
        })

        # Verify individual trade net_gains use per-trade amounts
        trade1 = trade_service.get(trade1.id)
        trade2 = trade_service.get(trade2.id)
        expected_gain_1 = (15 * 100) - (10 * 100)  # 500
        expected_gain_2 = (15 * 50) - (12 * 50)    # 150

        self.assertAlmostEqual(
            expected_gain_1,
            trade1.net_gain,
            msg=(
                f"trade1.net_gain should be {expected_gain_1}, "
                f"got {trade1.net_gain}. "
                "Bug #397: sell_amount used instead of per-trade amount."
            ),
        )
        self.assertAlmostEqual(
            expected_gain_2,
            trade2.net_gain,
            msg=(
                f"trade2.net_gain should be {expected_gain_2}, "
                f"got {trade2.net_gain}. "
                "Bug #397: sell_amount used instead of per-trade amount."
            ),
        )

        # Verify portfolio total_net_gain (also exercises bug #1 path)
        portfolio = self.app.container.portfolio_repository() \
            .get(portfolio_id)
        expected_total = expected_gain_1 + expected_gain_2   # 650
        self.assertAlmostEqual(
            expected_total,
            portfolio.total_net_gain,
            msg=(
                f"portfolio.total_net_gain should be {expected_total}, "
                f"got {portfolio.total_net_gain}."
            ),
        )
