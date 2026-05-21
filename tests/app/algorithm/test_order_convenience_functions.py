from unittest.mock import patch

from investing_algorithm_framework import (
    MarketCredential,
    OperationalException,
    OrderSide,
    OrderStatus,
    PortfolioConfiguration,
)
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestOrderConvenienceFunctions(TestBase):
    """Tests for ``Context.order_value``, ``order_percent``,
    ``order_target``, ``order_target_value`` and ``order_target_percent``
    (issue #440)."""

    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR",
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    external_balances = {"EUR": 1000}

    # ---------------------------------------------------------------
    # order_value
    # ---------------------------------------------------------------
    def test_order_value_buy(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        order = self.app.context.order_value(
            target_symbol="BTC",
            value=200,
            order_side=OrderSide.BUY,
            price=10,
        )
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        self.assertEqual("LIMIT", order.get_order_type())

    def test_order_value_rejects_non_positive_value(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        with self.assertRaises(OperationalException):
            self.app.context.order_value(
                target_symbol="BTC",
                value=0,
                order_side=OrderSide.BUY,
                price=10,
            )

    def test_order_value_rejects_non_positive_price(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        with self.assertRaises(OperationalException):
            self.app.context.order_value(
                target_symbol="BTC",
                value=100,
                order_side=OrderSide.BUY,
                price=0,
            )

    # ---------------------------------------------------------------
    # order_percent
    # ---------------------------------------------------------------
    def test_order_percent_buy(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        # 20% of 1000 EUR = 200 EUR / 10 = 20 BTC
        order = self.app.context.order_percent(
            target_symbol="BTC",
            percent=20,
            order_side=OrderSide.BUY,
            price=10,
        )
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        self.assertEqual(OrderStatus.OPEN.value, order.status)

    def test_order_percent_rejects_zero(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        with self.assertRaises(OperationalException):
            self.app.context.order_percent(
                target_symbol="BTC",
                percent=0,
                order_side=OrderSide.BUY,
                price=10,
            )

    # ---------------------------------------------------------------
    # order_target
    # ---------------------------------------------------------------
    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_order_target_buys_from_zero(self, mock_get_ticker):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR",
            "bid": 10,
            "ask": 10,
            "last": 10,
        }
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        order = self.app.context.order_target(
            target_symbol="BTC",
            target_amount=5,
            price=10,
        )
        self.assertEqual(5, order.get_amount())
        self.assertEqual("BUY", order.get_order_side())

    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_order_target_sells_excess(self, mock_get_ticker):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR",
            "bid": 10,
            "ask": 10,
            "last": 10,
        }
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        # Build up a position of 10 BTC
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side=OrderSide.BUY,
            amount=10,
        )
        self.app.container.order_service().check_pending_orders()
        # Now target down to 4 BTC -> SELL 6
        order = self.app.context.order_target(
            target_symbol="BTC",
            target_amount=4,
            price=10,
        )
        self.assertEqual(6, order.get_amount())
        self.assertEqual("SELL", order.get_order_side())

    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_order_target_no_op_when_already_at_target(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR",
            "bid": 10,
            "ask": 10,
            "last": 10,
        }
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side=OrderSide.BUY,
            amount=5,
        )
        self.app.container.order_service().check_pending_orders()
        result = self.app.context.order_target(
            target_symbol="BTC",
            target_amount=5,
            price=10,
        )
        self.assertIsNone(result)

    def test_order_target_rejects_negative_target(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        with self.assertRaises(OperationalException):
            self.app.context.order_target(
                target_symbol="BTC",
                target_amount=-1,
                price=10,
            )

    # ---------------------------------------------------------------
    # order_target_value
    # ---------------------------------------------------------------
    def test_order_target_value_buys_from_zero(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        # No position -> need 300 / 10 = 30 BTC
        order = self.app.context.order_target_value(
            target_symbol="BTC",
            target_value=300,
            price=10,
        )
        self.assertEqual(30, order.get_amount())
        self.assertEqual("BUY", order.get_order_side())

    def test_order_target_value_rejects_negative(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        with self.assertRaises(OperationalException):
            self.app.context.order_target_value(
                target_symbol="BTC",
                target_value=-1,
                price=10,
            )

    # ---------------------------------------------------------------
    # order_target_percent
    # ---------------------------------------------------------------
    def test_order_target_percent_buys_from_zero(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        # 30% of 1000 EUR = 300 EUR / 10 = 30 BTC
        order = self.app.context.order_target_percent(
            target_symbol="BTC",
            target_percent=30,
            price=10,
        )
        self.assertEqual(30, order.get_amount())
        self.assertEqual("BUY", order.get_order_side())

    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_order_target_percent_rebalances_down(self, mock_get_ticker):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR",
            "bid": 10,
            "ask": 10,
            "last": 10,
        }
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        # Take 60% allocation: 600 / 10 = 60 BTC
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side=OrderSide.BUY,
            amount=60,
        )
        self.app.container.order_service().check_pending_orders()
        # Rebalance to 10% -> target_value = 100 -> target_amount = 10
        # -> SELL 50
        order = self.app.context.order_target_percent(
            target_symbol="BTC",
            target_percent=10,
            price=10,
        )
        self.assertEqual(50, order.get_amount())
        self.assertEqual("SELL", order.get_order_side())

    def test_order_target_percent_rejects_negative(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        with self.assertRaises(OperationalException):
            self.app.context.order_target_percent(
                target_symbol="BTC",
                target_percent=-1,
                price=10,
            )
