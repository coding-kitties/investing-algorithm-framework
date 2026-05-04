"""Unit tests for the Pipeline base class introspection.

See ``investing_algorithm_framework/domain/pipeline/pipeline.py`` and
``docs/design/pipeline-api.md`` (Phase 1, #501).
"""
from __future__ import annotations

import unittest

from investing_algorithm_framework import (
    AverageDollarVolume,
    Pipeline,
    Returns,
    SMA,
)


class _Screener(Pipeline):
    dollar_volume = AverageDollarVolume(window=5)
    momentum = Returns(window=3)
    universe = dollar_volume.top(2)
    alpha = momentum.rank(mask=universe)


class TestPipelineIntrospection(unittest.TestCase):

    def test_pipeline_collects_columns_excluding_universe(self):
        cols = _Screener.get_columns()
        self.assertEqual(
            list(cols.keys()), ["dollar_volume", "momentum", "alpha"]
        )
        self.assertIs(_Screener.get_universe(), _Screener.universe)

    def test_pipeline_required_columns_union(self):
        required = _Screener.required_columns()
        # AverageDollarVolume needs close+volume, Returns needs close
        self.assertIn("close", required)
        self.assertIn("volume", required)

    def test_pipeline_required_window_is_max(self):
        self.assertEqual(_Screener.required_window(), 5)

    def test_pipeline_name_defaults_to_class_name(self):
        self.assertEqual(_Screener.name(), "_Screener")

    def test_pipeline_with_no_columns_raises(self):
        with self.assertRaisesRegex(TypeError, "declares no factor columns"):
            class _Empty(Pipeline):
                pass

    def test_pipeline_universe_must_be_filter(self):
        with self.assertRaisesRegex(TypeError, "must be a Filter"):
            class _BadUniverse(Pipeline):
                momentum = Returns(window=3)
                # Returns is a Factor, not a Filter
                universe = momentum

    def test_pipeline_inheritance_collects_parent_columns(self):
        class _Child(_Screener):
            sma = SMA(window=4)

        cols = _Child.get_columns()
        # Child columns + parent columns
        self.assertIn("sma", cols)
        self.assertIn("dollar_volume", cols)
        self.assertIn("momentum", cols)
        self.assertIn("alpha", cols)


if __name__ == "__main__":
    unittest.main()
