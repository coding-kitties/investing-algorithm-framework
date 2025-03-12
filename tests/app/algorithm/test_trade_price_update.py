import os
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    Algorithm, MarketCredential, CSVOHLCVMarketDataSource, \
    CSVTickerMarketDataSource
from tests.resources import random_string, MarketServiceStub

class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2
    market_data_sources = ["BTC/EUR-ohlcv", "BTC/EUR-ticker"]

    def apply_strategy(self, context, market_data):
        pass


class Test(TestCase):

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

    def tearDown(self) -> None:
        super().tearDown()
        # Delete the resources database directory

        database_dir = os.path.join(self.resource_dir, "databases")

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))


    def test_trade_recent_price_update(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.container.market_service.override(MarketServiceStub(None))
        app.container.portfolio_configuration_service().clear()
        app.add_market_data_source(
            CSVOHLCVMarketDataSource(
                identifier="BTC/EUR-ohlcv",
                market="BINANCE",
                symbol="BTC/EUR",
                window_size=200,
                csv_file_path=os.path.join(
                    self.resource_dir,
                    "market_data_sources",
                    "OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
                )
            )
        )
        app.add_market_data_source(
            CSVTickerMarketDataSource(
                identifier="BTC/EUR-ticker",
                market="BINANCE",
                symbol="BTC/EUR",
                csv_file_path=os.path.join(
                    self.resource_dir,
                    "market_data_sources",
                    "TICKER_DOT-EUR_BINANCE_2023-08-23-22-00_2023-12-02-00-00.csv"
                )
            )
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BINANCE",
                trading_symbol="EUR",
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                api_key=random_string(10),
                secret_key=random_string(10)
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        app.add_algorithm(algorithm)
        app.set_config(
            "DATE_TIME", datetime(2023, 11, 2, 7, 59, tzinfo=timezone.utc)
        )
        app.initialize_config()
        app.initialize()
        app.context.create_limit_order(
            target_symbol="btc",
            amount=20,
            price=20,
            order_side="BUY"
        )
        app.run(number_of_iterations=1)
        strategy_orchestration_service = app.algorithm\
            .strategy_orchestrator_service
        self.assertTrue(strategy_orchestration_service.has_run("StrategyOne"))

        # Check that the last reported price is updated
        trade = app.context.get_trades()[0]
        self.assertIsNotNone(trade)
        self.assertIsNotNone(trade.last_reported_price)
