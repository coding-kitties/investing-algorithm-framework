import os
from decimal import Decimal

from investing_algorithm_framework import PortfolioConfiguration, \
    CSVTickerMarketDataSource, MarketCredential
from tests.resources import TestBase, RandomPriceMarketDataSourceServiceStub, \
    MarketDataSourceServiceStub


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
    market_data_source_service = RandomPriceMarketDataSourceServiceStub(
        None,
        None,
        None
    )
    market_data_source_service = MarketDataSourceServiceStub()

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.app.add_market_data_source(CSVTickerMarketDataSource(
            identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=os.path.join(
                self.resource_directory,
                "market_data_sources",
                "TICKER_BTC-EUR_BINANCE_2023-08-23-22-00_2023-12-02-00-00.csv"
            )
        ))

    def test_close_position(self):
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
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position.get_amount())
        self.assertEqual(Decimal(1), btc_position.get_amount())
        self.assertNotEqual(Decimal(990), trading_symbol_position.get_amount())
        self.app.context.close_position("BTC")
        self.app.run(number_of_iterations=1)
        btc_position = self.app.context.get_position("BTC")
        self.assertEqual(Decimal(0), btc_position.get_amount())
