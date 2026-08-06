from unittest import TestCase
from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, TimeUnit, Schedule


class StrategyForTesting(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="twitter_data"
        ),
    ]
    schedule = Schedule.every(2, TimeUnit.HOUR)
    def run_strategy(self, context, data):
        pass


class TestStrategy(TestCase):

    def test_configurations(self):
        strategy = StrategyForTesting()
        self.assertEqual(len(strategy.data_sources), 2)
        self.assertTrue(strategy.schedule.is_interval)
        self.assertTrue(TimeUnit.HOUR.equals(strategy.schedule.time_unit))
        self.assertEqual(strategy.schedule.interval, 2)
