import os

from investing_algorithm_framework import RESOURCE_DIRECTORY, \
    PortfolioConfiguration, CSVTickerMarketDataSource, MarketCredential
from tests.resources import TestBase


class TestMarketDataSourceService(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="USDT"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
         "USDT": 1000
    }

    def setUp(self) -> None:
        super(TestMarketDataSourceService, self).setUp()
        configuration_service = self.app.container.configuration_service()
        config = configuration_service.get_config()
        self.app.add_market_data_source(CSVTickerMarketDataSource(
            identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=os.path.join(
                config[RESOURCE_DIRECTORY],
                "market_data_sources",
                "TICKER_BTC-EUR_BINANCE_2023-08-23-22-00_2023-12-02-00-00.csv"
            )
        ))

    def test_get_ticker_market_data_source(self):
        market_data_source_service = self.app.container\
            .market_data_source_service()
        ticker_market_data_source = market_data_source_service\
            .get_ticker_market_data_source(
                symbol="BTC/EUR",
                market="BITVAVO"
            )
        self.assertIsNotNone(ticker_market_data_source)
        self.assertEqual("BTC/EUR", ticker_market_data_source.symbol)
        self.assertEqual("BITVAVO", ticker_market_data_source.market)
        self.assertTrue(
            isinstance(ticker_market_data_source, CSVTickerMarketDataSource)
        )
        ticker_market_data_source = market_data_source_service \
            .get_ticker_market_data_source(
                symbol="BTC/EUR",
            )
        self.assertIsNotNone(ticker_market_data_source)
        self.assertEqual("BTC/EUR", ticker_market_data_source.symbol)
        self.assertEqual("BITVAVO", ticker_market_data_source.market)
        self.assertTrue(
            isinstance(ticker_market_data_source, CSVTickerMarketDataSource)
        )
