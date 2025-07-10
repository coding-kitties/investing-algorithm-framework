from unittest import TestCase
from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, TimeUnit


class StrategyForTesting(TradingStrategy):
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
    time_unit = "hour"
    interval = 2

    def run_strategy(self, context, market_data):
        pass


class TestStrategy(TestCase):

    def test_configurations(self):
        strategy = StrategyForTesting()
        self.assertEqual(len(strategy.data_sources), 2)
        self.assertTrue(TimeUnit.HOUR.equals(strategy.time_unit))
        self.assertEqual(strategy.interval, 2)
