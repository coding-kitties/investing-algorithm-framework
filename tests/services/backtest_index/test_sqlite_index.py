"""Tests for :class:`SqliteBacktestIndex` (epic #540 phase 2)."""
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
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


class TestSqliteBacktestIndex(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Schema / lifecycle
    # ------------------------------------------------------------------
    def test_create_initialises_schema(self):
        idx = SqliteBacktestIndex.create(self.index_path)
        try:
            self.assertTrue(os.path.isfile(self.index_path))
            self.assertEqual(len(idx), 0)
        finally:
            idx.close()

    def test_open_creates_file_when_missing(self):
        idx = SqliteBacktestIndex.open(self.index_path)
        try:
            self.assertTrue(os.path.isfile(self.index_path))
        finally:
            idx.close()

    def test_upsert_requires_bundle_path(self):
        with SqliteBacktestIndex.create(self.index_path) as idx:
            row = self.fixture.index_row(bundle_path=None)
            with self.assertRaises(ValueError):
                idx.upsert(row)

    # ------------------------------------------------------------------
    # Round-trip
    # ------------------------------------------------------------------
    def test_round_trip_preserves_identity_and_metrics(self):
        row = self.fixture.index_row(bundle_path="bundle.iafbt")

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert(row)
            self.assertEqual(len(idx), 1)
            (loaded,) = list(idx.iter_rows())

        self.assertIsInstance(loaded, BacktestIndexRow)
        self.assertEqual(loaded.algorithm_id, row.algorithm_id)
        self.assertEqual(loaded.tag, row.tag)
        self.assertEqual(loaded.bundle_path, row.bundle_path)
        self.assertEqual(loaded.number_of_runs, row.number_of_runs)
        self.assertEqual(loaded.parameters, row.parameters)

        # If the fixture has scalar metrics, key ones must round-trip.
        # SQLite stores NaN as NULL, so treat NaN/None as equivalent.
        if row.summary_metrics is not None:
            import math

            self.assertIsNotNone(loaded.summary_metrics)
            for name in ("sharpe_ratio", "total_net_gain"):
                got = getattr(loaded.summary_metrics, name, None)
                exp = getattr(row.summary_metrics, name, None)
                if isinstance(exp, float) and math.isnan(exp):
                    self.assertIsNone(got)
                else:
                    self.assertEqual(got, exp)

    def test_upsert_replaces_on_duplicate_bundle_path(self):
        row = self.fixture.index_row(bundle_path="dup.iafbt")
        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert(row)

            # Mutate algorithm_id and re-upsert \u2014 should not duplicate.
            row.algorithm_id = "new_algo"
            idx.upsert(row)

            self.assertEqual(len(idx), 1)
            (loaded,) = list(idx.iter_rows())
            self.assertEqual(loaded.algorithm_id, "new_algo")

    def test_upsert_many_writes_all(self):
        rows = []
        for i in range(3):
            r = self.fixture.index_row(bundle_path=f"b{i}.iafbt")
            r.algorithm_id = f"algo_{i}"
            rows.append(r)

        with SqliteBacktestIndex.create(self.index_path) as idx:
            n = idx.upsert_many(rows)
            self.assertEqual(n, 3)
            self.assertEqual(len(idx), 3)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def test_query_with_where_clause(self):
        rows = []
        for i in range(3):
            r = self.fixture.index_row(bundle_path=f"q{i}.iafbt")
            r.algorithm_id = "alpha" if i == 0 else "beta"
            rows.append(r)

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(rows)
            hits = idx.query("algorithm_id = ?", ("alpha",))
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].bundle_path, "q0.iafbt")

    # ------------------------------------------------------------------
    # Build from real bundle on disk
    # ------------------------------------------------------------------
    def test_index_built_from_bundle_uses_summary_only_path(self):
        bundle_path = os.path.join(self.tmp, "report" + BUNDLE_EXT)
        save_bundle(self.fixture, bundle_path)

        # Open the bundle in summary_only mode — mirrors what the CLI
        # does.
        bt = Backtest.open(bundle_path, summary_only=True)
        row = bt.index_row(bundle_path=bundle_path)

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert(row)
            (loaded,) = list(idx.iter_rows())

        self.assertEqual(loaded.bundle_path, bundle_path)
        self.assertEqual(loaded.algorithm_id, self.fixture.algorithm_id)
