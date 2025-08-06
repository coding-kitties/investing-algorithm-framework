from decimal import Decimal
from unittest.mock import patch

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OperationalException
from tests.resources import TestBase


class Test(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def test_close_trade(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(1, len(self.app.context.get_trades()))

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={
                "bid": 990,
                "ask": 1000,
                "last": 995

            }
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
                return_value={
                    "bid": 990,
                    "ask": 1000,
                    "last": 995

                }
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
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(1, len(self.app.context.get_trades()))

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={
                "bid": 990,
                "ask": 1000,
                "last": 995

            }
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
                return_value={
                    "bid": 990,
                    "ask": 1000,
                    "last": 995

                }
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
