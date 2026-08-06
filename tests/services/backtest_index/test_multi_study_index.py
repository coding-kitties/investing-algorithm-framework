"""Phase 3d coverage: multi-study row emission + ``study=`` filters.

These tests exercise the schema-v5 contract from
``docs/design/multi-study-bundle.md`` Phase 3d:

* :meth:`Backtest.index_rows` emits one row set per study slot —
  the legacy default slot *and* every entry in
  :meth:`Backtest.studies`.
* :class:`SqliteBacktestIndex` v5 keys rows on
  ``(bundle_path, engine_type, universe_key, study_name)`` so
  multiple studies on the same bundle coexist without collision.
* CLI :func:`list_index` / :func:`rank_index` accept a ``study=``
  parameter to scope reports to a single study slot.
"""
import os
import shutil
import tempfile
from datetime import datetime, timezone
from unittest import TestCase
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange

from investing_algorithm_framework.cli.index_command import (
    list_index, rank_index,
)
from investing_algorithm_framework.domain import (
    Backtest,
    BacktestRun,
    BacktestSummaryMetrics,
)
from investing_algorithm_framework.domain.backtesting.study import (
    EngineSlot,
    Study,
)
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)


def _make_run(*, gain: float = 10.0, trades: int = 2) -> BacktestRun:
    return BacktestRun(
        backtest_window=BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            )
        ),
        initial_unallocated=10_000.0,
        number_of_runs=1,
        number_of_days=30,
        number_of_orders=trades,
        number_of_trades=trades,
    )


def _make_summary(*, sharpe: float, gain: float) -> BacktestSummaryMetrics:
    return BacktestSummaryMetrics(
        sharpe_ratio=sharpe,
        total_net_gain=gain,
        total_net_gain_percentage=gain / 100.0,
        number_of_trades=10,
    )


def _make_two_study_backtest() -> Backtest:
    """Build a Backtest with ``in_sample`` (legacy slot) plus an
    ``oos`` extra study, each carrying a single vector engine slot.
    """
    bt = Backtest(
        algorithm_id="algo-multi",
        tag="phase3d",
        risk_free_rate=0.02,
        parameters={"lookback": 20},
        strategy_ids=["mom"],
        study_name="in_sample",
        study_description="In-sample window",
        vector_runs=[_make_run()],
        vector_summary=_make_summary(sharpe=1.4, gain=140.0),
    )
    oos = Study(
        name="oos",
        description="Out-of-sample window",
        engine_results={
            "vector": EngineSlot(
                runs=[_make_run()],
                summary=_make_summary(sharpe=0.7, gain=70.0),
            )
        },
    )
    bt.add_study(oos)
    return bt


class TestIndexRowsEmitsAllStudies(TestCase):

    def test_two_studies_produce_two_rows(self):
        bt = _make_two_study_backtest()
        rows = bt.index_rows(bundle_path="multi.iafbt")
        self.assertEqual(len(rows), 2)

        by_study = {r.study_name: r for r in rows}
        self.assertEqual(
            sorted(by_study), ["in_sample", "oos"]
        )
        self.assertAlmostEqual(
            by_study["in_sample"].summary_metrics.sharpe_ratio, 1.4,
        )
        self.assertAlmostEqual(
            by_study["oos"].summary_metrics.sharpe_ratio, 0.7,
        )
        self.assertEqual(
            by_study["in_sample"].study_description, "In-sample window"
        )
        self.assertEqual(
            by_study["oos"].study_description, "Out-of-sample window"
        )
        for r in rows:
            self.assertEqual(r.engine_type, "vector")
            self.assertIsNone(r.universe_key)
            self.assertEqual(r.bundle_path, "multi.iafbt")
            self.assertEqual(r.algorithm_id, "algo-multi")


