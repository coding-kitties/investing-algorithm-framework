import json
from unittest import TestCase
from dataclasses import replace
from unittest.mock import Mock, patch

import pandas as pd

from investing_algorithm_framework import (
    AllOf,
    AnyOf,
    AtLeast,
    Condition,
    ConditionExpression,
    ConfluenceCard,
    EvaluationContext,
    EvidenceGroup,
    Not,
    Operator,
    PrimaryGroup,
    Requirement,
    ScoreRule,
    ScoreType,
    Veto,
    DecisionTrace,
    condition as framework_condition,
)


def condition(indicator, operator, value=None, reference=None, timeframe=None):
    return ConditionExpression(Condition(
        indicator=indicator,
        operator=operator,
        value=value,
        reference=reference,
        timeframe=timeframe,
    ))


class TestConfluenceCard(TestCase):

    def test_condition_factory_preserves_fields_and_evaluation(self):
        expression = framework_condition(
            "close", Operator.CROSS_ABOVE, reference="ema_50",
            timeframe="4h", name="Trend reversal",
        )
        self.assertEqual(ConditionExpression(Condition(
            "close", Operator.CROSS_ABOVE, reference="ema_50",
            timeframe="4h", name="Trend reversal",
        )), expression)
        self.assertTrue(expression.evaluate(EvaluationContext(
            {"4h:close": 105, "4h:ema_50": 100},
            {"4h:close": 95, "4h:ema_50": 100},
        )))
        frame = pd.DataFrame({
            "4h:close": [95, 105], "4h:ema_50": [100, 100],
        })
        self.assertTrue(expression.evaluate_series(frame).iloc[-1])
        card = ConfluenceCard("Factory", PrimaryGroup(AllOf((
            expression, framework_condition("rsi", "gt", value=30),
        ))))
        self.assertEqual(card, ConfluenceCard.from_dict(card.to_dict()))

    def test_condition_factory_reuses_validation_and_public_exports(self):
        from investing_algorithm_framework.domain import condition as domain
        from investing_algorithm_framework.domain.models import (
            condition as model,
        )
        from examples.framework_features.confluence_score_cards import (
            condition as example,
        )

        self.assertIs(framework_condition, domain)
        self.assertIs(framework_condition, model)
        self.assertIs(framework_condition, example)
        for settings in (
            {"indicator": "", "operator": Operator.EQ},
            {"indicator": "rsi", "operator": "invalid"},
            {"indicator": "rsi", "operator": Operator.GT,
             "value": 30, "reference": "other"},
            {"indicator": "rsi", "operator": Operator.BETWEEN,
             "value": [30]},
        ):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    framework_condition(**settings)

    def test_example_long_card_properties_match_signal_sides(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )
        from investing_algorithm_framework import SignalSide

        strategy = ConfluenceEntryStrategy()
        self.assertIs(strategy.long_entry_card,
                      strategy.signal_cards[SignalSide.OPEN_LONG])
        self.assertIs(strategy.long_exit_card,
                      strategy.signal_cards[SignalSide.CLOSE_LONG])

    def test_print_card_shows_group_thresholds_and_rule_weights(self):
        card = self.grouped_card()
        definition = card.to_dict()

        border = "+" + "=" * 50 + "+"
        separator = "+" + "-" * 50 + "+"
        rows = [
            "ConfluenceCard: Grouped reversal",
            "Minimum total score: 7",
            None,
            "Primary: primary (matches >= 2, score >= 5)",
            "  +3  RSI",
            "      rsi > 30",
            "  +3  MACD",
            "      macd > 0",
            None,
            "Secondary: confirmation (score >= 2)",
            "  +2  EMA",
            "      close > 100",
        ]
        self.assertEqual(
            "\n".join([border] + [
                separator if row is None else f"| {row:<48} |"
                for row in rows
            ] + [border]),
            str(card),
        )
        self.assertEqual(definition, card.to_dict())
        self.assertEqual(str(card), str(ConfluenceCard.from_dict(definition)))

    def test_print_card_wraps_long_and_multiline_content_inside_border(self):
        card = replace(
            self.grouped_card(),
            name="Long reversal " * 12 + "\nSecond line\twith tab",
            scoring=(ScoreRule(
                "confirmation_" * 15,
                AllOf(tuple(condition(f"indicator_{index}", Operator.GT, 0)
                            for index in range(10))),
                123.5,
            ),),
        )
        text = str(card)
        lines = text.splitlines()
        self.assertTrue(text.isascii())
        self.assertEqual({78}, {len(line) for line in lines})
        self.assertEqual(lines[0], lines[-1])
        self.assertIn("Second line with tab", " ".join(text.split()))
        self.assertIn("+123.5", text)
        for index in range(10):
            self.assertIn(f"indicator_{index} > 0", text)
        for line in lines[1:-1]:
            self.assertTrue(
                (line.startswith("| ") and line.endswith(" |"))
                or line == "+" + "-" * 76 + "+"
            )

    def test_print_card_explains_logic_optional_evidence_and_hard_gates(self):
        ready = condition("ready", Operator.EQ, True)
        crossing = condition("rsi", Operator.CROSS_ABOVE, 30)
        bearish = condition("macd", Operator.CROSS_BELOW, 0)
        trend = condition("ema_50", Operator.GTE, reference="ema_200",
                          timeframe="4h")
        card = ConfluenceCard(
            name="Explained",
            primary=PrimaryGroup(AtLeast(1, (crossing, bearish))),
            secondary=(EvidenceGroup("support", (
                ScoreRule("Ready", ready, 0),
            )),),
            scoring=(ScoreRule("Penalty", bearish, -2,
                               score_type=ScoreType.NEGATIVE, group="risk"),),
            requirements=(Requirement("Trend", AllOf((trend, ready))),),
            vetoes=(Veto("Blocked", AnyOf((
                Not(ready), condition("rsi", Operator.BETWEEN, (80, 100)),
            ))),),
        )
        with patch.object(ConditionExpression, "evaluate",
                          side_effect=AssertionError("must not evaluate")):
            text = str(card)
        for expected in (
            "Primary: primary (required)",
            "AT LEAST 1 OF (rsi crosses above 30; macd crosses below 0)",
            "Secondary: support (optional)", "  +0  Ready",
            "Additional scoring:", "  -2  Penalty [risk]",
            "Requirements (all must match):",
            "ALL OF (4h:ema_50 >= 4h:ema_200; ready == true)",
            "Vetoes (any match rejects):",
            "ANY OF (NOT (ready == true); 80 <= rsi <= 100)",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_batch_all_operators_and_nested_logic_match_scalar(self):
        frame = pd.DataFrame({
            "value": [2, 3, 5, 4, 1], "reference": [2, 2, 6, 3, 1],
            "4h:value": [2, 3, 5, 4, 1], "4h:reference": [2, 2, 6, 3, 1],
        }, index=pd.date_range("2026-01-01", periods=5))
        expressions = []
        for operator in Operator:
            if operator == Operator.BETWEEN:
                expressions.append(condition("value", operator, (2, 4)))
            else:
                expressions.extend((
                    condition("value", operator, 3),
                    condition("value", operator, reference="reference"),
                    condition("value", operator, reference="reference",
                              timeframe="4h"),
                ))
        above = condition("value", Operator.GT, 3)
        below = condition("value", Operator.LT, reference="reference")
        expressions.extend((
            AllOf((above, Not(below))), AnyOf((above, below)),
            AtLeast(2, (above, below, Not(above))),
        ))
        for expression in expressions:
            with self.subTest(expression=expression):
                actual = expression.evaluate_series(frame)
                for index in range(1, len(frame)):
                    expected = expression.evaluate(EvaluationContext(
                        frame.iloc[index].to_dict(),
                        frame.iloc[index - 1].to_dict(),
                    ))
                    self.assertEqual(expected, actual.iloc[index])
                card = ConfluenceCard("Operator", PrimaryGroup(expression))
                with patch.object(ConfluenceCard, "evaluate",
                                  side_effect=AssertionError("scalar call")):
                    batch = card.evaluate_series(frame)
                pd.testing.assert_series_equal(
                    batch["qualified"], actual.fillna(False).astype(bool),
                    check_names=False,
                )

    def test_batch_empty_frames_and_required_columns(self):
        from investing_algorithm_framework import Expression

        card = ConfluenceCard("Ready", PrimaryGroup(
            condition("value", Operator.CROSS_ABOVE, 3)
        ))
        empty = pd.DataFrame({"value": pd.Series(dtype=float)},
                             index=pd.DatetimeIndex([]))
        self.assertTrue(card.evaluate_series(empty).empty)
        with self.assertRaises(KeyError):
            card.evaluate_series(pd.DataFrame({"typo": [1, 2]}))
        with self.assertRaises(ValueError):
            card.evaluate_series(pd.DataFrame(
                [[1, 2]], columns=["value", "value"]
            ))
        with self.assertRaisesRegex(TypeError, "custom conditions"):
            Expression().evaluate_series(empty)
        nullable = pd.DataFrame({
            "value": pd.Series([pd.NA, 4, 2], dtype="Float64"),
        })
        self.assertEqual([False, False, False],
                         card.evaluate_series(nullable)["qualified"].tolist())

    def test_batch_card_matches_scalar_for_all_available_rows(self):
        ready = condition("close", Operator.GT, reference="ema")
        crossing = condition("rsi", Operator.CROSS_ABOVE, 30)
        card = ConfluenceCard(
            "Batch",
            primary=PrimaryGroup(
                rules=(ScoreRule("Cross", crossing, 3),
                       ScoreRule("Trend", ready, 2)),
                minimum_matches=1, minimum_score=2,
            ),
            secondary=(EvidenceGroup("confirmation", (
                ScoreRule("Ready", ready, 2),
            ), minimum_score=2),),
            scoring=(ScoreRule("Penalty", condition("rsi", Operator.GT, 70),
                               -2, score_type=ScoreType.NEGATIVE),),
            requirements=(Requirement("Liquid", condition(
                "volume", Operator.GT, 0
            )),),
            vetoes=(Veto("Blocked", condition("blocked", Operator.EQ, True)),),
            minimum_score=4,
        )
        dataframe = pd.DataFrame({
            "close": [101, 102, 99, 105, 110], "ema": [100] * 5,
            "rsi": [29, 31, 72, 28, 32], "volume": [10, 10, 10, 0, 10],
            "blocked": [False, False, False, False, True],
        }, index=pd.date_range("2026-01-01", periods=5, tz="UTC"))
        result = card.evaluate_series(dataframe)
        self.assertFalse(result["available"].iloc[0])
        for index in range(1, len(dataframe)):
            scalar = card.evaluate(EvaluationContext(
                dataframe.iloc[index].to_dict(),
                dataframe.iloc[index - 1].to_dict(),
            ))
            self.assertEqual(scalar.score, result["score"].iloc[index])
            self.assertEqual(scalar.qualified, result["qualified"].iloc[index])
        self.assertTrue(result.index.equals(dataframe.index))

    def test_batch_expressions_preserve_unavailable_through_not_and_or(self):
        dataframe = pd.DataFrame({"value": [pd.NA, 3, 5], "ready": [True] * 3})
        unknown = condition("value", Operator.NEQ, 3)
        expression = AnyOf((
            condition("ready", Operator.EQ, True), Not(unknown),
        ))
        result = expression.evaluate_series(dataframe)
        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertEqual([True, True], result.iloc[1:].tolist())
        card = ConfluenceCard("Ready", PrimaryGroup(expression))
        self.assertEqual([False, True, True],
                         card.evaluate_series(dataframe)["qualified"].tolist())

    def grouped_card(self):
        return ConfluenceCard(
            name="Grouped reversal",
            primary=PrimaryGroup(
                rules=(
                    ScoreRule("RSI", condition("rsi", Operator.GT, 30), 3),
                    ScoreRule("MACD", condition("macd", Operator.GT, 0), 3),
                ),
                minimum_matches=2,
                minimum_score=5,
            ),
            secondary=(EvidenceGroup(
                name="confirmation",
                rules=(ScoreRule(
                    "EMA", condition("close", Operator.GT, 100), 2
                ),),
                minimum_score=2,
            ),),
            minimum_score=7,
        )

    def test_group_thresholds_and_total_count_points_once(self):
        result = self.grouped_card().evaluate(EvaluationContext(
            {"rsi": 31, "macd": 1, "close": 110}
        ))
        self.assertTrue(result.qualified)
        self.assertEqual(8, result.score)
        self.assertEqual([6, 2], [group.score for group in result.groups])
        self.assertEqual([2, 1], [group.matches for group in result.groups])
        self.assertEqual(8, sum(item.points for item in result.evaluations))

    def test_each_threshold_can_reject_independently(self):
        card = self.grouped_card()
        cases = (
            replace(card, primary=replace(card.primary, minimum_score=7)),
            replace(card, secondary=(replace(
                card.secondary[0], minimum_score=3
            ),)),
            replace(card, minimum_score=9),
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                result = candidate.evaluate(EvaluationContext(
                    {"rsi": 31, "macd": 1, "close": 110}
                ))
                self.assertEqual(8, result.score)
                self.assertFalse(result.qualified)

    def test_primary_match_count_cannot_be_bought_back(self):
        card = self.grouped_card()
        card = replace(card, primary=replace(card.primary, rules=(
            replace(card.primary.rules[0], points=20), card.primary.rules[1]
        )))
        result = card.evaluate(EvaluationContext(
            {"rsi": 31, "macd": -1, "close": 110}
        ))
        self.assertEqual(22, result.score)
        self.assertFalse(result.primary_triggered)
        self.assertFalse(result.qualified)

    def test_optional_secondary_group_needs_no_matches(self):
        card = self.grouped_card()
        card = replace(card, minimum_score=6, secondary=(replace(
            card.secondary[0], minimum_score=None
        ),))
        result = card.evaluate(EvaluationContext(
            {"rsi": 31, "macd": 1, "close": 90}
        ))
        self.assertTrue(result.qualified)
        self.assertTrue(result.secondary_passed)
        self.assertEqual(6, result.score)

    def test_secondary_match_threshold_with_expression_primary(self):
        card = self.grouped_card()
        card = replace(
            card,
            primary=PrimaryGroup(card.primary.rules[0].expression),
            scoring=card.primary.rules,
            secondary=(replace(
                card.secondary[0], minimum_score=None, minimum_matches=1
            ),),
            minimum_score=6,
        )
        restored = ConfluenceCard.from_dict(json.loads(json.dumps(
            card.to_dict()
        )))
        result = restored.evaluate(EvaluationContext(
            {"rsi": 31, "macd": 1, "close": 90}
        ))
        self.assertTrue(result.primary_triggered)
        self.assertEqual(6, result.score)
        self.assertFalse(result.secondary_passed)
        self.assertFalse(result.qualified)

    def test_group_rules_evaluated_once_and_json_round_trip(self):
        card = self.grouped_card()
        restored = ConfluenceCard.from_dict(json.loads(json.dumps(
            card.to_dict()
        )))
        context = EvaluationContext({"rsi": 31, "macd": 1, "close": 110})
        self.assertEqual(card, restored)
        self.assertEqual(card.evaluate(context), restored.evaluate(context))
        expression = Mock()
        expression.evaluate.return_value = True
        card = replace(card, primary=PrimaryGroup(
            rules=(ScoreRule("Once", expression, 6),)
        ))
        self.assertTrue(card.evaluate(context).qualified)
        expression.evaluate.assert_called_once_with(context)

    def test_group_configuration_validation(self):
        rule = self.grouped_card().primary.rules[0]
        for minimum in (-1, 2, 0.5, True):
            with self.subTest(minimum=minimum), self.assertRaises(ValueError):
                EvidenceGroup("invalid", (rule,), minimum_matches=minimum)
        with self.assertRaises(ValueError):
            PrimaryGroup()
        with self.assertRaises(ValueError):
            PrimaryGroup(expression=rule.expression, rules=(rule,))
        with self.assertRaises(ValueError):
            EvidenceGroup("invalid", (rule,), minimum_score=float("nan"))

    def test_negative_evidence_reduces_group_and_total_scores(self):
        card = self.grouped_card()
        penalty = ScoreRule(
            "Penalty", condition("rsi", Operator.GT, 30), -2,
            score_type=ScoreType.NEGATIVE,
        )
        card = replace(card, secondary=(replace(
            card.secondary[0], rules=card.secondary[0].rules + (penalty,)
        ),))
        restored = ConfluenceCard.from_dict(json.loads(json.dumps(
            card.to_dict()
        )))
        result = restored.evaluate(EvaluationContext(
            {"rsi": 31, "macd": 1, "close": 110}
        ))
        self.assertEqual(6, result.score)
        self.assertEqual(0, result.groups[1].score)
        self.assertEqual(2, result.groups[1].matches)
        self.assertFalse(result.secondary_passed)
        self.assertFalse(result.qualified)

    def test_group_failures_visible_in_json_and_decision_trace(self):
        result = self.grouped_card().evaluate(EvaluationContext(
            {"rsi": 31, "macd": 1, "close": 90}
        ))
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertFalse(payload["secondary_passed"])
        self.assertFalse(payload["groups"][1]["passed"])
        self.assertEqual(2, payload["groups"][1]["minimum_score"])
        trace = DecisionTrace.from_confluence_result(result)
        entries = {
            entry.name: entry.value for entry in trace.entries
            if entry.group == "confirmation"
        }
        self.assertFalse(entries["passed"])
        self.assertEqual(0, entries["score"])
        self.assertEqual(2, entries["minimum_score"])

    def test_strategy_example_emits_signal_with_group_trace(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )
        from investing_algorithm_framework import (
            DECISION_TRACE_METADATA_KEY, SignalSide,
        )

        strategy = ConfluenceEntryStrategy()
        signals = list(strategy.generate_signals(None, {
            "indicators": pd.DataFrame([{"rsi": 29, "macd": -0.1}, {
                "rsi": 31, "macd": 0.2, "stoch": 24,
                "close": 42000, "ema_50": 41000,
                "volume": 900, "average_volume": 1000,
                "trend": "bullish", "volume_confirmed": True,
            }]),
        }))
        self.assertEqual(
            {SignalSide.OPEN_LONG, SignalSide.CLOSE_SHORT},
            {signal.side for signal in signals},
        )
        signal = next(signal for signal in signals
                      if signal.side == SignalSide.OPEN_LONG)
        trace = signal.metadata[DECISION_TRACE_METADATA_KEY]
        self.assertEqual("Long reversal: QUALIFIED (9 / 7)", trace["summary"])
        self.assertTrue(next(
            entry["value"] for entry in trace["entries"]
            if entry["name"] == "Last row confirms bullish setup"
        ))
        self.assertEqual(2, sum(
            entry["name"] == "passed" and entry["value"] is True
            for entry in trace["entries"]
        ))

    def test_sweep_constructor_keeps_variants_and_templates_independent(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy, ENTRY_CONFLUENCE_CARD,
            EXIT_CONFLUENCE_CARD, ENTRY_SHORT_CONFLUENCE_CARD,
            EXIT_SHORT_CONFLUENCE_CARD, build_entry_card, build_exit_card,
        )
        self.assertEqual(ENTRY_CONFLUENCE_CARD, build_entry_card())
        self.assertEqual(EXIT_CONFLUENCE_CARD, build_exit_card())
        self.assertEqual(ENTRY_SHORT_CONFLUENCE_CARD,
                         build_entry_card(short=True))
        self.assertEqual(EXIT_SHORT_CONFLUENCE_CARD,
                         build_exit_card(short=True))
        default = ConfluenceEntryStrategy()
        strict = ConfluenceEntryStrategy(entry_minimum_score=10)
        context = EvaluationContext({
            "rsi": 31, "macd": 0.2, "stoch": 24, "close": 42000,
            "ema_50": 41000, "volume": 900, "average_volume": 1000,
            "confirmed_setup": True,
        }, {"rsi": 29, "macd": -0.1})
        self.assertTrue(default.long_entry_card.evaluate(context).qualified)
        self.assertFalse(strict.long_entry_card.evaluate(context).qualified)
        self.assertEqual(7, default.long_entry_card.minimum_score)
        self.assertEqual(7, ENTRY_CONFLUENCE_CARD.minimum_score)
        self.assertEqual(3, EXIT_CONFLUENCE_CARD.minimum_score)
        self.assertIsNot(default.long_entry_card, strict.long_entry_card)
        self.assertIsNot(
            default.long_entry_card.primary, strict.long_entry_card.primary
        )

    def test_sweep_parameters_and_definitions_are_reconstructible(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )
        metadata = {"experiment": "sweep"}
        strategy = ConfluenceEntryStrategy(
            entry_minimum_score=8, primary_minimum_score=6,
            primary_minimum_matches=1, confirmation_minimum_score=1,
            rsi_oversold=35, rsi_points=4,
            exit_minimum_score=5, rsi_overbought=65,
            short_entry_minimum_score=9, short_exit_minimum_score=6,
            metadata=metadata,
        )
        stored = json.loads(json.dumps(strategy.metadata))
        recreated = ConfluenceEntryStrategy(**stored["confluence_parameters"])
        self.assertEqual(strategy.signal_cards, recreated.signal_cards)
        self.assertEqual(4, len(strategy.signal_cards))
        for side, card in strategy.signal_cards.items():
            self.assertEqual(card, ConfluenceCard.from_dict(
                stored["confluence_cards"][side.value]
            ))
        self.assertEqual({"experiment": "sweep"}, metadata)
        self.assertEqual("sweep", stored["experiment"])
        entry_rsi = strategy.long_entry_card.primary.rules[0]
        self.assertEqual(35, entry_rsi.expression.condition.value)
        self.assertEqual(4, entry_rsi.points)
        exit_rsi = strategy.long_exit_card.primary.rules[0]
        self.assertEqual(65, exit_rsi.expression.condition.value)
        with self.assertRaises(ValueError):
            ConfluenceEntryStrategy(rsi_oversold=80, rsi_overbought=20)

    def test_sweep_all_four_directions(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )
        from investing_algorithm_framework import SignalSide

        strategy = ConfluenceEntryStrategy()
        for current, previous, expected in (
            ({"rsi": 31, "macd": 1, "close": 110},
             {"rsi": 29, "macd": -1},
             {SignalSide.OPEN_LONG, SignalSide.CLOSE_SHORT}),
            ({"rsi": 69, "macd": -1, "close": 90},
             {"rsi": 71, "macd": 1},
             {SignalSide.OPEN_SHORT, SignalSide.CLOSE_LONG}),
        ):
            with self.subTest(current=current):
                values = {
                    "stoch": 40, "ema_50": 100, "volume": 100,
                    "average_volume": 100, "confirmed_setup": True,
                    "confirmed_short_setup": True, **current,
                }
                signals = list(strategy.generate_signals_from_cards(
                    EvaluationContext(values, previous), symbol="BTC"
                ))
                self.assertEqual(expected, {signal.side for signal in signals})

    def test_example_prepares_raw_indicators_without_mutating_input(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )
        import math

        close = [100 + math.sin(index / 3) * 5 for index in range(80)]
        dataframe = pd.DataFrame({
            "close": close,
            "high": [value + 2 for value in close],
            "low": [value - 2 for value in close],
            "volume": [1000] * 80,
        })
        original = dataframe.copy(deep=True)
        prepared = ConfluenceEntryStrategy()._generate_indicators(dataframe)
        self.assertTrue({
            "rsi", "macd", "stoch", "ema_50", "average_volume", "trend",
            "volume_confirmed",
        }.issubset(prepared.columns))
        list(ConfluenceEntryStrategy().generate_signals(
            None, {"indicators": prepared}
        ))
        pd.testing.assert_frame_equal(original, dataframe)

    def test_example_default_vector_series_match_event_prefixes(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )
        from investing_algorithm_framework import SignalSeries, TradingStrategy

        frame = pd.DataFrame({
            "rsi": [29, 31, 71, 69, 29, 31],
            "macd": [-1, 1, 1, -1, -1, 1],
            "stoch": [40] * 6, "ema_50": [100] * 6,
            "close": [90, 110, 110, 90, 90, 110],
            "volume": [100] * 6, "average_volume": [90] * 6,
        }, index=pd.date_range("2026-01-01", periods=6, freq="h", tz="UTC"))
        original = frame.copy(deep=True)
        strategy = ConfluenceEntryStrategy()
        self.assertIs(TradingStrategy.generate_signals,
                      type(strategy).generate_signals)
        self.assertIs(TradingStrategy.generate_signal_series,
                      type(strategy).generate_signal_series)
        series = list(strategy.generate_signal_series({"indicators": frame}))
        self.assertEqual(4, len(series))
        self.assertTrue(all(isinstance(item, SignalSeries) for item in series))
        for index in range(len(frame)):
            events = list(strategy.generate_signals(None, {
                "indicators": frame.iloc[:index + 1],
            }))
            self.assertEqual(
                {item.side for item in series if item.series.iloc[index]},
                {event.side for event in events},
            )
        pd.testing.assert_frame_equal(original, frame)
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.backtest_service import BacktestService
        BacktestService.validate_strategy_for_vector_backtest(strategy)
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.vector_backtest_service import VectorBacktestService
        buy, sell, scale_in, scale_out, short, cover = (
            VectorBacktestService._bucket_signal_series(series)
        )
        for bucket in (buy, sell, short, cover):
            self.assertEqual({"BTC"}, set(bucket))
            self.assertTrue(bucket["BTC"].index.equals(frame.index))
        self.assertIsNone(scale_in)
        self.assertIsNone(scale_out)

    def test_custom_dataframe_condition_checks_only_last_row(self):
        from examples.framework_features.confluence_score_cards import (
            custom_condition,
        )
        dataframe = pd.DataFrame({
            "trend": ["bearish", "bullish"],
            "volume_confirmed": [False, True],
            "unrelated": [None, None],
        }, index=[20, 10])
        original = dataframe.copy(deep=True)
        expected = {"trend": "bullish", "volume_confirmed": True}
        self.assertIs(True, custom_condition(dataframe, expected))
        self.assertIs(False, custom_condition(dataframe.iloc[::-1], expected))
        self.assertIs(False, custom_condition(
            dataframe, {"trend": "bullish", "volume_confirmed": False}
        ))
        pd.testing.assert_frame_equal(original, dataframe)

    def test_custom_dataframe_condition_handles_empty_and_missing_values(self):
        from examples.framework_features.confluence_score_cards import (
            custom_condition,
        )

        self.assertFalse(custom_condition(
            pd.DataFrame(columns=["ready"]), {"ready": True}
        ))
        for value in (None, float("nan"), pd.NA):
            with self.subTest(value=value):
                self.assertFalse(custom_condition(
                    pd.DataFrame({"ready": [value]}), {"ready": True}
                ))
        with self.assertRaises(KeyError):
            custom_condition(pd.DataFrame({"ready": [True]}), {"typo": True})
        with self.assertRaises(ValueError):
            custom_condition(pd.DataFrame({"ready": [True]}), {})

    def test_strategy_example_waits_for_two_rows(self):
        from examples.framework_features.confluence_score_cards import (
            ConfluenceEntryStrategy,
        )

        for rows in ([], [{"rsi": 31}]):
            with self.subTest(rows=rows):
                self.assertEqual([], list(
                    ConfluenceEntryStrategy().generate_signals(
                        None, {"indicators": pd.DataFrame(rows)}
                    )
                ))

    def test_custom_dataframe_all_comparison_operators(self):
        from examples.framework_features.confluence_score_cards import (
            custom_condition,
        )

        cases = (
            (Operator.GT, 5, 6, 5),
            (Operator.GTE, 5, 5, 4),
            (Operator.LT, 5, 4, 5),
            (Operator.LTE, 5, 5, 6),
            (Operator.EQ, "bullish", "bullish", "bearish"),
            (Operator.NEQ, "bullish", "bearish", "bullish"),
            (Operator.BETWEEN, (3, 5), 3, 6),
        )
        for operator, target, matching, failing in cases:
            with self.subTest(operator=operator):
                expression = condition("value", operator, target)
                self.assertIs(True, custom_condition(
                    pd.DataFrame({"value": [matching]}), expression
                ))
                self.assertIs(False, custom_condition(
                    pd.DataFrame({"value": [failing]}), expression
                ))
        self.assertTrue(custom_condition(
            pd.DataFrame({"value": [5]}),
            Condition("value", Operator.BETWEEN, (3, 5)),
        ))

    def test_custom_dataframe_crossings_use_previous_reference(self):
        from examples.framework_features.confluence_score_cards import (
            custom_condition,
        )

        for operator, values, thresholds in (
            (Operator.CROSS_ABOVE, [5, 7], [5, 6]),
            (Operator.CROSS_BELOW, [5, 3], [5, 4]),
        ):
            with self.subTest(operator=operator):
                dataframe = pd.DataFrame({
                    "value": values, "threshold": thresholds,
                }, index=[20, 10])
                reference = condition(
                    "value", operator, reference="threshold"
                )
                self.assertTrue(custom_condition(dataframe, reference))
                self.assertTrue(custom_condition(
                    dataframe, condition("value", operator, 5)
                ))
                self.assertFalse(custom_condition(dataframe.iloc[-1:],
                                                  reference))
                self.assertFalse(custom_condition(dataframe.iloc[::-1],
                                                  reference))
                dataframe.loc[20, "threshold"] = float("nan")
                self.assertFalse(custom_condition(dataframe, reference))
        self.assertFalse(custom_condition(
            pd.DataFrame({"value": [6, 7]}),
            condition("value", Operator.CROSS_ABOVE, 5),
        ))

    def test_custom_dataframe_logical_expressions_and_timeframes(self):
        from examples.framework_features.confluence_score_cards import (
            custom_condition,
        )

        trend = condition("close", Operator.GT, reference="ema")
        oversold = condition("rsi", Operator.LT, 30)
        higher_trend = condition(
            "close", Operator.GTE, reference="ema", timeframe="4h"
        )
        dataframe = pd.DataFrame({
            "close": [110], "ema": [100], "rsi": [40],
            "4h:close": [110], "4h:ema": [105],
        })
        cases = (
            (AllOf((trend, oversold)), False),
            (AnyOf((trend, oversold)), True),
            (Not(oversold), True),
            (Not(trend), False),
            (AtLeast(2, (trend, oversold, higher_trend)), True),
            (AtLeast(3, (trend, oversold, higher_trend)), False),
            (AllOf((higher_trend, AnyOf((trend, oversold)))), True),
        )
        for expression, expected in cases:
            with self.subTest(expression=expression):
                self.assertIs(
                    expected, custom_condition(dataframe, expression)
                )

    def test_custom_dataframe_unavailable_values_fail_closed(self):
        from examples.framework_features.confluence_score_cards import (
            custom_condition,
        )

        dataframe = pd.DataFrame({"ready": [True], "rsi": [pd.NA]})
        ready = condition("ready", Operator.EQ, True)
        unknown = condition("rsi", Operator.NEQ, 30)
        for expression in (unknown, Not(unknown), AnyOf((ready, unknown))):
            with self.subTest(expression=expression):
                self.assertFalse(custom_condition(dataframe, expression))
        self.assertFalse(custom_condition(
            dataframe, condition("ready", Operator.NEQ, None)
        ))
        with self.assertRaises(KeyError):
            custom_condition(dataframe, condition("missing", Operator.GT, 0))
        with self.assertRaises(ValueError):
            custom_condition(
                pd.DataFrame([[1, 2]], columns=["ready", "ready"]), ready
            )
        with self.assertRaises(TypeError):
            custom_condition(dataframe, lambda values: True)

    def test_state_condition_does_not_require_previous_values(self):
        expression = condition("close", Operator.GT, value=100)

        self.assertTrue(expression.evaluate(EvaluationContext({"close": 101})))

    def test_crossing_condition_uses_previous_values(self):
        expression = condition("rsi", Operator.CROSS_ABOVE, value=30)
        context = EvaluationContext(
            values={"rsi": 31}, previous_values={"rsi": 29}
        )

        self.assertTrue(expression.evaluate(context))

    def test_evaluates_primary_requirements_vetoes_and_signed_score(self):
        rsi = condition("rsi", Operator.CROSS_ABOVE, value=30)
        macd = condition("macd", Operator.CROSS_ABOVE, value=0)
        stoch = condition("stoch", Operator.LT, value=20)
        card = ConfluenceCard(
            name="Reversal",
            primary=PrimaryGroup(AtLeast(2, (rsi, macd, stoch))),
            requirements=(Requirement(
                "4h trend bullish",
                condition(
                    "ema_50", Operator.GT,
                    reference="ema_200", timeframe="4h",
                ),
            ),),
            scoring=(
                ScoreRule("RSI reversal", rsi, 3, group="momentum"),
                ScoreRule("MACD reversal", macd, 3, group="momentum"),
                ScoreRule(
                    "Extreme volatility",
                    condition("atr_percentile", Operator.GT, value=95),
                    -2,
                    score_type=ScoreType.NEGATIVE,
                    group="volatility",
                ),
            ),
            vetoes=(Veto(
                "Extreme regime",
                condition("regime", Operator.EQ, value="extreme"),
            ),),
            minimum_score=6,
        )
        context = EvaluationContext(
            values={
                "rsi": 31,
                "macd": 1,
                "stoch": 25,
                "4h:ema_50": 110,
                "4h:ema_200": 100,
                "atr_percentile": 80,
                "regime": "normal",
            },
            previous_values={"rsi": 29, "macd": -1},
        )

        result = card.evaluate(context)

        self.assertTrue(result.qualified)
        self.assertEqual("QUALIFIED", result.decision)
        self.assertEqual(6, result.score)
        self.assertEqual(0, result.score_margin)
        self.assertEqual(
            ["requirement", "primary", "veto", "score", "score", "score"],
            [evaluation.category for evaluation in result.evaluations],
        )

    def test_veto_cannot_be_bought_back_by_score(self):
        always = condition("ready", Operator.EQ, value=True)
        card = ConfluenceCard(
            name="Veto",
            primary=PrimaryGroup(always),
            scoring=(ScoreRule("Strong setup", always, 10),),
            vetoes=(Veto("Blocked", always),),
            minimum_score=7,
        )

        result = card.evaluate(EvaluationContext({"ready": True}))

        self.assertEqual(10, result.score)
        self.assertFalse(result.qualified)

    def test_definition_round_trips_and_result_bridges_to_score_card(self):
        ready = condition("ready", Operator.EQ, value=True)
        card = ConfluenceCard(
            name="Serializable",
            primary=PrimaryGroup(ready),
            scoring=(ScoreRule("Ready", ready, 2, group="setup"),),
            minimum_score=2,
        )

        definition = json.loads(json.dumps(card.to_dict(), sort_keys=True))
        restored = ConfluenceCard.from_dict(definition)
        result = restored.evaluate(EvaluationContext({"ready": True}))
        score_card = DecisionTrace.from_confluence_result(
            result, indicator_snapshot={"ready": True}
        )

        self.assertEqual(card, restored)
        self.assertEqual(
            "Serializable: QUALIFIED (2 / 2)", score_card.summary
        )
        self.assertEqual(
            "QUALIFIED",
            next(entry.value for entry in score_card.entries
                 if entry.name == "decision"),
        )
