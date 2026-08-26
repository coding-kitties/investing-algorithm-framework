from unittest import TestCase
from investing_algorithm_framework import Algorithm, TradingStrategy, \
    DataSource, DataType, OperationalException, TimeUnit, Schedule, \
    create_app, PositionSize, ScalingRule


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


class StrategyWithoutSchedule(TradingStrategy):

    def __init__(self):
        self.strategy_id = self.__class__.__name__


class TestStrategy(TestCase):

    def test_configurations(self):
        strategy = StrategyForTesting()
        self.assertEqual(len(strategy.data_sources), 2)
        self.assertTrue(strategy.schedule.is_interval)
        self.assertTrue(TimeUnit.HOUR.equals(strategy.schedule.time_unit))
        self.assertEqual(strategy.schedule.interval, 2)

    def test_app_rejects_strategy_without_schedule(self):
        with self.assertRaisesRegex(
            OperationalException, "Schedule not set"
        ):
            create_app().add_strategy(StrategyWithoutSchedule())

    def test_algorithm_rejects_strategy_without_schedule(self):
        with self.assertRaisesRegex(
            OperationalException, "Schedule not set"
        ):
            Algorithm().add_strategy(StrategyWithoutSchedule())


class TestPositionSizeAndScalingRuleDefaults(TestCase):
    """symbol=None entries act as a default for every symbol that
    doesn't have its own symbol-specific entry, which always takes
    precedence."""

    def test_position_size_default_applies_to_symbol_without_override(
        self,
    ):
        strategy = StrategyForTesting(
            position_sizes=[
                PositionSize(symbol=None, percentage_of_portfolio=20.0),
            ],
        )
        size = strategy.get_position_size("BTC")
        self.assertEqual(20.0, size.percentage_of_portfolio)

    def test_position_size_symbol_specific_overrides_default(self):
        strategy = StrategyForTesting(
            position_sizes=[
                PositionSize(symbol=None, percentage_of_portfolio=20.0),
                PositionSize(symbol="BTC", percentage_of_portfolio=50.0),
            ],
        )
        self.assertEqual(
            50.0, strategy.get_position_size("BTC").percentage_of_portfolio
        )
        self.assertEqual(
            20.0, strategy.get_position_size("ETH").percentage_of_portfolio
        )

    def test_scaling_rule_default_applies_to_symbol_without_override(self):
        strategy = StrategyForTesting(
            scaling_rules=[
                ScalingRule(symbol=None, max_position_percentage=20.0),
            ],
        )
        rule = strategy.get_scaling_rule("BTC")
        self.assertEqual(20.0, rule.max_position_percentage)

    def test_scaling_rule_symbol_specific_overrides_default(self):
        strategy = StrategyForTesting(
            scaling_rules=[
                ScalingRule(symbol=None, max_position_percentage=20.0),
                ScalingRule(symbol="BTC", max_position_percentage=50.0),
            ],
        )
        self.assertEqual(
            50.0, strategy.get_scaling_rule("BTC").max_position_percentage
        )
        self.assertEqual(
            20.0, strategy.get_scaling_rule("ETH").max_position_percentage
        )
