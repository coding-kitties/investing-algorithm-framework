import os
from decimal import Decimal

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, CSVTickerMarketDataSource, Algorithm, \
    MarketCredential, OperationalException
from tests.resources import TestBase, MarketServiceStub


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

    def setUp(self) -> None:
        super().setUp()
        self.app.add_market_data_source(CSVTickerMarketDataSource(
            identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=os.path.join(
                self.resource_directory,
                "market_data_sources",
                "TICKER_BTC-EUR_BINANCE_2023-08-23:22:00_2023-12-02:00:00.csv"
            )
        ))

    def test_close_trade(self):
        trading_symbol_position = self.app.algorithm.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.algorithm.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(0, len(self.app.algorithm.get_trades()))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        trades = self.app.algorithm.get_trades()
        trade = trades[0]
        self.assertIsNotNone(trade.get_amount())
        self.assertEqual(Decimal(1), trade.get_amount())
        self.app.algorithm.close_trade(trade)
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        self.assertEqual(0, len(self.app.algorithm.get_open_trades()))

    def test_close_trade_with_already_closed_trade(self):
        trading_symbol_position = self.app.algorithm.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.algorithm.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(0, len(self.app.algorithm.get_trades()))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        trades = self.app.algorithm.get_trades()
        trade = trades[0]
        self.assertIsNotNone(trade.get_amount())
        self.assertEqual(Decimal(1), trade.get_amount())
        self.app.algorithm.close_trade(trade)
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        self.assertEqual(0, len(self.app.algorithm.get_open_trades()))
        trades = self.app.algorithm.get_trades()
        trade = trades[0]

        with self.assertRaises(OperationalException):
            self.app.algorithm.close_trade(trade)
