import json
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

import numpy as np
import pandas as pd

from investing_algorithm_framework import (
    AllOf, AnyOf, AtLeast, ConfluenceScoreCard, ConfluenceScoreRule,
    DecisionTrace, EvaluationContext, Expression, Not, Requirement, Rule,
    Schedule, SignalSide, Threshold, TimeUnit, TradingStrategy, Veto, condition,
)
from investing_algorithm_framework.domain.backtesting.records import (
    CardDefinition, ConfluenceEvaluation,
)
from investing_algorithm_framework.domain.models.confluence_native import (
    NativeConfluenceUnsupported,
)


def card(**changes):
    definition = dict(
        name="Named entry",
        rules={
            "normal_z": ConfluenceScoreRule(condition("z", "lte", value=-2), {"primary": 1}),
            "extreme_z": ConfluenceScoreRule(condition("z", "lte", value=-3), {"primary": 3}),
            "rsi_confirmation": ConfluenceScoreRule(condition("rsi", "lte", value=30), {"secondary": 1}),
        },
        group_thresholds={"primary": 1, "secondary": 1},
        group_aggregation={"primary": "max", "secondary": "sum"},
        override_triggers=AnyOf(Rule("extreme_z"), Threshold("primary", 3)),
        requirements=(Requirement("eligible", condition("eligible", "eq", value=True)),),
        vetoes=(Veto("blocked", condition("blocked", "eq", value=True)),),
    )
    return ConfluenceScoreCard(**(definition | changes))


def context(z=-2, rsi=30, eligible=True, blocked=False):
    return EvaluationContext(dict(z=z, rsi=rsi, eligible=eligible, blocked=blocked))


