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
            row = self.fixture.index_rows(bundle_path=None)[0]
            with self.assertRaises(ValueError):
                idx.upsert(row)

    # ------------------------------------------------------------------
    # Round-trip
    # ------------------------------------------------------------------
    def test_round_trip_preserves_identity_and_metrics(self):
        row = self.fixture.index_rows(bundle_path="bundle.iafbt")[0]

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
        row = self.fixture.index_rows(bundle_path="dup.iafbt")[0]
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
            r = self.fixture.index_rows(bundle_path=f"b{i}.iafbt")[0]
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
            r = self.fixture.index_rows(bundle_path=f"q{i}.iafbt")[0]
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
        row = bt.index_rows(bundle_path=bundle_path)[0]

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert(row)
            (loaded,) = list(idx.iter_rows())

        self.assertEqual(loaded.bundle_path, bundle_path)
        self.assertEqual(loaded.algorithm_id, self.fixture.algorithm_id)


class TestSqliteBacktestIndexV3Schema(TestCase):
    """Stage 5 regression coverage for design doc \u00a75 \u2014 composite
    primary key ``(bundle_path, engine_type)``, SCHEMA_VERSION = 3.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")
        fixture_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "resources",
            "backtest_reports_for_testing",
            "test_algorithm_backtest",
        )
        self.fixture = Backtest.open(fixture_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _user_version(self) -> int:
        import sqlite3
        conn = sqlite3.connect(self.index_path)
        try:
            return int(
                conn.execute("PRAGMA user_version").fetchone()[0]
            )
        finally:
            conn.close()

    def test_fresh_index_stamps_schema_version_3(self):
        with SqliteBacktestIndex.create(self.index_path):
            pass
        # SCHEMA_VERSION was bumped to 5 in the multi-study rollout
        # (composite PK extended to include ``study_name``).
        self.assertEqual(self._user_version(), 5)

    def test_composite_pk_distinguishes_engine_rows(self):
        """Two rows with the same ``bundle_path`` but different
        ``engine_type`` coexist; a third row matching either PK pair
        replaces the existing row."""
        vec = self.fixture.index_rows(bundle_path="b.iafbt")[0]
        vec.engine_type = "vector"
        evt = self.fixture.index_rows(bundle_path="b.iafbt")[0]
        evt.engine_type = "event"

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert(vec)
            idx.upsert(evt)
            self.assertEqual(len(idx), 2)

            engines = sorted(r.engine_type for r in idx.iter_rows())
            self.assertEqual(engines, ["event", "vector"])

            # Re-upsert the vector row with a mutated algorithm_id.
            vec.algorithm_id = "renamed"
            idx.upsert(vec)
            self.assertEqual(len(idx), 2)
            algos = {
                r.engine_type: r.algorithm_id for r in idx.iter_rows()
            }
            self.assertEqual(algos["vector"], "renamed")

    def test_migration_from_v2_promotes_pk_and_coerces_null_engine(self):
        """A pre-v9.0 (schema v\u22642) file with single PK and a NULL
        ``engine_type`` is rebuilt with the composite PK and the
        legacy row's engine is coerced to ``'vector'``."""
        import sqlite3

        # Hand-roll the legacy v2 schema (single PK on bundle_path,
        # NULL engine_type allowed) and seed one row.
        conn = sqlite3.connect(self.index_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                'CREATE TABLE backtest_index ('
                '"bundle_path" TEXT PRIMARY KEY, '
                '"algorithm_id" TEXT, '
                '"engine_type" TEXT'
                ')'
            )
            conn.execute(
                'INSERT INTO backtest_index '
                '("bundle_path", "algorithm_id", "engine_type") '
                'VALUES (?, ?, NULL)',
                ("legacy.iafbt", "legacy_algo"),
            )
            conn.execute("PRAGMA user_version = 2")
            conn.commit()
        finally:
            conn.close()

        # Opening with the v9.0 code path must migrate to v3 in-place.
        with SqliteBacktestIndex.open(self.index_path) as idx:
            self.assertEqual(self._user_version(), 5)
            rows = list(idx.iter_rows())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].bundle_path, "legacy.iafbt")
            self.assertEqual(rows[0].algorithm_id, "legacy_algo")
            self.assertEqual(rows[0].engine_type, "vector")

            # Composite PK is now in place: an ``event`` row under
            # the same bundle_path coexists with the migrated one.
            evt_row = BacktestIndexRow(
                algorithm_id="legacy_algo",
                bundle_path="legacy.iafbt",
                engine_type="event",
            )
            idx.upsert(evt_row)
            self.assertEqual(len(idx), 2)
