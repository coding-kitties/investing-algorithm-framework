import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange, BacktestEngine, BacktestIndex,
    BacktestRunConfiguration, BacktestWindow, CSVOHLCVDataProvider,
    RESOURCE_DIRECTORY,
    Study, Universe, create_app,
)
from investing_algorithm_framework.infrastructure import BacktestService
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.infrastructure.services.backtesting \
    import backtest_service as service_module
from tests.scenarios.vector_vs_event_backtests.test_event_vs_vector_backtest \
    import CSV_FILENAME, LongCycleStrategy


class TestVectorCheckpointResume(TestCase):
    engine = BacktestEngine.VECTOR
    engine_name = "vector"

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.resources = Path(temporary.name)
        self.directory = self.resources / "results"
        start = datetime(2020, 12, 20, 10, tzinfo=timezone.utc)
        self.windows = [
            BacktestDateRange(
                start_date=start + timedelta(hours=10 * i),
                end_date=start + timedelta(hours=10 * (i + 1)),
            )
            for i in range(2)
        ]
        self.study = Study(
            name="checkpoint-resume",
            universe=Universe(
                market="BITVAVO", trading_symbol="EUR", symbols=["BTC"],
            ),
            initial_capital=1000,
            risk_free_rate=0.03,
            engines=[self.engine],
            backtest_windows=[
                BacktestWindow(train_range=window)
                for window in self.windows
            ],
        )
        self.executed = []
        self.save = BacktestService._batch_save_and_checkpoint

    def _run(
        self, ids=("a", "b"), *, interrupt_after=None,
        use_checkpoints=True, window_filter=None, changed_parameter=None,
        n_workers=None, final_filter=None,
    ):
        # A fresh app and strategy instances model restarting the caller.
        app = create_app(
            name=f"checkpoint-resume-{uuid4().hex}",
            config={RESOURCE_DIRECTORY: str(self.resources)},
        )
        csv_path = (
            Path(__file__).resolve().parents[2] / "resources" / "test_data"
            / "ohlcv" / CSV_FILENAME
        )
        app.add_data_provider(
            CSVOHLCVDataProvider(
                storage_path=str(csv_path), symbol="BTC/EUR",
                time_frame="2h", market="BITVAVO", warmup_window=5,
            ),
            priority=1,
        )
        strategies = [
            LongCycleStrategy(algorithm_id=algorithm_id)
            for algorithm_id in ids
        ]
        for strategy in strategies:
            strategy.changed_parameter = changed_parameter
        saved_count = 0

        def record_and_save(service, backtests, date_range, *args, **kwargs):
            nonlocal saved_count
            self.executed.extend(
                (backtest.algorithm_id, date_range.start_date)
                for backtest in backtests
            )
            self.save(service, backtests, date_range, *args, **kwargs)
            saved_count += len(backtests)
            if interrupt_after is not None and saved_count >= interrupt_after:
                raise KeyboardInterrupt("simulated restart")

        with patch.object(
            BacktestService, "_batch_save_and_checkpoint",
            new=record_and_save,
        ):
            return app.run_backtests(
                strategies=strategies,
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    backtest_storage_directory=self.directory,
                    use_checkpoints=use_checkpoints,
                    show_progress=False,
                    continue_on_error=False,
                    n_workers=n_workers,
                ),
                window_metrics_filter_function=window_filter,
                final_metrics_filter_function=final_filter,
            )

    def _checkpoint(self):
        with (self.directory / "checkpoints.json").open() as handle:
            return json.load(handle)

    def _assert_complete(self, result, ids=("a", "b")):
        self.assertEqual(set(result.df["algorithm_id"]), set(ids))
        self.assertEqual(set(result.df["engine_type"]), {self.engine_name})
        self.assertEqual(set(result.df["summary.number_of_windows"]), {2})
        expected_dates = {
            (window.start_date, window.end_date) for window in self.windows
        }
        backtests = list(result.iter_backtests())
        self.assertEqual(len(backtests), len(ids))
        for backtest in backtests:
            study = backtest.get_study(self.study.name)
            self.assertIsNotNone(study)
            runs = study.get_engine(self.engine_name).runs
            self.assertEqual(len(runs), 2, "resume must not duplicate runs")
            self.assertEqual(
                {
                    (run.backtest_start_date, run.backtest_end_date)
                    for run in runs
                },
                expected_dates,
            )
        reopened = BacktestIndex.open(
            self.directory, filename="backtest_session_index.parquet",
        )
        pd.testing.assert_frame_equal(result.df, reopened.df)

    def test_restart_after_completed_window_runs_only_second_window(self):
        with self.assertRaisesRegex(KeyboardInterrupt, "simulated restart"):
            self._run(interrupt_after=2)

        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(self.windows[0]): ["a", "b"],
        })
        self.executed.clear()
        result = self._run()

        self.assertEqual(self.executed, [
            ("a", self.windows[1].start_date),
            ("b", self.windows[1].start_date),
        ])
        self._assert_complete(result)

    def test_restart_mid_window_runs_only_missing_algorithm_window_pairs(self):
        with self.assertRaises(KeyboardInterrupt):
            self._run(interrupt_after=1)

        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(self.windows[0]): ["a"],
        })
        self.executed.clear()
        result = self._run()

        self.assertEqual(self.executed, [
            ("b", self.windows[0].start_date),
            ("a", self.windows[1].start_date),
            ("b", self.windows[1].start_date),
        ])
        self._assert_complete(result)

    def test_parallel_restart_skips_completed_window(self):
        with self.assertRaisesRegex(KeyboardInterrupt, "simulated restart"):
            self._run(interrupt_after=2, n_workers=2)

        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(self.windows[0]): ["a", "b"],
        })
        self.executed.clear()
        result = self._run(n_workers=2)

        self.assertCountEqual(self.executed, [
            ("a", self.windows[1].start_date),
            ("b", self.windows[1].start_date),
        ])
        self._assert_complete(result)

    def test_completed_restart_ignores_parameters_and_strategy_order(self):
        original = self._run()
        checkpoint = self._checkpoint()
        bundle_bytes = {
            path.name: path.read_bytes()
            for path in self.directory.glob("*.obtf")
        }
        self.executed.clear()

        with patch.object(
            BacktestService, "_run_batch_backtest_worker",
            side_effect=AssertionError("completed vector run executed"),
        ), patch.object(
            EventLoopService, "start",
            side_effect=AssertionError("completed event run executed"),
        ):
            result = self._run(ids=("b", "a"), changed_parameter=object())

        self.assertEqual(self.executed, [])
        self.assertEqual(self._checkpoint(), checkpoint)
        self.assertEqual(
            {path.name: path.read_bytes()
             for path in self.directory.glob("*.obtf")},
            bundle_bytes,
        )
        self._assert_complete(result)
        pd.testing.assert_frame_equal(
            original.df.sort_values("algorithm_id").reset_index(drop=True),
            result.df.sort_values("algorithm_id").reset_index(drop=True),
        )

    def test_new_algorithm_runs_without_rerunning_existing_ids(self):
        self._run()
        self.executed.clear()
        result = self._run(ids=("a", "b", "new"))

        self.assertEqual(self.executed, [
            ("new", window.start_date) for window in self.windows
        ])
        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(window): ["a", "b", "new"]
            for window in self.windows
        })
        self._assert_complete(result, ids=("a", "b", "new"))

    def test_changed_window_dates_run_even_when_algorithm_ids_match(self):
        self._run()
        changed_window = BacktestDateRange(
            start_date=self.windows[1].start_date,
            end_date=self.windows[1].end_date - timedelta(hours=2),
        )
        self.study.backtest_windows = [
            BacktestWindow(train_range=self.windows[0]),
            BacktestWindow(train_range=changed_window),
        ]
        self.executed.clear()

        result = self._run()

        self.assertEqual(self.executed, [
            ("a", changed_window.start_date),
            ("b", changed_window.start_date),
        ])
        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(window): ["a", "b"]
            for window in [*self.windows, changed_window]
        })
        self.assertEqual(set(result.df["summary.number_of_windows"]), {2})
        for backtest in result.iter_backtests():
            runs = backtest.get_study(self.study.name).get_engine(
                self.engine_name,
            ).runs
            self.assertEqual(len(runs), 3)
            self.assertEqual(
                {run.backtest_end_date for run in runs},
                {window.end_date
                 for window in [*self.windows, changed_window]},
            )

    def test_resumed_metrics_match_an_uninterrupted_backtest(self):
        with self.assertRaises(KeyboardInterrupt):
            self._run(interrupt_after=1)
        resumed = self._run()
        self._assert_complete(resumed)

        self.directory = self.resources / "baseline"
        baseline = self._run()
        self._assert_complete(baseline)
        columns = [
            column for column in baseline.df.columns
            if column.startswith("summary.") or column == "algorithm_id"
        ]
        pd.testing.assert_frame_equal(
            resumed.df[columns].sort_values(
                "algorithm_id",
            ).reset_index(drop=True),
            baseline.df[columns].sort_values(
                "algorithm_id",
            ).reset_index(drop=True),
        )

    def test_disabled_checkpoints_rerun_without_duplicate_bundle_windows(self):
        self._run()
        self.executed.clear()
        result = self._run(use_checkpoints=False)

        self.assertEqual(self.executed, [
            (algorithm_id, window.start_date)
            for window in self.windows for algorithm_id in ("a", "b")
        ])
        self._assert_complete(result)

    def test_resume_reapplies_window_filter_before_running_next_window(self):
        with self.assertRaises(KeyboardInterrupt):
            self._run(interrupt_after=2)
        self.executed.clear()
        observed = []

        def prune(index, window):
            observed.append((
                window.start_date,
                set(index.df["algorithm_id"]),
                set(index.df["summary.number_of_windows"]),
            ))
            return index.filter(lambda row: row["algorithm_id"] == "a")

        result = self._run(window_filter=prune)

        self.assertEqual(observed, [
            (self.windows[0].start_date, {"a", "b"}, {1}),
            (self.windows[1].start_date, {"a"}, {2}),
        ])
        self.assertEqual(self.executed, [("a", self.windows[1].start_date)])
        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(self.windows[0]): ["a", "b"],
            BacktestService._checkpoint_key_for(self.windows[1]): ["a"],
        })
        self._assert_complete(result, ids=("a",))

    def test_index_filters_receive_current_summaries_on_run_and_resume(self):
        for resume in (False, True):
            with self.subTest(resume=resume):
                self.executed.clear()
                observed = []

                def inspect_window(index, window):
                    observed.append((
                        "window", window.start_date,
                        set(index.df["summary.number_of_windows"]),
                    ))
                    return index

                def select_final(index):
                    observed.append((
                        "final", None,
                        set(index.df["summary.number_of_windows"]),
                    ))
                    return index.filter(
                        lambda row: row["algorithm_id"] == "b",
                    )

                result = self._run(
                    window_filter=inspect_window, final_filter=select_final,
                )

                self.assertEqual(observed, [
                    ("window", self.windows[0].start_date, {1}),
                    ("window", self.windows[1].start_date, {2}),
                    ("final", None, {2}),
                ])
                if resume:
                    self.assertEqual(self.executed, [])
                else:
                    self.assertEqual(len(self.executed), 4)
                self._assert_complete(result, ids=("b",))
                self.assertTrue((self.directory / "a.obtf").is_file())

    def test_failed_bundle_save_is_not_checkpointed_and_is_retried(self):
        save_bundles = service_module.save_backtests_to_directory

        def fail_second_save(*args, **kwargs):
            if len(self.executed) == 2:
                raise OSError("simulated disk failure")
            return save_bundles(*args, **kwargs)

        with patch.object(
            service_module, "save_backtests_to_directory",
            side_effect=fail_second_save,
        ), self.assertRaisesRegex(OSError, "simulated disk failure"):
            self._run()

        self.assertEqual(self._checkpoint(), {
            BacktestService._checkpoint_key_for(self.windows[0]): ["a"],
        })
        self.assertTrue((self.directory / "a.obtf").is_file())
        self.assertFalse((self.directory / "b.obtf").exists())
        self.executed.clear()
        result = self._run()

        self.assertEqual(self.executed, [
            ("b", self.windows[0].start_date),
            ("a", self.windows[1].start_date),
            ("b", self.windows[1].start_date),
        ])
        self._assert_complete(result)


class TestEventCheckpointResume(TestVectorCheckpointResume):
    engine = BacktestEngine.EVENT_DRIVEN
    engine_name = "event"