class TestNamedScoring(TestCase):
    def test_normal_override_and_inclusive_thresholds(self):
        for z, rsi, score, normal, override in (
            (-2, 30, 2, True, False),
            (-2, 31, 1, False, False),
            (-3, 31, 3, False, True),
            (-3, 30, 4, True, True),
            (-1, 30, 1, False, False),
        ):
            with self.subTest(z=z, rsi=rsi):
                result = card().evaluate(context(z, rsi))
                self.assertEqual(result.score, score)
                self.assertEqual(result.qualified, normal or override)
                paths = {e.name: e.matched for e in result.evaluations if e.group == "qualification"}
                self.assertEqual(paths, {"normal_path": normal, "override_path": override})
                self.assertEqual(result.score, sum(item.points for item in result.evaluations))
                if z == -3:
                    normal_rule = next(e for e in result.evaluations if e.name == "normal_z")
                    self.assertTrue(normal_rule.matched)
                    self.assertEqual(normal_rule.points, 0)

    def test_overrides_cannot_bypass_requirements_or_vetoes(self):
        for eligible, blocked in ((False, False), (True, True), (False, True)):
            with self.subTest(eligible=eligible, blocked=blocked):
                result = card().evaluate(context(-3, 80, eligible, blocked))
                self.assertTrue(result.primary_triggered)
                self.assertFalse(result.qualified)
                self.assertEqual(result.requirements_passed, eligible)
                self.assertEqual(result.veto_triggered, blocked)

    def test_override_only_and_nested_reference_expressions(self):
        definition = card(
            group_thresholds={},
            override_triggers=AnyOf(
                AllOf(Rule("normal_z"), Threshold("secondary", 1)),
                AtLeast(1, (Rule("extreme_z"), Not(Rule("normal_z")))),
            ),
        )
        self.assertTrue(definition.evaluate(context(-2, 30)).qualified)
        self.assertFalse(definition.evaluate(context(-2, 31)).qualified)
        self.assertTrue(definition.evaluate(context(-3, 31)).qualified)

    def test_multi_group_weights_negative_evidence_and_max_ties(self):
        ready = condition("ready", "eq", value=True)
        definition = ConfluenceScoreCard(
            "Signed scores", {
                "z_first": ConfluenceScoreRule(ready, {"p": 2, "s": -1}),
                "a_second": ConfluenceScoreRule(ready, {"p": 2, "s": -2}),
            },
            group_thresholds={"p": 2, "s": -3},
            group_aggregation={"p": "max", "s": "sum"},
        )
        result = definition.evaluate(EvaluationContext({"ready": True}))
        self.assertTrue(result.qualified)
        self.assertEqual(result.score, -1)
        points = {(e.group, e.name): e.points for e in result.evaluations if e.group in ("p", "s")}
        self.assertEqual(points["p", "z_first"], 2)
        self.assertEqual(points["p", "a_second"], 0)
        self.assertEqual(points["s", "a_second"], -2)
        negative_max = replace(definition, group_aggregation={"p": "max", "s": "max"})
        self.assertEqual(negative_max.evaluate(EvaluationContext({"ready": True})).score, 1)
        pd.testing.assert_frame_equal(
            negative_max.evaluate_series(pd.DataFrame({"ready": [True]})),
            pd.DataFrame({"score": [1.0], "available": [True], "qualified": [True]}),
        )

    def test_predicates_evaluated_once_even_for_multiple_groups_and_references(self):
        calls = []

        class Counted(Expression):
            def evaluate(self, _context):
                calls.append(1)
                return True

        definition = ConfluenceScoreCard(
            "One evaluation",
            {"one": ConfluenceScoreRule(Counted(), {"p": 1, "s": 2})},
            {"p": 1}, override_triggers=AllOf(Rule("one"), Threshold("s", 2)),
        )
        definition.evaluate(EvaluationContext({}))
        self.assertEqual(calls, [1])

    def test_validation_rejects_unknown_references_cycles_and_bad_weights(self):
        invalid = (
            lambda: card(rules={}),
            lambda: card(rules={"score": next(iter(card().rules.values()))}),
            lambda: card(group_aggregation={"primary": "median"}),
            lambda: card(group_thresholds={"unknown": 1}),
            lambda: card(group_thresholds={"primary": 4}),
            lambda: card(override_triggers=Rule("missing")),
            lambda: card(override_triggers=Threshold("missing", 1)),
            lambda: card(override_triggers=Threshold("primary", 4)),
            lambda: card(group_thresholds={}, override_triggers=None),
            lambda: ConfluenceScoreRule(Rule("cycle"), {"p": 1}),
            lambda: ConfluenceScoreRule(condition("x", "gt", value=0), {"p": float("nan")}),
            lambda: ConfluenceScoreRule(condition("x", "gt", value=0), {"p": True}),
            lambda: card(requirements=(Requirement("bad", Rule("normal_z")),)),
            lambda: card(vetoes=(Requirement("wrong", condition("x", "gt", value=0)),)),
        )
        for create in invalid:
            with self.subTest(create=create), self.assertRaises((ValueError, TypeError)):
                create()
        with self.assertRaisesRegex(ValueError, "require"):
            Rule("normal_z").evaluate(context())
        with self.assertRaisesRegex(ValueError, "require"):
            Threshold("primary", 1).evaluate_series(pd.DataFrame({"x": [1]}))

    def test_serialization_formatting_immutability_and_public_exports(self):
        import investing_algorithm_framework.domain as domain
        import investing_algorithm_framework.domain.models as models

        for name in ("ConfluenceScoreCard", "ConfluenceScoreRule", "Rule", "Threshold"):
            self.assertIs(getattr(domain, name), getattr(models, name))
        definition = card()
        restored = ConfluenceScoreCard.from_dict(json.loads(json.dumps(definition.to_dict(), sort_keys=True)))
        self.assertEqual(restored, definition)
        self.assertEqual(restored.evaluate(context()).to_dict(), definition.evaluate(context()).to_dict())
        with self.assertRaises(TypeError):
            definition.rules["new"] = definition.rules["normal_z"]
        with self.assertRaises(TypeError):
            definition.rules["normal_z"].group_weights["primary"] = 5
        with self.assertRaisesRegex(ValueError, "version"):
            ConfluenceScoreCard.from_dict({**definition.to_dict(), "confluence_score_card_version": 99})
        for order in ([], ["normal_z", "normal_z"], [{}], "normal_z"):
            with self.subTest(order=order), self.assertRaises(ValueError):
                ConfluenceScoreCard.from_dict({
                    **definition.to_dict(), "rule_order": order,
                })
        self.assertIn("score >= 1", str(definition))
        self.assertIn("Score(primary) >= 3", str(definition))
        self.assertIn("no veto", str(definition))

    def test_existing_logical_constructor_forms_still_work(self):
        a = condition("z", "lt", value=0)
        b = condition("rsi", "lt", value=50)
        self.assertEqual(AnyOf(a, b), AnyOf((a, b)))
        self.assertEqual(AllOf(a, b), AllOf(expressions=(a, b)))
        with self.assertRaises(ValueError):
            AnyOf()


