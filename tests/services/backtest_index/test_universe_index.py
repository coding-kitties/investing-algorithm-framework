"""Phase 3 (multi-universe / studies) coverage for the SQLite index
and CLI helpers.

These tests exercise the schema-v4 contract:

* :class:`BacktestIndexRow` carries ``universe_key`` /
  ``study_name`` / ``study_description`` and round-trips them
  through :meth:`to_flat_dict` / :meth:`from_flat_dict`.
* :meth:`Backtest.index_rows` emits one pooled row per engine plus
  one row per (engine, universe_key) when per-universe summaries
  are present.
* :class:`SqliteBacktestIndex` v4 distinguishes pooled and
  per-universe rows by composite PK
  ``(bundle_path, engine_type, universe_key)``.
* CLI :func:`list_index` / :func:`rank_index` default to pooled
  rows but can be filtered by ``universe_key``.
"""
import os
import shutil
import tempfile
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.cli.index_command import (
    list_index, rank_index,
)
from investing_algorithm_framework.domain import (
    Backtest,
    BacktestDateRange,
    BacktestIndexRow,
    BacktestRun,
    BacktestSummaryMetrics,
    BacktestWindow,
    Universe,
)
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)


def _make_run(
    *, gain: float, trades: int, universe_key: str | None = None,
) -> BacktestRun:
    return BacktestRun(
        backtest_window=BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            )
        ),
        initial_unallocated=10_000.0,
        trading_symbol="USDT",
        number_of_runs=1,
        number_of_days=30,
        number_of_orders=trades,
        number_of_trades=trades,
        symbols=["BTC/USDT"],
        metadata={"universe_key": universe_key} if universe_key else {},
    )


def _make_summary(*, sharpe: float, gain: float) -> BacktestSummaryMetrics:
    return BacktestSummaryMetrics(
        sharpe_ratio=sharpe,
        total_net_gain=gain,
        total_net_gain_percentage=gain / 100.0,
        number_of_trades=10,
    )


def _make_backtest_with_universes() -> Backtest:
    """Build an in-memory Backtest with one engine populated and
    two per-universe summaries plus one cross-universe pooled
    summary."""
    bt = Backtest(
        algorithm_id="algo-x",
        tag="mu-test",
        risk_free_rate=0.02,
        parameters={"lookback": 20},
        strategy_ids=["mom"],
        study_name="rolling-2024",
        study_description="ETH/BTC across universes",
        universes=[
            Universe(key="majors", symbols=["BTC/USDT", "ETH/USDT"]),
            Universe(key="alts", symbols=["SOL/USDT", "AVAX/USDT"]),
        ],
        vector_runs=[
            _make_run(gain=120.0, trades=10, universe_key="majors"),
            _make_run(gain=80.0, trades=8, universe_key="majors"),
            _make_run(gain=40.0, trades=6, universe_key="alts"),
        ],
        vector_summary=_make_summary(sharpe=1.1, gain=240.0),
        vector_summaries_by_universe={
            "majors": _make_summary(sharpe=1.5, gain=200.0),
            "alts": _make_summary(sharpe=0.6, gain=40.0),
        },
    )
    return bt


class TestBacktestIndexRowFields(TestCase):

    def test_new_fields_default_to_none(self):
        row = BacktestIndexRow()
        self.assertIsNone(row.universe_key)
        self.assertIsNone(row.study_name)
        self.assertIsNone(row.study_description)

    def test_to_from_flat_dict_round_trip_includes_new_fields(self):
        row = BacktestIndexRow(
            algorithm_id="a",
            bundle_path="b.iafbt",
            engine_type="vector",
            universe_key="majors",
            study_name="study-A",
            study_description="rolling 2024",
        )
        flat = row.to_flat_dict()
        self.assertEqual(flat["universe_key"], "majors")
        self.assertEqual(flat["study_name"], "study-A")
        self.assertEqual(flat["study_description"], "rolling 2024")

        rebuilt = BacktestIndexRow.from_flat_dict(flat)
        self.assertEqual(rebuilt.universe_key, "majors")
        self.assertEqual(rebuilt.study_name, "study-A")
        self.assertEqual(rebuilt.study_description, "rolling 2024")


