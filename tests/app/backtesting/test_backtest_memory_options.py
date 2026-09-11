from datetime import datetime, timedelta, timezone
import gc
import inspect
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
import weakref

import pandas as pd

from investing_algorithm_framework import (
    Algorithm, BacktestDateRange, BacktestEngine, BacktestIndex,
    BacktestRunConfiguration,
    BacktestWindow, SnapshotInterval,
    CSVOHLCVDataProvider, RESOURCE_DIRECTORY, Schedule,
    Study, Task, TimeUnit, TradingStrategy, Universe, create_app,
)
from investing_algorithm_framework.app.app import App
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.infrastructure import BacktestService
from investing_algorithm_framework.infrastructure.services.backtesting \
    .event_backtest_service import EventBacktestService
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_resources import BacktestResourceError, MemoryGuard
from tests.app.backtesting \
    .test_run_backtest_independent_algorithms_vector import VectorTestStrategy
from tests.scenarios.vector_vs_event_backtests.test_event_vs_vector_backtest \
    import LongCycleStrategy


class MemoryOptionsStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.HOUR)

    def generate_signal_series(self, data):
        return iter(())


class EventIndexStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.HOUR)

    def generate_signals(self, context, data):
        return iter(())


class EventWorkerProbeStrategy(EventIndexStrategy):
    def __init__(self, algorithm_id, probe_directory, fail=False):
        super().__init__(algorithm_id=algorithm_id)
        self.strategy_id = algorithm_id
        self.probe_directory = probe_directory
        self.fail = fail

    def generate_signals(self, context, data):
        if self.fail:
            raise RuntimeError("intentional event worker failure")
        path = Path(self.probe_directory) / (
            f"{self.strategy_id}-{os.getpid()}.json"
        )
        path.write_text(json.dumps({
            "pid": os.getpid(),
            "resource_directory": context.config[RESOURCE_DIRECTORY],
            "database_uri": context.config["SQLALCHEMY_DATABASE_URI"],
        }))
        return iter(())


class EventWorkerResourceFailure(EventIndexStrategy):
    def generate_signals(self, context, data):
        raise BacktestResourceError("intentional worker memory pressure")


class EventWorkerProbeTask(Task):
    schedule = Schedule.every(12, TimeUnit.HOUR)

    def run(self, context):
        path = Path(self.probe_directory) / f"task-{os.getpid()}.json"
        path.write_text(json.dumps(context.config[RESOURCE_DIRECTORY]))