class TestNamedBatchAndRecords(TestCase):
    def test_unweighted_gate_preserves_evidence_records_and_batch_results(self):
        definition = ConfluenceScoreCard(
            "gate-only rule",
            rules={
                "trigger": ConfluenceScoreRule(
                    condition("z", "lt", value=-2), {"primary": 1},
                ),
                "bearish": ConfluenceScoreRule(
                    condition("trend", "eq", value=0), {},
                ),
            },
            group_thresholds={"primary": 1},
            vetoes=(Veto("bearish_market", condition("trend", "eq", value=0)),),
        )
        schema = CardDefinition.from_card(definition)
        self.assertIn("rules/1/match", [slot.path for slot in schema.slots()])
        frame = pd.DataFrame({
            "z": [-3., -3., -1.], "trend": [1., 0., 1.],
        })
        batch = definition.evaluate_series(frame)
        self.assertEqual(batch["qualified"].tolist(), [True, False, False])
        for i, values in frame.iterrows():
            result = definition.evaluate(EvaluationContext(values.to_dict()))
            self.assertEqual(result.qualified, bool(batch.loc[i, "qualified"]))
            self.assertEqual(result.score, batch.loc[i, "score"])
            self.assertEqual([group.name for group in result.groups], ["primary"])
            unweighted = next(item for item in result.evaluations if item.name == "bearish")
            self.assertEqual(unweighted.points, 0)
            self.assertIsNone(unweighted.group)
            record = ConfluenceEvaluation.from_result(
                schema, result, attempt_id="unweighted", sequence=i,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                symbol_id="BTC", strategy_id="gates",
            )
            self.assertEqual(record.to_result(schema).to_dict(), result.to_dict())
            self.assertEqual(record, ConfluenceEvaluation.from_record(record.to_record(schema), schema))
            self.assertEqual(
                record.to_trace(schema).to_dict(),
                DecisionTrace.from_confluence_result(result).to_dict(),
            )

    def test_scalar_pandas_auto_parity_and_fail_closed_missing_inputs(self):
        definition = card(override_triggers=AnyOf(
            AllOf(Rule("normal_z"), Threshold("secondary", 1)),
            Rule("extreme_z"),
        ))
        frame = pd.DataFrame({
            "z": [-2., -2., -3., -3., np.nan, -3., -3.],
            "rsi": [30., 31., 80., 20., 30., np.nan, 80.],
            "eligible": [True, True, True, True, True, True, False],
            "blocked": [False, False, False, True, False, False, False],
        }, index=pd.date_range("2026-01-01", periods=7, tz="UTC"))
        vector = definition.evaluate_series(frame)
        self.assertEqual(vector["qualified"].tolist(), [True, False, True, False, False, False, False])
        self.assertEqual(vector["available"].tolist(), [True, True, True, True, False, False, True])
        for index, values in frame.iterrows():
            if vector.loc[index, "available"]:
                result = definition.evaluate(EvaluationContext(values.to_dict()))
                self.assertEqual(result.qualified, bool(vector.loc[index, "qualified"]))
                self.assertEqual(result.score, vector.loc[index, "score"])
        pd.testing.assert_frame_equal(vector, definition.evaluate_series(frame, backend="auto"))
        with self.assertRaisesRegex(NativeConfluenceUnsupported, "Python"):
            definition.evaluate_series(frame, backend="rust")
        self.assertTrue(definition.evaluate_series(frame.iloc[:0]).empty)
        with self.assertRaises(KeyError):
            definition.evaluate_series(frame.drop(columns="z"))

    def test_crossing_history_and_override_conditions(self):
        definition = card(
            rules={
                "cross": ConfluenceScoreRule(condition("z", "cross_below", value=-2), {"p": 1}),
            },
            group_thresholds={"p": 1}, group_aggregation={},
            override_triggers=condition("rsi", "lt", value=10),
        )
        frame = pd.DataFrame({
            "z": [-1., -3., -4., -1., -3.], "rsi": [5., 30., 30., 30., 30.],
            "eligible": [True] * 5, "blocked": [False] * 5,
        })
        batch = definition.evaluate_series(frame)
        self.assertEqual(batch["qualified"].tolist(), [False, True, False, False, True])
        for index in range(1, len(frame)):
            result = definition.evaluate(EvaluationContext(frame.iloc[index].to_dict(), frame.iloc[index - 1].to_dict()))
            self.assertEqual(result.qualified, bool(batch.loc[index, "qualified"]))

    def test_native_direct_dispatch_rejects_the_new_definition(self):
        from investing_algorithm_framework.domain.models.confluence_native import evaluate_native_card

        # Even direct low-level dispatch must not hand the named schema to an old kernel.
        with self.assertRaises(NativeConfluenceUnsupported):
            evaluate_native_card(card(), pd.DataFrame({"z": [-3.], "rsi": [80.]}))

    def test_compact_record_and_trace_roundtrip_preserve_paths_and_contributions(self):
        for values in (context(-2, 30), context(-3, 80), context(-3, 80, blocked=True)):
            definition = card()
            result = definition.evaluate(values)
            schema = CardDefinition.from_card(definition)
            record = ConfluenceEvaluation.from_result(
                schema, result, attempt_id="named", sequence=1,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                symbol_id="BTC", strategy_id="named",
            )
            self.assertEqual(record.to_result(schema).to_dict(), result.to_dict())
            self.assertEqual(record, ConfluenceEvaluation.from_record(record.to_record(schema), schema))
            self.assertEqual(record.to_trace(schema).to_dict(), DecisionTrace.from_confluence_result(result).to_dict())
            secondary = next(group for group in result.groups if group.name == "secondary")
            self.assertEqual(secondary.passed, values.values["rsi"] <= 30)

    def test_canonical_records_preserve_max_tie_rule_order(self):
        definition = card(
            rules={
                "z_first": ConfluenceScoreRule(condition("z", "lt", value=0), {"p": 1}),
                "a_second": ConfluenceScoreRule(condition("z", "lt", value=0), {"p": 1}),
            },
            group_thresholds={"p": 1}, group_aggregation={"p": "max"}, override_triggers=None,
        )
        restored = CardDefinition.from_card(definition).to_card()
        self.assertEqual(list(restored.rules), ["z_first", "a_second"])
        self.assertEqual(restored.evaluate(context()).to_dict(), definition.evaluate(context()).to_dict())

    def test_framework_strategy_default_event_and_vector_hooks_accept_named_cards(self):
        class NamedStrategy(TradingStrategy):
            def prepare_signal_data(self, data):
                return {"BTC": data["prices"]}

        strategy = NamedStrategy(
            signal_cards={SignalSide.OPEN_LONG: card()},
            schedule=Schedule.every(1, TimeUnit.HOUR),
        )
        frame = pd.DataFrame({
            "z": [-2., -2., -3.], "rsi": [30., 80., 80.],
            "eligible": [True] * 3, "blocked": [False] * 3,
        }, index=pd.date_range("2026-01-01", periods=3, tz="UTC"))
        vector = list(strategy.generate_signal_series({"prices": frame}))
        self.assertEqual(vector[0].series.tolist(), [True, False, True])
        for offset in range(len(frame)):
            signals = list(strategy.generate_signals(None, {"prices": frame.iloc[:offset + 1]}))
            self.assertEqual(bool(signals), bool(vector[0].series.iloc[offset]))

    def test_auto_does_not_hide_unrelated_evaluation_errors(self):
        with patch(
            "investing_algorithm_framework.domain.models.confluence_frame._expression",
            side_effect=RuntimeError("bad predicate"),
        ), self.assertRaisesRegex(RuntimeError, "bad predicate"):
            card().evaluate_series(pd.DataFrame({"z": [-3.]}), backend="auto")
