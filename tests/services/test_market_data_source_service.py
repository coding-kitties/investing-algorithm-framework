import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, CSVTickerMarketDataSource, MarketCredential, \
    Algorithm
from tests.resources import TestBase, MarketServiceStub


class TestMarketDataSourceService(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(
            MarketServiceStub(self.app.container.market_credential_service())
        )
        self.app.add_market_data_source(CSVTickerMarketDataSource(
            identifier="BTC/EUR-ticker",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=os.path.join(
                self.resource_dir,
                "market_data_sources",
                "TICKER_BTC-EUR_BINANCE_2023-08-23:22:00_2023-12-02:00:00.csv"
            )
        ))
        algorithm = Algorithm()
        self.app.add_algorithm(algorithm)
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="api_key",
                secret_key="secret_key",
            )
        )
        self.app.initialize()

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