class TestBacktestMemoryOptions(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.app = create_app(
            name=f"memory-options-{uuid4().hex}",
            config={RESOURCE_DIRECTORY: self.storage.name},
        )
        self.study = Study(
            name="memory-test",
            universe=Universe(
                market="BITVAVO", trading_symbol="EUR", symbols=["BTC"],
            ),
            initial_capital=1000,
            engines=[BacktestEngine.VECTOR],
            backtest_windows=[BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
                ),
            )],
        )
        self.strategy = MemoryOptionsStrategy(algorithm_id="memory-test")

    def test_run_backtest_forwards_index_and_memory_controls(self):
        result = BacktestIndex(
            self.storage.name, pd.DataFrame(columns=["algorithm_id"]),
        )

        def window_filter(index, date_range):
            return index

        def final_filter(index):
            return index

        options = {
            "window_metrics_filter_function": window_filter,
            "final_metrics_filter_function": final_filter,
        }
        configuration = BacktestRunConfiguration(
            backtest_storage_directory=Path(self.storage.name),
            n_workers=2, memory_budget_mb=2048, min_available_memory_mb=1024,
            max_tasks_per_child=3, show_progress=False,
            continue_on_error=False, use_checkpoints=False,
            snapshot_interval=SnapshotInterval.STRATEGY_ITERATION,
            skip_data_sources_initialization=True,
            dynamic_position_sizing=True, fill_missing_data=False,
        )
        with patch.object(
            BacktestService, "run_vector_backtests", return_value=result,
        ) as run:
            actual = self.app.run_backtest(
                strategy=self.strategy,
                study=self.study,
                **options,
                run_configuration=configuration,
            )

        self.assertIs(actual, result)
        self.assertEqual(run.call_args.kwargs["result_mode"], "index")
        for name, value in vars(configuration).items():
            self.assertEqual(run.call_args.kwargs[name], value)
        for key, value in options.items():
            self.assertEqual(run.call_args.kwargs[key], value)

    def test_run_backtests_wrapper_forwards_controls(self):
        options = {
            "window_metrics_filter_function": lambda index, window: index,
            "final_metrics_filter_function": lambda index: index,
        }
        with patch.object(App, "run_backtest") as run:
            configuration = BacktestRunConfiguration(
                memory_budget_mb=2048, min_available_memory_mb=1024,
                max_tasks_per_child=None,
            )
            self.app.run_backtests(
                strategies=[self.strategy], study=self.study, **options,
                run_configuration=configuration,
            )
        self.assertIs(run.call_args.kwargs["run_configuration"], configuration)
        for key, value in options.items():
            self.assertEqual(run.call_args.kwargs[key], value)

    def test_default_creates_unique_persistent_index_directories(self):
        with patch.object(
            BacktestService, "run_vector_backtests",
            side_effect=lambda **kwargs: BacktestIndex(
                kwargs["backtest_storage_directory"],
                pd.DataFrame(columns=["algorithm_id"]),
            ),
        ) as run:
            actual = self.app.run_backtest(
                strategy=self.strategy, study=self.study,
            )
            second = self.app.run_backtests(
                strategies=[self.strategy], study=self.study,
            )
        self.assertIsInstance(actual, BacktestIndex)
        self.assertIsInstance(second, BacktestIndex)
        self.assertNotEqual(actual.directory, second.directory)
        for result in (actual, second):
            self.assertTrue(result.directory.is_dir())
            self.assertEqual(
                result.directory.parent,
                Path(self.storage.name).resolve() / "backtests",
            )
        self.assertEqual(run.call_args.kwargs["result_mode"], "index")
        self.assertIsNone(run.call_args.kwargs["memory_budget_mb"])
        self.assertIsNone(run.call_args.kwargs["min_available_memory_mb"])

    def test_real_spawn_index_matches_sequential_and_resumes(self):
        csv_path = (
            Path(__file__).resolve().parents[2] / "resources" / "test_data"
            / "ohlcv" / "OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv"
        )
        self.app.add_data_provider(
            CSVOHLCVDataProvider(
                storage_path=str(csv_path), symbol="BTC/EUR",
                time_frame="2h", market="BITVAVO", warmup_window=5,
            ),
            priority=1,
        )
        dates = [
            datetime(2020, 12, 20, 10, tzinfo=timezone.utc),
            datetime(2020, 12, 20, 20, tzinfo=timezone.utc),
            datetime(2020, 12, 21, 6, tzinfo=timezone.utc),
        ]
        self.study.backtest_windows = [
            BacktestWindow(train_range=BacktestDateRange(
                start_date=start, end_date=end,
            )) for start, end in zip(dates, dates[1:])
        ]
        strategies: list[TradingStrategy] = [
            VectorTestStrategy(algorithm_id=f"real-{i}") for i in range(2)
        ]
        baseline = self.app.run_backtest(
            strategies=strategies,
            study=self.study,
            run_configuration=BacktestRunConfiguration(
                backtest_storage_directory=Path(self.storage.name) / "baseline",
            ),
        )
        assert isinstance(baseline, BacktestIndex)
        output_path = Path(self.storage.name) / "parallel"
        index = self.app.run_backtest(
            strategies=strategies,
            study=self.study,
            run_configuration=BacktestRunConfiguration(
                backtest_storage_directory=output_path,
                n_workers=2,
                max_tasks_per_child=2,
                use_checkpoints=True,
            ),
        )
        assert isinstance(index, BacktestIndex)
        for backtest in baseline.iter_backtests():
            row = index.df.loc[
                (index.df["algorithm_id"] == backtest.algorithm_id)
                & index.df["universe_key"].isna()
            ].iloc[0]
            summary = backtest.get_summary("vector", study=self.study.name)
            assert summary is not None
            self.assertEqual(row["summary.number_of_windows"], 2)
            self.assertEqual(
                row["summary.total_net_gain"], summary.total_net_gain,
            )
        with patch.object(
            BacktestService, "_run_batch_backtest_worker",
            side_effect=AssertionError("checkpointed strategy was rerun"),
        ):
            resumed = self.app.run_backtest(
                strategies=strategies,
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    backtest_storage_directory=output_path,
                    n_workers=2,
                    max_tasks_per_child=2,
                    use_checkpoints=True,
                ),
            )
        assert isinstance(resumed, BacktestIndex)
        pd.testing.assert_frame_equal(index.df, resumed.df)
        self.assertEqual(len(list(resumed.iter_backtests())), 2)

    def test_event_engine_returns_persistent_index_by_default(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        strategy = EventIndexStrategy(algorithm_id="event-index")
        with patch.object(
            BacktestService, "_load_backtests_from_session",
            side_effect=AssertionError("event must not bulk reload"),
        ):
            result = self.app.run_backtest(
                strategy=strategy,
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    min_available_memory_mb=1,
                ),
            )
        self.assertIsInstance(result, BacktestIndex)
        self.assertEqual(set(result.df["engine_type"]), {"event"})
        self.assertEqual(set(result.df["study_name"]), {self.study.name})
        self.assertTrue((result.directory / "event-index.obtf").is_file())
        loaded = result.load_backtests(workers=1)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(
            loaded[0].get_study(self.study.name).initial_capital, 1000,
        )
        self.assertEqual(
            len(loaded[0].get_study(self.study.name).backtest_windows), 1,
        )
        reopened = BacktestIndex.open(
            result.directory, filename="backtest_session_index.parquet",
        )
        pd.testing.assert_frame_equal(result.df, reopened.df)

    def test_parallel_event_workers_match_sequential_trades_and_resume(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        self.study.risk_free_rate = 0.03
        self.study.backtest_windows = [BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2020, 12, 20, 10, tzinfo=timezone.utc),
                end_date=datetime(2020, 12, 20, 16, tzinfo=timezone.utc),
            ),
        )]
        csv_path = Path(__file__).resolve().parents[2] / "resources" \
            / "test_data" / "ohlcv" \
            / "OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv"
        self.app.add_data_provider(CSVOHLCVDataProvider(
            storage_path=str(csv_path), symbol="BTC/EUR", time_frame="2h",
            market="BITVAVO", warmup_window=5,
        ), priority=1)
        sequential = self.app.run_backtest(
            strategies=[
                LongCycleStrategy(algorithm_id=f"trading-{i}")
                for i in range(2)
            ], study=self.study,
        )
        parallel = self.app.run_backtest(
            strategies=[
                LongCycleStrategy(algorithm_id=f"trading-{i}")
                for i in range(2)
            ],
            study=self.study,
            run_configuration=BacktestRunConfiguration(
                n_workers=2,
                max_tasks_per_child=2,
            ),
        )
        for expected, actual in zip(
            sequential.iter_backtests(), parallel.iter_backtests(),
        ):
            expected_summary = expected.get_summary("event", self.study.name)
            actual_summary = actual.get_summary("event", self.study.name)
            self.assertEqual(
                expected_summary.total_net_gain, actual_summary.total_net_gain,
            )
            self.assertGreater(
                len(actual.get_all_backtest_runs()[0].trades), 0,
            )
            self.assertEqual(
                len(expected.get_all_backtest_runs()[0].trades),
                len(actual.get_all_backtest_runs()[0].trades),
            )
        with patch(
            "investing_algorithm_framework.infrastructure.services."
            "backtesting.backtest_service.bounded_process_map",
            side_effect=AssertionError("completed events must not spawn"),
        ):
            resumed = self.app.run_backtest(
                strategies=[
                    LongCycleStrategy(algorithm_id=f"trading-{i}")
                    for i in range(2)
                ],
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    n_workers=2,
                    use_checkpoints=True,
                    backtest_storage_directory=parallel.directory,
                ),
            )
        pd.testing.assert_frame_equal(parallel.df, resumed.df)

    def test_parallel_event_workers_are_isolated_and_recycled(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        probes = Path(self.storage.name) / "probes"
        probes.mkdir()
        result = self.app.run_backtest(
            strategies=[
                EventWorkerProbeStrategy(
                    algorithm_id=f"isolated-{i}", probe_directory=str(probes),
                ) for i in range(2)
            ],
            study=self.study,
            run_configuration=BacktestRunConfiguration(
                n_workers=2,
                max_tasks_per_child=1,
            ),
        )
        self.assertEqual(result.df["algorithm_id"].nunique(), 2)
        recorded = [json.loads(path.read_text()) for path in probes.iterdir()]
        self.assertEqual(len({row["pid"] for row in recorded}), 2)
        for row in recorded:
            self.assertNotEqual(row["pid"], os.getpid())
            resource = Path(row["resource_directory"])
            self.assertNotEqual(resource, Path(self.storage.name))
            self.assertIn(resource.as_posix(), row["database_uri"])
            self.assertFalse(resource.exists(), "worker directory leaked")

    def test_parallel_event_failure_keeps_completed_checkpoint(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        probes = Path(self.storage.name) / "failure-probes"
        probes.mkdir()
        strategies = [
            EventWorkerProbeStrategy(
                algorithm_id=f"failure-{i}", probe_directory=str(probes),
                fail=(i == 1),
            ) for i in range(2)
        ]
        directory = Path(self.storage.name) / "failed-parallel"
        with self.assertRaisesRegex(RuntimeError, "intentional event"):
            self.app.run_backtest(
                strategies=strategies,
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    continue_on_error=False,
                    backtest_storage_directory=directory,
                    n_workers=2,
                    max_tasks_per_child=1,
                ),
            )
        self.assertTrue((directory / "failure-0.obtf").exists())
        self.assertFalse((directory / "failure-1.obtf").exists())
        strategies[1].fail = False
        result = self.app.run_backtest(
            strategies=strategies,
            study=self.study,
            run_configuration=BacktestRunConfiguration(
                backtest_storage_directory=directory,
                n_workers=2,
                max_tasks_per_child=1,
            ),
        )
        self.assertEqual(result.df["algorithm_id"].nunique(), 2)
        self.assertEqual(len(list(probes.glob("failure-0-*.json"))), 1)

    def test_parallel_event_pruning_is_a_window_barrier(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.study.backtest_windows = [
            BacktestWindow(train_range=BacktestDateRange(
                start_date=start + timedelta(days=i),
                end_date=start + timedelta(days=i + 1),
            )) for i in range(2)
        ]
        observed = []

        def prune(index, date_range):
            observed.append(index.df.copy())
            return index.filter(lambda row: row["algorithm_id"] == "event-0")

        result = self.app.run_backtest(
            strategies=[
                EventIndexStrategy(algorithm_id=f"event-{i}")
                for i in range(2)
            ],
            study=self.study,
            window_metrics_filter_function=prune,
            run_configuration=BacktestRunConfiguration(
                n_workers=2,
                max_tasks_per_child=2,
            ),
        )
        self.assertEqual(len(observed), 2)
        self.assertEqual(
            set(observed[0]["algorithm_id"]), {"event-0", "event-1"},
        )
        self.assertEqual(set(observed[0]["summary.number_of_windows"]), {1})
        self.assertEqual(set(observed[1]["algorithm_id"]), {"event-0"})
        self.assertEqual(set(observed[1]["summary.number_of_windows"]), {2})
        self.assertEqual(set(result.df["algorithm_id"]), {"event-0"})

    def test_parallel_combined_algorithms_keep_strategies_and_tasks_together(
        self,
    ):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        probes = Path(self.storage.name) / "combined-probes"
        probes.mkdir()
        algorithms = []
        for i in range(2):
            task = EventWorkerProbeTask()
            task.probe_directory = str(probes)
            algorithms.append(Algorithm(
                algorithm_id=f"combined-{i}",
                strategies=[
                    EventWorkerProbeStrategy(
                        algorithm_id=f"combined-{i}-leg-{leg}",
                        probe_directory=str(probes),
                    ) for leg in range(2)
                ],
                tasks=[task],
            ))
        result = self.app.run_backtest(
            algorithms=algorithms,
            study=self.study,
            run_configuration=BacktestRunConfiguration(
                n_workers=2,
                max_tasks_per_child=1,
            ),
        )
        self.assertEqual(
            set(result.df["algorithm_id"]), {"combined-0", "combined-1"},
        )
        task_resources = {
            json.loads(path.read_text()) for path in probes.glob("task-*.json")
        }
        strategy_resources = [
            json.loads(path.read_text())["resource_directory"]
            for path in probes.glob("combined-*.json")
        ]
        self.assertEqual(set(strategy_resources), task_resources)
        self.assertEqual(len(strategy_resources), 4)
        self.assertEqual(len(task_resources), 2)

    def test_parallel_worker_resource_errors_cannot_be_skipped(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        with self.assertRaisesRegex(
            BacktestResourceError, "intentional worker memory pressure",
        ):
            self.app.run_backtest(
                strategy=EventWorkerResourceFailure(algorithm_id="pressure"),
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    n_workers=2,
                    continue_on_error=True,
                    min_available_memory_mb=1,
                ),
            )

    def test_public_signatures_expose_inputs_config_filters_and_search(self):
        common = {
            "self", "strategies", "algorithms", "study", "run_configuration",
            "window_metrics_filter_function", "final_metrics_filter_function",
            "optimization",
        }
        self.assertEqual(
            set(inspect.signature(App.run_backtests).parameters), common,
        )
        self.assertEqual(
            set(inspect.signature(App.run_backtest).parameters),
            common | {"strategy", "algorithm"},
        )

    def test_removed_and_individual_run_settings_are_rejected(self):
        removed = {
            "result_mode": "index",
            "window_filter_function": lambda *args: [],
            "final_filter_function": lambda *args: [],
            "batch_size": 50,
            "checkpoint_batch_size": 25,
            "iterative_summary_update": True,
            "anchor_algorithm_id": "anchor",
        }
        removed.update(vars(BacktestRunConfiguration()))
        for method in (self.app.run_backtest, self.app.run_backtests):
            for name, value in removed.items():
                with self.subTest(method=method.__name__, parameter=name):
                    with self.assertRaisesRegex(TypeError, name):
                        method(**{name: value})

    def test_event_results_are_released_and_resume_pruning_is_window_scoped(
        self,
    ):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.study.backtest_windows = [
            BacktestWindow(train_range=BacktestDateRange(
                start_date=start + timedelta(days=i),
                end_date=start + timedelta(days=i + 1),
            )) for i in range(2)
        ]
        strategies = [
            EventIndexStrategy(algorithm_id=f"event-{i}") for i in range(2)
        ]
        references = []
        create = EventBacktestService.create_backtest

        def tracked_create(service, *args, **kwargs):
            gc.collect()
            self.assertTrue(all(ref() is None for ref in references))
            backtest = create(service, *args, **kwargs)
            references.append(weakref.ref(backtest))
            return backtest

        with patch.object(
            EventBacktestService, "create_backtest", new=tracked_create,
        ):
            result = self.app.run_backtest(
                strategies=strategies, study=self.study,
            )
        self.assertEqual(len(references), 4)
        self.assertTrue(all(ref() is None for ref in references))
        self.assertEqual(set(result.df["summary.number_of_windows"]), {2})
        observed = []

        def prune(index, date_range):
            observed.append(index.df.copy())
            return index.filter(lambda row: row["algorithm_id"] == "event-0")

        with patch.object(
            EventLoopService, "start",
            side_effect=AssertionError("completed events must not rerun"),
        ):
            resumed = self.app.run_backtest(
                strategies=strategies,
                study=self.study,
                window_metrics_filter_function=prune,
                final_metrics_filter_function=lambda index: index.filter(
                    lambda row: False,
                ),
                run_configuration=BacktestRunConfiguration(
                    backtest_storage_directory=result.directory,
                    use_checkpoints=True,
                ),
            )
        self.assertEqual(len(observed), 2)
        self.assertEqual(set(observed[0]["summary.number_of_windows"]), {1})
        self.assertEqual(set(observed[1]["summary.number_of_windows"]), {2})
        self.assertEqual(set(observed[1]["algorithm_id"]), {"event-0"})
        self.assertEqual(len(resumed), 0)
        self.assertEqual(
            len(BacktestIndex.open(
                result.directory, filename="backtest_session_index.parquet",
            )), 0,
        )
        self.assertEqual(len(list(result.directory.glob("*.obtf"))), 2)

    def test_event_resource_failure_preserves_completed_checkpoints(self):
        self.study.engines = [BacktestEngine.EVENT_DRIVEN]
        strategies = [
            EventIndexStrategy(algorithm_id=f"event-{i}") for i in range(2)
        ]
        storage = Path(self.storage.name) / "interrupted"
        check = MemoryGuard.check_periodically
        completed = []
        create = EventBacktestService.create_backtest

        def tracked_create(service, *args, **kwargs):
            result = create(service, *args, **kwargs)
            completed.append(result.algorithm_id)
            return result

        def interrupt(guard):
            if completed:
                raise BacktestResourceError("simulated event pressure")
            return check(guard)

        with patch.object(
            MemoryGuard, "check_periodically", new=interrupt,
        ), patch.object(
            EventBacktestService, "create_backtest", new=tracked_create,
        ), self.assertRaisesRegex(BacktestResourceError, "event pressure"):
            self.app.run_backtest(
                strategies=strategies,
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    backtest_storage_directory=storage,
                    min_available_memory_mb=1,
                    continue_on_error=True,
                ),
            )
        self.assertEqual(completed, ["event-0"])
        self.assertTrue((storage / "event-0.obtf").is_file())
        self.assertFalse((storage / "event-1.obtf").exists())
        with patch.object(
            EventBacktestService, "create_backtest", new=tracked_create,
        ):
            resumed = self.app.run_backtest(
                strategies=strategies,
                study=self.study,
                run_configuration=BacktestRunConfiguration(
                    backtest_storage_directory=storage,
                    use_checkpoints=True,
                ),
            )
        self.assertEqual(completed, ["event-0", "event-1"])
        self.assertEqual(resumed.df["algorithm_id"].nunique(), 2)
