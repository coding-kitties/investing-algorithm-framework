"""
Consolidated tests for trade-related context operations.

Merged from:
- test_get_trades.py
- test_get_open_trades.py
- test_get_closed_trades.py
- test_close_trade.py
"""
from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from investing_algorithm_framework import OperationalException
from investing_algorithm_framework.app.context import Context
from tests.resources import BitvavoTestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestGetTrades(BitvavoTestBase):

    def test_filtered_history_includes_closed_filled_lots(self):
        context = self.app.context
        context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=20,
        )
        context.order_service.check_pending_orders()
        portfolio = context.portfolio_service.get_all()[0]
        filters = {
            "target_symbol": "BTC", "trading_symbol": "EUR",
            "market": portfolio.market, "portfolio": portfolio.id,
        }
        self.assertEqual(len(context.get_trades(**filters)), 1)
        self.assertEqual(context.get_trades(target_symbol="ETH"), [])
        self.assertEqual(context.get_trades(trading_symbol="USD"), [])
        self.assertEqual(context.get_trades(status="CLOSED"), [])

        context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=20,
        )
        context.order_service.check_pending_orders()
        history = context.get_trades(**filters)
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0].is_short)
        self.assertGreater(history[0].filled_amount, 0)
        self.assertIsNotNone(history[0].opened_at)
        self.assertIsNotNone(history[0].closed_at)
        self.assertEqual(context.get_trades(status="OPEN"), [])
        self.assertEqual(
            context.get_trades(status="CLOSED")[0].id, history[0].id,
        )

    def test_get_trades(self):
        order = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=20
        )
        self.assertIsNotNone(order)
        # v9.0 (#431) — BUY trade is deferred until fill.
        self.assertEqual(0, len(self.app.context.get_trades()))
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


class TestGetTradesFilterForwarding(TestCase):
    def setUp(self):
        self.context = Context.__new__(Context)
        self.context.trade_service = Mock()
        self.context.portfolio_service = Mock()
        self.portfolio = SimpleNamespace(id=7, market="BITVAVO")
        self.context.portfolio_service.get.return_value = self.portfolio
        self.context.portfolio_service.find.return_value = self.portfolio

    def test_forwards_all_supported_filters(self):
        opened_since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = self.context.get_trades(
            target_symbol="BTC", trading_symbol="EUR", market="BITVAVO",
            portfolio=7, status="CLOSED", opened_since=opened_since,
        )
        self.context.trade_service.get_all.assert_called_once_with({
            "portfolio_id": 7, "target_symbol": "BTC",
            "trading_symbol": "EUR", "status": "CLOSED",
            "opened_at_gte": opened_since,
        })
        self.assertIs(result, self.context.trade_service.get_all.return_value)

    def test_market_resolves_to_portfolio_id(self):
        self.context.get_trades(target_symbol="BTC", market="BITVAVO")
        self.context.portfolio_service.find.assert_called_once_with({
            "market": "BITVAVO",
        })
        self.context.trade_service.get_all.assert_called_once_with({
            "portfolio_id": 7, "target_symbol": "BTC",
        })

    def test_accepts_portfolio_object_without_market_lookup(self):
        self.context.get_trades(portfolio=self.portfolio)
        self.context.portfolio_service.find.assert_not_called()
        self.context.portfolio_service.get.assert_not_called()
        self.context.trade_service.get_all.assert_called_once_with({
            "portfolio_id": 7,
        })

    def test_conflicting_market_and_portfolio_do_not_leak_history(self):
        self.assertEqual(self.context.get_trades(
            market="OTHER", portfolio=7,
        ), [])
        self.context.trade_service.get_all.assert_not_called()

    def test_no_filters_preserves_unrestricted_history(self):
        self.context.get_trades()
        self.context.trade_service.get_all.assert_called_once_with({})


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
        self.assertEqual(1, len(self.app.context.get_open_trades("BTC")))
        order_service.check_pending_orders()
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
        self.assertEqual(2, len(self.app.context.get_open_trades("BTC")))
        self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="SELL", amount=5
        )
        self.assertEqual(
            2,
            len(self.app.context.get_orders(order_side="SELL", status="OPEN"))
        )
        self.assertEqual(2, len(self.app.context.get_open_trades("BTC")))
        order_service.check_pending_orders()
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
        # v9.0 (#431) — BUY trade is deferred until fill.
        self.assertEqual(0, len(self.app.context.get_trades()))

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
        # v9.0 (#431) — BUY trade is deferred until fill.
        self.assertEqual(0, len(self.app.context.get_trades()))

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