class TestSqliteIndexMultiStudyRows(TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_studies_coexist_under_v5_pk(self):
        bt = _make_two_study_backtest()
        rows = bt.index_rows(bundle_path="multi.iafbt")

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(rows)
            self.assertEqual(len(idx), 2)
            loaded = sorted(
                (r.study_name for r in idx.iter_rows())
            )
            self.assertEqual(loaded, ["in_sample", "oos"])

    def test_re_upsert_updates_in_place(self):
        bt = _make_two_study_backtest()
        rows = bt.index_rows(bundle_path="multi.iafbt")
        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(rows)
            # Re-upsert just the ``oos`` row with mutated metrics.
            oos_row = next(r for r in rows if r.study_name == "oos")
            oos_row.summary_metrics = _make_summary(
                sharpe=99.0, gain=1.0,
            )
            idx.upsert(oos_row)
            self.assertEqual(len(idx), 2)
            by_study = {
                r.study_name: r for r in idx.iter_rows()
            }
            self.assertAlmostEqual(
                by_study["oos"].summary_metrics.sharpe_ratio, 99.0,
            )
            self.assertAlmostEqual(
                by_study["in_sample"].summary_metrics.sharpe_ratio, 1.4,
            )

    def test_legacy_unnamed_study_stored_as_default(self):
        """A backtest with no ``study_name`` produces a row whose
        SQL ``study_name`` column is the canonical ``'default'``
        sentinel — keeping the composite PK well-defined."""
        bt = Backtest(
            algorithm_id="legacy",
            vector_runs=[_make_run()],
            vector_summary=_make_summary(sharpe=0.5, gain=10.0),
        )
        rows = bt.index_rows(bundle_path="legacy.iafbt")
        self.assertEqual(len(rows), 1)

        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(rows)
            (loaded,) = list(idx.iter_rows())
            self.assertEqual(loaded.study_name, "default")


class TestListAndRankStudyFilter(TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmp, "index.sqlite")
        bt = _make_two_study_backtest()
        with SqliteBacktestIndex.create(self.index_path) as idx:
            idx.upsert_many(bt.index_rows(bundle_path="multi.iafbt"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_list_index_no_study_filter_returns_all_studies(self):
        rows = list_index(self.index_path)
        self.assertEqual(len(rows), 2)

    def test_list_index_filters_by_study(self):
        rows = list_index(self.index_path, study="in_sample")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(
            rows[0]["summary_sharpe_ratio"], 1.4,
        )

        rows = list_index(self.index_path, study="oos")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(
            rows[0]["summary_sharpe_ratio"], 0.7,
        )

    def test_rank_index_filters_by_study(self):
        # Without a study filter, both studies participate.
        ranked_all = rank_index(self.index_path, by="sharpe_ratio")
        self.assertEqual(len(ranked_all), 2)

        # Restrict to ``oos`` — only the OOS row appears.
        ranked_oos = rank_index(
            self.index_path, by="sharpe_ratio", study="oos",
        )
        self.assertEqual(len(ranked_oos), 1)
        self.assertAlmostEqual(
            ranked_oos[0]["summary_sharpe_ratio"], 0.7,
        )

    def test_rank_index_engine_and_study_filter_combine(self):
        """Mirrors the notebook 03 call shape:
        ``rank_index(..., engine="vector", study="in_sample_param_sweep")``.

        ``engine=`` and ``study=`` are independent SQL clauses
        AND-ed together, so an engine that matches no rows must
        prune the whole result even when the study filter alone
        would return rows.
        """
        # vector + in_sample → exactly the in_sample row
        # (sharpe 1.4 uniquely identifies it in the fixture).
        ranked = rank_index(
            self.index_path,
            by="sharpe_ratio",
            engine="vector",
            study="in_sample",
        )
        self.assertEqual(len(ranked), 1)
        self.assertAlmostEqual(
            ranked[0]["summary_sharpe_ratio"], 1.4,
        )

        # vector + oos → exactly the oos row (sharpe 0.7).
        ranked = rank_index(
            self.index_path,
            by="sharpe_ratio",
            engine="vector",
            study="oos",
        )
        self.assertEqual(len(ranked), 1)
        self.assertAlmostEqual(
            ranked[0]["summary_sharpe_ratio"], 0.7,
        )

        # event + in_sample → empty (fixture has only vector slots),
        # which proves the engine filter is actually applied on top
        # of the study filter rather than silently ignored.
        ranked = rank_index(
            self.index_path,
            by="sharpe_ratio",
            engine="event",
            study="in_sample",
        )
        self.assertEqual(ranked, [])
