import os
from decimal import Decimal

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, CSVTickerMarketDataSource, Algorithm, \
    MarketCredential
from tests.resources import TestBase, MarketServiceStub


class Test(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
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
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        self.app.container.market_service.override(MarketServiceStub(None))
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
        self.app.add_algorithm(Algorithm())
        self.app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        self.app.initialize()

    def test_close_position(self):
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
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        btc_position = self.app.algorithm.get_position("BTC")
        self.assertIsNotNone(btc_position.get_amount())
        self.assertEqual(Decimal(1), btc_position.get_amount())
        self.assertNotEqual(Decimal(990), trading_symbol_position.get_amount())
        self.app.algorithm.close_position("BTC")
        self.app.run(number_of_iterations=1)
        btc_position = self.app.algorithm.get_position("BTC")
        self.assertEqual(Decimal(0), btc_position.get_amount())
