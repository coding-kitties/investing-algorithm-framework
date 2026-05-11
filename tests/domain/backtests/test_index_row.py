"""Tests for the Tier-1 :class:`BacktestIndexRow` contract (epic #540).

These tests verify that:

* ``Backtest.index_row()`` produces a typed row with the right fields.
* The flat-dict round-trip is lossless for canonical scalar fields.
* The row can be built from a bundle opened with ``summary_only=True``
  \u2014 i.e. without decoding any v2 Parquet metric blobs. This is the
  fast read path the tiered-storage indexer relies on.
"""
import os
import shutil
import tempfile
from unittest import TestCase

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestIndexRow,
    BUNDLE_EXT,
)
from investing_algorithm_framework.domain.backtesting.bundle import (
    save_bundle,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


class TestBacktestIndexRow(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # In-memory derivation
    # ------------------------------------------------------------------
    def test_index_row_has_expected_identity(self):
        row = self.fixture.index_row(bundle_path="/tmp/x.iafbt")

        self.assertIsInstance(row, BacktestIndexRow)
        self.assertEqual(row.algorithm_id, self.fixture.algorithm_id)
        self.assertEqual(row.tag, self.fixture.tag)
        self.assertEqual(row.bundle_path, "/tmp/x.iafbt")
        self.assertEqual(
            row.number_of_runs, len(self.fixture.backtest_runs or [])
        )
        # summary_metrics should be the live BacktestSummaryMetrics dataclass
        self.assertIs(row.summary_metrics, self.fixture.backtest_summary)

    def test_to_flat_dict_carries_summary_prefix(self):
        row = self.fixture.index_row(bundle_path="bundle.iafbt")
        flat = row.to_flat_dict()

        # Identity columns are present and unprefixed.
        self.assertEqual(flat["algorithm_id"], self.fixture.algorithm_id)
        self.assertEqual(flat["bundle_path"], "bundle.iafbt")

        # Summary-metric scalars are emitted with the canonical prefix.
        if self.fixture.backtest_summary is not None:
            summary_keys = [
                k for k in flat if k.startswith("summary.")
            ]
            self.assertGreater(
                len(summary_keys), 0,
                "expected at least one summary.* scalar column",
            )

    def test_flat_dict_round_trip(self):
        import math

        row = self.fixture.index_row(bundle_path="bundle.iafbt")
        flat = row.to_flat_dict()
        restored = BacktestIndexRow.from_flat_dict(flat)

        self.assertEqual(restored.algorithm_id, row.algorithm_id)
        self.assertEqual(restored.tag, row.tag)
        self.assertEqual(restored.bundle_path, row.bundle_path)
        self.assertEqual(restored.number_of_runs, row.number_of_runs)
        self.assertEqual(restored.parameters, row.parameters)

        # Scalar metrics that survived the flat hop should match.
        if row.summary_metrics is not None:
            self.assertIsNotNone(restored.summary_metrics)
            original = row.summary_metrics.to_dict()
            restored_dict = restored.summary_metrics.to_dict()
            for k, v in original.items():
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    if isinstance(v, str) or v is None:
                        self.assertEqual(restored_dict.get(k), v)
                    continue
                rv = restored_dict.get(k)
                if isinstance(v, float) and math.isnan(v):
                    self.assertTrue(
                        isinstance(rv, float) and math.isnan(rv)
                    )
                else:
                    self.assertEqual(rv, v)

    def test_unknown_columns_land_in_extras(self):
        row = BacktestIndexRow.from_flat_dict({
            "algorithm_id": "a1",
            "summary.sharpe_ratio": 1.5,
            "extras.custom": "hello",
            "totally_unknown": 7,
        })
        self.assertEqual(row.algorithm_id, "a1")
        self.assertEqual(row.extras.get("custom"), "hello")
        self.assertEqual(row.extras.get("totally_unknown"), 7)

    # ------------------------------------------------------------------
    # Fast-path: build row from a summary-only bundle load
    # ------------------------------------------------------------------
    def test_index_row_from_summary_only_bundle(self):
        path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        save_bundle(self.fixture, path)

        # summary_only=True skips Parquet metric-blob decoding \u2014
        # the index row must still build without error.
        loaded = Backtest.open(path, summary_only=True)
        row = loaded.index_row(bundle_path=path)

        self.assertEqual(row.algorithm_id, self.fixture.algorithm_id)
        self.assertEqual(row.bundle_path, path)
        self.assertEqual(
            row.number_of_runs, len(self.fixture.backtest_runs or [])
        )

        # Flat dict shape must also work in the summary-only path.
        flat = row.to_flat_dict()
        self.assertEqual(flat["algorithm_id"], self.fixture.algorithm_id)
