import os
from datetime import datetime
from investing_algorithm_framework import PortfolioConfiguration, \
    CSVTickerMarketDataSource, MarketCredential, BACKTESTING_INDEX_DATETIME
from tests.resources import TestBase


class Test(TestBase):
    external_balances = {
        "EUR": 1000
    }
    external_available_symbols = ["BTC/EUR"]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="bitvavo",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.app.add_market_data_source(CSVTickerMarketDataSource(
            identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=os.path.join(
                self.resource_directory,
                "market_data_sources_for_testing",
                "TICKER_BTC-EUR_BINANCE_2023-08-23:22:00_2023-12-02:00:00.csv"
            )
        ))

    def test_get_trades(self):
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=20
        )
        order = self.app.algorithm.get_order()
        self.assertIsNotNone(order)
        self.assertEqual(0, len(self.app.algorithm.get_trades()))
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        trade = self.app.algorithm.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(20, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNone(trade.closed_price)
        self.assertIsNone(trade.closed_at)
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=20
        )
        order_service.check_pending_orders()
        self.assertEqual(1, len(self.app.algorithm.get_trades()))
        trade = self.app.algorithm.get_trades()[0]
        self.assertEqual(10, trade.open_price)
        self.assertEqual(20, trade.amount)
        self.assertEqual("BTC", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertIsNotNone(trade.closed_price)
        self.assertIsNotNone(trade.closed_at)