class TestBacktestIndexRowsEmission(TestCase):

    def test_legacy_backtest_emits_only_pooled_rows(self):
        bt = Backtest(
            algorithm_id="legacy",
            vector_runs=[_make_run(gain=10.0, trades=2)],
            vector_summary=_make_summary(sharpe=0.5, gain=10.0),
        )
        rows = bt.index_rows(bundle_path="leg.iafbt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].engine_type, "vector")
        self.assertIsNone(rows[0].universe_key)

    def test_multi_universe_backtest_emits_pooled_and_per_universe(self):
        bt = _make_backtest_with_universes()
        rows = bt.index_rows(bundle_path="mu.iafbt")

        # 1 pooled vector + 2 per-universe vector rows.
        self.assertEqual(len(rows), 3)
        keys = [r.universe_key for r in rows]
        self.assertEqual(keys.count(None), 1)
        self.assertIn("majors", keys)
        self.assertIn("alts", keys)

        # Pooled row has total run count, per-universe rows have
        # their own slice.
        by_key = {r.universe_key: r for r in rows}
        self.assertEqual(by_key[None].number_of_runs, 3)
        self.assertEqual(by_key["majors"].number_of_runs, 2)
        self.assertEqual(by_key["alts"].number_of_runs, 1)

        # Study fields are stamped on every row.
        for r in rows:
            self.assertEqual(r.study_name, "rolling-2024")
            self.assertEqual(r.study_description, "ETH/BTC across universes")
            self.assertEqual(r.algorithm_id, "algo-x")
            self.assertEqual(r.bundle_path, "mu.iafbt")

        # Per-universe summary metrics differ from pooled.
        self.assertAlmostEqual(
            by_key[None].summary_metrics.sharpe_ratio, 1.1,
        )
        self.assertAlmostEqual(
            by_key["majors"].summary_metrics.sharpe_ratio, 1.5,
        )
        self.assertAlmostEqual(
            by_key["alts"].summary_metrics.sharpe_ratio, 0.6,
        )


class TestSqliteIndexUniverseRows(TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pooled_and_per_universe_rows_coexist(self):
        bt = _make_backtest_with_universes()
        rows = bt.index_rows(bundle_path="mu.iafbt")

        with SqliteBacktestIndex.create(self.index_path) as idx:
            for r in rows:
                idx.upsert(r)
            self.assertEqual(len(idx), 3)

            loaded = list(idx.iter_rows())
            keys = sorted(
                "" if r.universe_key is None else r.universe_key
                for r in loaded
            )
            self.assertEqual(keys, ["", "alts", "majors"])

    def test_replace_per_universe_row_keeps_others(self):
        bt = _make_backtest_with_universes()
        rows = bt.index_rows(bundle_path="mu.iafbt")

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(rows)
            self.assertEqual(len(idx), 3)

            # Re-upsert just the "majors" row with a mutated metric.
            mu_row = next(r for r in rows if r.universe_key == "majors")
            mu_row.summary_metrics = _make_summary(sharpe=99.0, gain=1.0)
            idx.upsert(mu_row)
            self.assertEqual(len(idx), 3)

            loaded = {
                r.universe_key: r for r in idx.iter_rows()
            }
            self.assertAlmostEqual(
                loaded["majors"].summary_metrics.sharpe_ratio, 99.0,
            )
            # Pooled (None) and "alts" rows untouched.
            self.assertAlmostEqual(
                loaded[None].summary_metrics.sharpe_ratio, 1.1,
            )
            self.assertAlmostEqual(
                loaded["alts"].summary_metrics.sharpe_ratio, 0.6,
            )

    def test_list_index_default_returns_pooled_only(self):
        bt = _make_backtest_with_universes()
        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(bt.index_rows(bundle_path="mu.iafbt"))

        rows = list_index(self.index_path)
        # Default ``universe_key=""`` filters to the pooled row.
        self.assertEqual(len(rows), 1)

    def test_list_index_universe_filter(self):
        bt = _make_backtest_with_universes()
        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(bt.index_rows(bundle_path="mu.iafbt"))

        majors = list_index(self.index_path, universe_key="majors")
        self.assertEqual(len(majors), 1)

        all_rows = list_index(self.index_path, universe_key=None)
        self.assertEqual(len(all_rows), 3)

    def test_rank_index_filters_to_pooled_by_default(self):
        bt = _make_backtest_with_universes()
        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(bt.index_rows(bundle_path="mu.iafbt"))

        ranked = rank_index(self.index_path, by="sharpe_ratio")
        # Only the pooled row participates by default.
        self.assertEqual(len(ranked), 1)


class TestSqliteIndexV4Migration(TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migration_from_v3_adds_universe_columns(self):
        """A v3 file (composite PK on ``(bundle_path, engine_type)``)
        is rebuilt with the v4 PK and gains the universe / study
        columns. Pre-existing rows become pooled rows."""
        import sqlite3

        # Hand-roll a v3 schema and seed one row.
        conn = sqlite3.connect(self.index_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                'CREATE TABLE backtest_index ('
                '"bundle_path" TEXT NOT NULL, '
                '"algorithm_id" TEXT, '
                '"engine_type" TEXT NOT NULL DEFAULT \'vector\', '
                'PRIMARY KEY ("bundle_path", "engine_type")'
                ')'
            )
            conn.execute(
                'INSERT INTO backtest_index '
                '("bundle_path", "algorithm_id", "engine_type") '
                'VALUES (?, ?, ?)',
                ("legacy.iafbt", "legacy_algo", "vector"),
            )
            conn.execute("PRAGMA user_version = 3")
            conn.commit()
        finally:
            conn.close()

        with SqliteBacktestIndex.open(self.index_path) as idx:
            # Schema bumped to v5.
            v = int(
                self._raw_user_version()
            )
            self.assertEqual(v, 5)

            rows = list(idx.iter_rows())
            self.assertEqual(len(rows), 1)
            (loaded,) = rows
            self.assertEqual(loaded.bundle_path, "legacy.iafbt")
            self.assertEqual(loaded.engine_type, "vector")
            # SQL ``''`` round-trips to in-memory ``None``.
            self.assertIsNone(loaded.universe_key)

            # Upserting a per-universe row alongside the migrated
            # pooled row works under the new composite PK.
            idx.upsert(BacktestIndexRow(
                bundle_path="legacy.iafbt",
                algorithm_id="legacy_algo",
                engine_type="vector",
                universe_key="majors",
            ))
            self.assertEqual(len(idx), 2)

    def _raw_user_version(self) -> int:
        import sqlite3
        conn = sqlite3.connect(self.index_path)
        try:
            return int(
                conn.execute("PRAGMA user_version").fetchone()[0]
            )
        finally:
            conn.close()
