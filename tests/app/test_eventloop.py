from unittest import TestCase
from datetime import datetime, timezone, timedelta

from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, MarketCredential, PortfolioConfiguration

from tests.resources import TestBase


class StragyForTesting(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="DOT/EUR",
            time_frame="2h",
            market="bitvavo"
        )
    ]
    time_unit = "hour"
    interval = 2

    def run_strategy(self, context, market_data):
        pass


class StrategyForTestingTwo(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="ETH/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="custom_feed_data"
        ),
    ]
    time_unit = "hour"
    interval = 4

    def run_strategy(self, context, market_data):
        pass


class StrategyForTestingThree(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="twitter_data"
        ),
    ]
    time_unit = "day"
    interval = 1

    def run_strategy(self, context, market_data):
        pass


class TestEventloopService(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def test_initialize(self):
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=self.app.container.data_provider_service()
        )
        event_loop_service.strategies = [
            StragyForTesting(),
            StrategyForTestingTwo(),
            StrategyForTestingThree()
        ]
        event_loop_service.initialize()
        self.assertEqual(len(event_loop_service.next_run_times), 3)
        self.assertEqual(len(event_loop_service.data_sources), 5)

        # Each next run time should be set to the current datatime
        # because no runs have been executed yet
        for strategy in event_loop_service.strategies:
            self.assertIn(
                strategy.strategy_id,
                event_loop_service.next_run_times
            )
            self.assertAlmostEqual(
                event_loop_service\
                    .next_run_times[strategy.strategy_id]["next_run"],
                datetime.now(tz=timezone.utc),
                delta=timedelta(seconds=10)
            )
