from unittest import TestCase
from unittest.mock import Mock
import pandas as pd
from investing_algorithm_framework import Algorithm, TradingStrategy, \
    DataSource, DataType, OperationalException, TimeUnit, Schedule, \
    create_app, PositionSize, ScalingRule, ConfluenceCard, PrimaryGroup, \
    Condition, ConditionExpression, Operator, EvaluationContext, SignalSide, \
    DECISION_TRACE_METADATA_KEY


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


class TestSignalCards(TestCase):

    def test_default_hooks_prepare_once_and_match_for_each_symbol(self):
        class PreparedStrategy(TradingStrategy):
            schedule = Schedule.every(1, TimeUnit.HOUR)
            signal_cards = {
                SignalSide.OPEN_LONG: self.card("entry"),
                SignalSide.CLOSE_LONG: self.card("exit"),
            }

            def prepare_signal_data(self, data):
                return data

        frame = pd.DataFrame({
            "entry": [True, False, pd.NA, True],
            "exit": [False, True, True, False],
        }, index=pd.date_range("2026-01-01", periods=4, tz="UTC"))
        strategy = PreparedStrategy()
        strategy.prepare_signal_data = Mock(wraps=strategy.prepare_signal_data)
        batches = list(strategy.generate_signal_series({"BTC": frame,
                                                       "ETH": frame}))
        strategy.prepare_signal_data.assert_called_once()
        self.assertEqual(4, len(batches))
        for index in range(len(frame)):
            strategy.prepare_signal_data.reset_mock()
            events = list(strategy.generate_signals(None, {
                "BTC": frame.iloc[:index + 1], "ETH": frame.iloc[:index + 1],
            }))
            strategy.prepare_signal_data.assert_called_once()
            expected = {(item.symbol, item.side) for item in batches
                        if item.series.iloc[index]}
            self.assertEqual(expected, {(item.symbol, item.side)
                                        for item in events})
        self.assertTrue(all(not batch.metadata for batch in batches))
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.backtest_service import BacktestService
        BacktestService.validate_strategy_for_vector_backtest(strategy)

    def test_default_hooks_reject_missing_preparation_and_bad_index(self):
        strategy = self.strategy({SignalSide.OPEN_LONG: self.card("entry")})
        with self.assertRaisesRegex(
            NotImplementedError, "prepare_signal_data"
        ):
            list(strategy.generate_signals(None, {}))
        strategy.prepare_signal_data = Mock(return_value={
            "BTC": pd.DataFrame({"entry": [True]}),
        })
        with self.assertRaisesRegex(ValueError, "DatetimeIndex"):
            list(strategy.generate_signal_series({}))
        empty = self.strategy({})
        self.assertEqual([], list(empty.generate_signals(None, {})))
        self.assertEqual([], list(empty.generate_signal_series({})))

    def test_default_vector_admission_and_existing_override(self):
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.backtest_service import BacktestService

        for strategy in (self.strategy({}), self.strategy({
            SignalSide.OPEN_LONG: self.card("entry"),
        })):
            with self.assertRaises(OperationalException):
                BacktestService.validate_strategy_for_vector_backtest(strategy)

        class CustomStrategy(TradingStrategy):
            schedule = Schedule.every(1, TimeUnit.HOUR)

            def generate_signal_series(self, data):
                return iter(())

        BacktestService.validate_strategy_for_vector_backtest(CustomStrategy())
        self.assertEqual([], list(CustomStrategy().generate_signal_series({})))

    def test_default_vector_rejects_unsorted_or_duplicate_timestamps(self):
        strategy = self.strategy({SignalSide.OPEN_LONG: self.card("entry")})
        for index in (
            pd.to_datetime(["2026-01-02", "2026-01-01"]),
            pd.to_datetime(["2026-01-01", "2026-01-01"]),
        ):
            with self.subTest(index=index):
                strategy.prepare_signal_data = Mock(return_value={
                    "BTC": pd.DataFrame({"entry": [True, False]}, index=index),
                })
                with self.assertRaisesRegex(ValueError, "unique and sorted"):
                    list(strategy.generate_signal_series({}))

    @staticmethod
    def card(name):
        return ConfluenceCard(
            name=name,
            primary=PrimaryGroup(ConditionExpression(
                Condition(name, Operator.EQ, True)
            )),
        )

    def strategy(self, cards):
        return TradingStrategy(
            schedule=Schedule.every(1, TimeUnit.HOUR), signal_cards=cards,
        )

    def test_entry_and_exit_are_independent_and_traced(self):
        strategy = self.strategy({
            SignalSide.OPEN_LONG: self.card("entry"),
            SignalSide.CLOSE_LONG: self.card("exit"),
        })
        strategy.record_decision_trace = Mock()
        signals = list(strategy.generate_signals_from_cards(
            EvaluationContext({"entry": False, "exit": True}), symbol="BTC"
        ))
        self.assertEqual(
            [SignalSide.CLOSE_LONG], [item.side for item in signals]
        )
        self.assertEqual("exit", signals[0].source)
        trace = signals[0].metadata[DECISION_TRACE_METADATA_KEY]
        self.assertIn({
            "name": "signal_side", "value": SignalSide.CLOSE_LONG.value,
            "unit": None, "description": None, "group": "decision",
        }, trace["entries"])
        strategy.record_decision_trace.assert_called_once()
        rejected = strategy.record_decision_trace.call_args.args[0]
        self.assertIn("REJECTED", rejected.summary)
        self.assertEqual(
            "BTC", strategy.record_decision_trace.call_args.kwargs["symbol"]
        )

    def test_all_signal_sides_can_be_mapped_without_combining_decisions(self):
        strategy = self.strategy({
            side: self.card(side.value) for side in SignalSide
        })
        signals = list(strategy.generate_signals_from_cards(
            EvaluationContext({side.value: True for side in SignalSide}),
            symbol="ETH",
        ))
        self.assertEqual(set(SignalSide), {signal.side for signal in signals})
        self.assertTrue(all(signal.symbol == "ETH" for signal in signals))

    def test_class_mapping_is_copied_and_constructor_can_override(self):
        class CardStrategy(TradingStrategy):
            schedule = Schedule.every(1, TimeUnit.HOUR)
            signal_cards = {SignalSide.OPEN_LONG: self.card("entry")}

        first = CardStrategy()
        second = CardStrategy()
        first.signal_cards.clear()
        self.assertEqual(1, len(second.signal_cards))
        self.assertEqual(1, len(CardStrategy.signal_cards))
        self.assertEqual({}, CardStrategy(signal_cards={}).signal_cards)

    def test_invalid_mapping_and_unconfigured_strategy(self):
        for cards in ({"entry": self.card("entry")},
                      {SignalSide.OPEN_LONG: True}):
            with self.subTest(cards=cards), self.assertRaises(ValueError):
                self.strategy(cards)
        signals = self.strategy({}).generate_signals_from_cards(
            EvaluationContext({}), symbol="BTC"
        )
        self.assertEqual([], list(signals))

    def test_rejected_card_traces_reset_between_strategy_ticks(self):
        from investing_algorithm_framework.domain import INDEX_DATETIME

        phase = Mock()

        def collect(state):
            signals = state.strategy.generate_signals_from_cards(
                EvaluationContext(state.data), symbol="BTC"
            )
            state.raw_signals = list(signals)

        phase.run.side_effect = collect
        strategy = TradingStrategy(
            schedule=Schedule.every(1, TimeUnit.HOUR), phases=[phase],
            signal_cards={
                SignalSide.OPEN_LONG: self.card("entry"),
                SignalSide.CLOSE_LONG: self.card("exit"),
            },
        )
        context = Mock(config={INDEX_DATETIME: None})
        strategy.run_strategy(context, {"entry": False, "exit": False})
        self.assertEqual(2, len(strategy.last_score_cards))
        self.assertEqual([], strategy.last_signals)
        strategy.run_strategy(context, {"entry": True, "exit": True})
        self.assertEqual([], strategy.last_score_cards)
        self.assertEqual(2, len(strategy.last_signals))


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
