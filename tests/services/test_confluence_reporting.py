from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from investing_algorithm_framework import (
    ConfluenceScoreCard, ConfluenceScoreRule, EvaluationContext, Requirement,
    condition,
)
from investing_algorithm_framework.services.confluence_reporting import (
    confluence_report_details,
)
from investing_algorithm_framework.services.run_reports.snapshot import (
    confluence_position_snapshots, confluence_score_snapshots,
)


class TestConfluenceReporting(TestCase):
    def test_records_weights_capacity_and_requirements_without_re_evaluation(self):
        primary = condition("zscore", "lte", value=-2)
        card = ConfluenceScoreCard(
            name="entry",
            rules={
                "zscore": ConfluenceScoreRule(primary, {"primary": 1}),
                "stochastic": ConfluenceScoreRule(
                    condition("stochastic", "lte", value=20), {"secondary": 1},
                ),
                "willr": ConfluenceScoreRule(
                    condition("willr", "lte", value=-80), {"secondary": 1},
                ),
                "rsi": ConfluenceScoreRule(
                    condition("rsi", "lte", value=30), {"secondary": 1},
                ),
            },
            group_thresholds={"primary": 1, "secondary": 2},
            requirements=(Requirement("required_z", primary),),
        )
        result = card.evaluate(EvaluationContext({
            "zscore": -2.68, "stochastic": 16.8, "willr": -74.6, "rsi": 27.4,
        })).to_dict()
        original = deepcopy(result)
        with patch.object(
            type(primary), "evaluate", side_effect=AssertionError("Must not recalculate"),
        ):
            record = confluence_report_details(card, result)
        self.assertEqual(3., record["score"])
        self.assertEqual(4., record["maximum_score"])
        self.assertIsNone(record["overall_minimum_score"])
        self.assertEqual(
            {"primary": 1., "secondary": 3.},
            {group["name"]: group["maximum_score"] for group in record["groups"]},
        )
        rows = {item["name"]: item for item in record["evaluations"]}
        self.assertEqual(1., rows["willr"]["weight"])
        self.assertEqual(0., rows["willr"]["points"])
        self.assertFalse(rows["willr"]["matched"])
        self.assertTrue(rows["zscore"]["required"])
        self.assertEqual(original, result)

    def test_max_aggregation_and_signed_weights_preserve_credited_points(self):
        for aggregation, expected_maximum, expected_score in (
            ("max", 3., 3.), ("sum", 4., 2.),
        ):
            with self.subTest(aggregation=aggregation):
                card = ConfluenceScoreCard(
                    name="entry",
                    rules={
                        name: ConfluenceScoreRule(
                            condition(name, "eq", value=True), {"evidence": weight},
                        )
                        for name, weight in (("a", 1.), ("b", 3.), ("penalty", -2.))
                    },
                    group_thresholds={"evidence": 1},
                    group_aggregation={"evidence": aggregation},
                )
                record = confluence_report_details(card, card.evaluate(
                    EvaluationContext({"a": True, "b": True, "penalty": True}),
                ).to_dict())
                self.assertEqual(expected_maximum, record["maximum_score"])
                self.assertEqual(expected_score, record["score"])
                rows = {item["name"]: item for item in record["evaluations"]}
                self.assertEqual(-2., rows["penalty"]["weight"])
                self.assertEqual(0., rows["penalty"]["maximum_points"])
                if aggregation == "max":
                    self.assertTrue(rows["a"]["matched"])
                    self.assertEqual(0., rows["a"]["points"])

    def test_records_pre_signal_position_and_actual_strength_independently(self):
        strategy = SimpleNamespace(
            symbols=["BTC"], data_sources=[],
            get_scaling_rule=Mock(return_value=SimpleNamespace(max_entries=3)),
        )
        context = SimpleNamespace(get_open_trades=Mock(return_value=[
            SimpleNamespace(filled_amount=1, is_short=False),
            SimpleNamespace(filled_amount=0, is_short=False),
        ]))
        before = confluence_position_snapshots(strategy, context)
        self.assertEqual({
            "side": "long", "long_entries": 1, "short_entries": 0,
            "maximum_entries": 3,
        }, before["BTC"])
        record, = confluence_score_snapshots(
            evaluated=[{
                "symbol": "BTC", "side": "scale_in", "card_id": "scale",
                "score": 3, "maximum_score": 4, "ready": True, "qualified": True,
            }],
            signals=[{
                "symbol": "BTC", "side": "scale_in", "source": "scale",
                "status": "approved", "reason": None, "strength": .4,
            }],
            positions_before=before,
        )
        self.assertEqual(.4, record["signal_strength"])
        before["BTC"]["long_entries"] = 99
        self.assertEqual(1, record["position_before"]["long_entries"])
