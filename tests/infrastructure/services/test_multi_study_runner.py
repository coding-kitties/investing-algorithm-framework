"""
Phase 3c integration tests: end-to-end multi-study runner behaviour.

These tests exercise the public ``app.run_*_backtests`` entry points
with a real data provider against a small fixture window, then re-open
the resulting bundle and assert that:

* A single ``study_name`` round-trips through the persistence layer
  unchanged.
* Re-running the *same* algorithm against the *same* storage directory
  with a *different* ``study_name`` produces a single bundle file
  containing both studies (use cases UC2 / UC3 in
  ``docs/design/multi-study-bundle.md``).
* Re-running with the *same* ``study_name`` and a non-overlapping date
  range merges the new run into the same study slot (preserving the
  pre-Phase-3c multi-window aggregation behaviour).
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework import (
    BacktestDateRange,
    RESOURCE_DIRECTORY,
    SnapshotInterval,
    create_app,
)
from investing_algorithm_framework.domain.backtesting.backtest import Backtest

from tests.infrastructure.services.test_backtest_service import (
    SimpleVectorStrategy,
)


class TestMultiStudyRunnerIntegration(unittest.TestCase):
    """End-to-end tests for the Phase 3c runner integration."""

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                os.pardir,
                os.pardir,
                "resources",
            )
        )
        self.storage = tempfile.mkdtemp()
        self.algo_id = "phase3c_algo"
        self.end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        self.window_a = BacktestDateRange(
            start_date=self.end_date - timedelta(days=20),
            end_date=self.end_date,
            name="A",
        )
        self.window_b = BacktestDateRange(
            start_date=self.end_date,
            end_date=self.end_date + timedelta(days=20),
            name="B",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.storage, ignore_errors=True)

    def _run(self, *, date_range, study_name, study_description=None):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        return app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[SimpleVectorStrategy(algorithm_id=self.algo_id)],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=self.storage,
            use_checkpoints=True,
            study_name=study_name,
            study_description=study_description,
        )

    def _open(self) -> Backtest:
        return Backtest.open(
            os.path.join(self.storage, f"{self.algo_id}.iafbt")
        )

    def test_single_study_round_trips_through_runner(self):
        """``study_name`` set on the runner survives save+open."""
        results = self._run(
            date_range=self.window_a,
            study_name="in_sample",
            study_description="IS window",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].get_study().name, "in_sample")

        bundled = self._open()
        self.assertEqual(bundled.get_study().name, "in_sample")
        self.assertEqual(sorted(bundled.list_studies()), ["in_sample"])

    def test_two_studies_same_algorithm_share_one_bundle(self):
        """
        Running the same algorithm twice with different ``study_name``s
        produces a single bundle file with both studies side-by-side
        (UC2 / UC3 in the multi-study design doc).
        """
        self._run(date_range=self.window_a, study_name="in_sample")
        self._run(date_range=self.window_b, study_name="oos")

        bundled = self._open()
        self.assertEqual(
            sorted(bundled.list_studies()), ["in_sample", "oos"]
        )

        # The most-recently-written study becomes the legacy slot;
        # the other lands in studies.
        self.assertEqual(bundled.get_study().name, "oos")
        self.assertEqual(len(bundled.vector_runs), 1)

        in_sample_study = bundled.get_study("in_sample")
        is_runs = (in_sample_study.engine_results.get("vector") or
                   type("Empty", (), {"runs": []})()).runs
        self.assertEqual(len(is_runs), 1)

    def test_same_study_multi_window_appends_runs(self):
        """
        When the second run uses the *same* ``study_name`` and a
        non-overlapping window, the runs accumulate inside that
        single study slot rather than spawning a new study.
        """
        self._run(date_range=self.window_a, study_name="full")
        self._run(date_range=self.window_b, study_name="full")

        bundled = self._open()
        self.assertEqual(sorted(bundled.list_studies()), ["full"])
        # Two distinct (non-overlapping) windows → two runs in the
        # default vector slot.
        self.assertEqual(len(bundled.vector_runs), 2)
        windows = sorted(
            (r.backtest_start_date, r.backtest_end_date)
            for r in bundled.vector_runs
        )
        self.assertEqual(len(set(windows)), 2)


if __name__ == "__main__":
    unittest.main()
