"""
Consolidated tests for trade-related context operations.

Merged from:
- test_get_trades.py
- test_get_open_trades.py
- test_get_closed_trades.py
- test_close_trade.py
"""
from decimal import Decimal
from unittest.mock import patch

from investing_algorithm_framework import OperationalException
from tests.resources import BitvavoTestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestGetTrades(BitvavoTestBase):

    def test_get_trades(self):
        order = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=20
        )
        self.assertIsNotNone(order)
        self.assertEqual(1, len(self.app.context.get_trades()))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.context.get_trades()))
        trade = self.app.context.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(20, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_at)
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=20
        )
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.context.get_trades()))
        trade = self.app.context.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(20, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNotNone(trade.closed_at)


class TestGetOpenTrades(BitvavoTestBase):

    def test_get_open_trades(self):
        order = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=20
        )
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.context.get_open_trades("BTC")))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.context.get_open_trades("BTC")))
        trade = self.app.context.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(20, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(1, len(self.app.context.get_open_trades("BTC")))
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=20
        )
        self.assertEqual(0, len(self.app.context.get_open_trades("BTC")))

    def test_get_open_trades_with_close_trades(self):
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=5
        )
        order = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=5
        )
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.context.get_open_trades("BTC")))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(2, len(self.app.context.get_open_trades("BTC")))
        trade = self.app.context.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(5, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_at)
        self.assertEqual(
            0,
            len(self.app.context
                .get_orders(order_side="SELL", status="OPEN"))
        )
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=5
        )
        self.assertEqual(
            1,
            len(self.app.context.get_orders(order_side="SELL", status="OPEN"))
        )
        self.assertEqual(1, len(self.app.context.get_open_trades("BTC")))
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=5
        )
        self.assertEqual(
            2,
            len(self.app.context.get_orders(order_side="SELL", status="OPEN"))
        )
        self.assertEqual(0, len(self.app.context.get_open_trades("BTC")))

    def test_get_open_trades_with_close_trades_of_partial_buy_orders(self):
        order_one = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=5
        )
        order_two = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=5
        )
        order_one_id = order_one.id
        order_two_id = order_two.id
        self.assertIsNotNone(order_one)
        self.assertIsNotNone(order_two)
        self.assertEqual(0, len(self.app.context.get_open_trades("BTC")))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(2, len(self.app.context.get_open_trades("BTC")))
        trade = self.app.context.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(5, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_at)

        # All orders are filled
        self.assertEqual(
            0,
            len(self.app.context.get_orders(order_side="SELL", status="OPEN"))
        )
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=2.5
        )
        self.assertEqual(
            1,
            len(self.app.context.get_orders(order_side="SELL", status="OPEN"))
        )
        trade_one = self.app.context.get_trade(order_id=order_one_id)
        trade_two = self.app.context.get_trade(order_id=order_two_id)
        self.assertEqual(2.5, trade_one.available_amount)
        self.assertEqual(5, trade_two.available_amount)
        self.app.context.order_service.check_pending_orders()
        trade_one = self.app.context.get_trade(order_id=order_one_id)
        trade_two = self.app.context.get_trade(order_id=order_two_id)
        self.assertEqual(2.5, trade_one.available_amount)
        self.assertEqual(5, trade_two.available_amount)
        self.assertEqual(2, len(self.app.context.get_open_trades("BTC")))


class TestGetClosedTrades(BitvavoTestBase):

    def test_get_closed_trades(self):
        self.app.add_strategy(StrategyOne)
        order = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=20
        )
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.context.get_closed_trades()))
        order_service = self.app.container.order_service()

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 10, "ask": 10, "last": 10}
        ):
            order_service.check_pending_orders()
            self.assertEqual(0, len(self.app.context.get_closed_trades()))
            trade = self.app.context.get_trades()[0]
            self.assertEqual(10, trade.open_price)
            self.assertEqual(20, trade.amount)
            self.assertEqual("BTC", trade.target_symbol)
            self.assertEqual("EUR", trade.trading_symbol)
            self.assertIsNone(trade.closed_at)
            self.app.context.create_limit_order(
                target_symbol="BTC", price=10, order_side="SELL", amount=20
            )
            order_service.check_pending_orders()
            self.assertEqual(1, len(self.app.context.get_closed_trades()))


class TestCloseTrade(BitvavoTestBase):

    def test_close_trade(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(1, len(self.app.context.get_trades()))

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 990, "ask": 1000, "last": 995}
        ):
            order_service = self.app.container.order_service()
            order_service.check_pending_orders()
            self.assertEqual(1, len(self.app.context.get_trades()))
            trades = self.app.context.get_trades()
            trade = trades[0]
            self.assertIsNotNone(trade.amount)
            self.assertEqual(trade.remaining, 0)
            self.assertEqual(trade.filled_amount, 1)
            self.assertEqual(trade.available_amount, 1)
            self.assertEqual(Decimal(1), trade.amount)

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 990, "ask": 1000, "last": 995}
        ):
            self.app.context.close_trade(trade)
            self.assertEqual(1, len(self.app.context.get_trades()))
            order_service.check_pending_orders()
            self.assertEqual(1, len(self.app.context.get_trades()))
            self.assertEqual(0, len(self.app.context.get_open_trades()))

    def test_close_trade_with_already_closed_trade(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(1, len(self.app.context.get_trades()))

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 990, "ask": 1000, "last": 995}
        ):
            order_service = self.app.container.order_service()
            order_service.check_pending_orders()
            self.assertEqual(1, len(self.app.context.get_trades()))
            trades = self.app.context.get_trades()
            trade = trades[0]
            self.assertIsNotNone(trade.amount)
            self.assertEqual(trade.remaining, 0)
            self.assertEqual(trade.filled_amount, 1)
            self.assertEqual(trade.available_amount, 1)
            self.assertEqual(Decimal(1), trade.amount)

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 990, "ask": 1000, "last": 995}
        ):
            self.app.context.close_trade(trade)
            self.assertEqual(1, len(self.app.context.get_trades()))
            order_service.check_pending_orders()
            self.assertEqual(1, len(self.app.context.get_trades()))
            self.assertEqual(0, len(self.app.context.get_open_trades()))

        trades = self.app.context.get_trades()
        trade = trades[0]

        with self.assertRaises(OperationalException):
            self.app.context.close_trade(trade)

