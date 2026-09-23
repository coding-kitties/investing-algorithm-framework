from importlib.util import find_spec
from unittest import TestCase, skipUnless
from unittest.mock import patch

import numpy as np
import pandas as pd

from investing_algorithm_framework import (
    AllOf, AnyOf, AtLeast, ConfluenceCard, EvidenceGroup, Not, Operator,
    PrimaryGroup, Requirement, ScoreRule, ScoreType, Veto, condition,
)
from investing_algorithm_framework.domain.models.confluence_native import (
    NativeConfluenceUnsupported,
)


class TestNativeDispatch(TestCase):
    def test_missing_extension_falls_back_only_when_requested(self):
        card = ConfluenceCard("fallback", PrimaryGroup(
            condition("value", "gt", value=0)
        ))
        frame = pd.DataFrame({"value": [1.0, np.nan, -1.0]})
        with patch(
            "investing_algorithm_framework.domain.models."
            "confluence_native._compile", side_effect=ImportError("missing"),
        ) as compile_card:
            expected = card.evaluate_series(frame)
            compile_card.assert_not_called()
            pd.testing.assert_frame_equal(
                expected, card.evaluate_series(frame, backend="auto")
            )
            with self.assertRaises(ImportError):
                card.evaluate_series(frame, backend="rust")
        with self.assertRaises(ValueError):
            card.evaluate_series(frame, backend="typo")

    def test_native_execution_errors_are_not_hidden(self):
        card = ConfluenceCard("error", PrimaryGroup(
            condition("value", "gt", value=0)
        ))
        with patch(
            "investing_algorithm_framework.domain.models."
            "confluence_native.evaluate_native_card",
            side_effect=RuntimeError("kernel error"),
        ), self.assertRaisesRegex(RuntimeError, "kernel error"):
            card.evaluate_series(
                pd.DataFrame({"value": [1.0]}), backend="auto"
            )


@skipUnless(find_spec("iaf_confluence_native"), "Rust wheel not installed")
class TestNativeConfluence(TestCase):
    def assert_parity(self, card, frame):
        pd.testing.assert_frame_equal(
            card.evaluate_series(frame),
            card.evaluate_series(frame, backend="rust"),
            check_exact=True,
        )

    def test_all_operators_nulls_infinities_crossings_and_empty_frames(self):
        frame = pd.DataFrame({
            "value": [np.nan, 2., 2., 3., np.inf, -np.inf, 0., np.nan, 4.],
            "reference": [1., 2., 3., 3., np.inf, 0., -np.inf, 1., 2.],
        }, index=pd.date_range("2026-01-01", periods=9, tz="UTC"))
        frame["4h:value"] = frame["value"]
        frame["4h:reference"] = frame["reference"]
        for operator in Operator:
            settings = ([{"value": (0, 3)}] if operator == Operator.BETWEEN
                        else [{"value": 2}, {"reference": "reference"},
                              {"reference": "reference", "timeframe": "4h"}])
            for kwargs in settings:
                with self.subTest(operator=operator, settings=kwargs):
                    card = ConfluenceCard("operator", PrimaryGroup(
                        condition("value", operator, **kwargs)
                    ))
                    self.assert_parity(card, frame)
                    self.assert_parity(card, frame.iloc[:0])
                    self.assert_parity(card, frame.astype("Float64"))

    def test_nested_logic_groups_and_large_rule_counts(self):
        above = condition("value", "gt", value=0)
        below = condition("value", "lt", reference="reference")
        expression = AtLeast(2, (
            AnyOf((above, below)), Not(below), AllOf((above, Not(below))),
        ))
        card = ConfluenceCard(
            "groups", PrimaryGroup(rules=(
                ScoreRule("above", above, 0.1),
                ScoreRule("nested", expression, 0.2),
            ), minimum_matches=1, minimum_score=0.1),
            secondary=(EvidenceGroup("secondary", (
                ScoreRule("below", below, 0.3),
            )),),
            scoring=tuple(ScoreRule("penalty", below, -0.1, ScoreType.NEGATIVE)
                          for _ in range(130)),
            requirements=(Requirement("required", above),),
            vetoes=(Veto("veto", below),), minimum_score=0.2,
        )
        random = np.random.default_rng(42)
        frame = pd.DataFrame(random.normal(size=(300, 2)),
                             columns=["value", "reference"])
        frame.iloc[::13, 0] = np.nan
        self.assert_parity(card, frame)
        self.assert_parity(ConfluenceCard(
            "nested", PrimaryGroup(expression)
        ), frame)

    def test_unsupported_types_do_not_lose_integer_precision(self):
        card = ConfluenceCard("ints", PrimaryGroup(
            condition("value", "gt", value=2 ** 53)
        ))
        frames = [pd.DataFrame({"value": [2 ** 53, 2 ** 53 + 1]}),
                  pd.DataFrame({"value": [True, False]})]
        for frame in frames:
            with self.assertRaises(NativeConfluenceUnsupported):
                card.evaluate_series(frame, backend="rust")
            pd.testing.assert_frame_equal(
                card.evaluate_series(frame),
                card.evaluate_series(frame, backend="auto"),
            )
        string_card = ConfluenceCard("strings", PrimaryGroup(
            condition("value", "eq", value="ready")
        ))
        frame = pd.DataFrame({"value": ["ready", "waiting"]})
        pd.testing.assert_frame_equal(string_card.evaluate_series(frame),
                                      string_card.evaluate_series(
                                          frame, backend="auto"))

    def test_float_constants_roundtrip_and_chunk_overlap(self):
        random = np.random.default_rng(19)
        for threshold in random.uniform(-1e100, 1e100, 100):
            card = ConfluenceCard("exact", PrimaryGroup(
                condition("value", "eq", value=float(threshold))
            ))
            self.assert_parity(card, pd.DataFrame({"value": [threshold]}))
        card = ConfluenceCard("cross", PrimaryGroup(
            condition("value", "cross_above", value=2)
        ))
        frame = pd.DataFrame({"value": [1., 3., 2., 4., np.nan, 3.]})
        whole = card.evaluate_series(frame, backend="rust")
        overlapped = card.evaluate_series(frame.iloc[2:], backend="rust")
        pd.testing.assert_frame_equal(whole.iloc[3:], overlapped.iloc[1:])

    def test_shape_validation_and_missing_columns(self):
        from iaf_confluence_native import CompiledCard
        import json

        card = ConfluenceCard("shape", PrimaryGroup(
            condition("value", "gt", value=0)
        ))
        compiled = CompiledCard(json.dumps(card.to_dict()))
        for columns, rows in (([], 2), ([b"short"], 2)):
            with self.assertRaises(ValueError):
                compiled.evaluate(columns, rows)
        with self.assertRaises(KeyError):
            card.evaluate_series(pd.DataFrame({"typo": [1.]}), backend="auto")
