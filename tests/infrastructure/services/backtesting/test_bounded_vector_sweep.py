import gc
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
import weakref
from datetime import datetime, timedelta, timezone

import pandas as pd

from investing_algorithm_framework.domain import (
    Backtest, BacktestDateRange, BacktestIndex, BacktestMetrics, BacktestRun,
    BacktestWindow, OperationalException, Study, Universe,
    generate_backtest_summary_metrics,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    .backtest_service import BacktestService
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_resources import BacktestResourceError
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_session_index import make_index, validated_filter


def _result(args):
    strategies, date_range = args[:2]
    assert len(strategies) == 1
    strategy = strategies[0]
    if getattr(strategy, "fail", False):
        raise RuntimeError("synthetic failure")
    window = BacktestWindow(train_range=date_range)
    metrics = BacktestMetrics(
        backtest_window=window, initial_unallocated=1000,
        total_net_gain=float(date_range.start_date.day),
        total_net_gain_percentage=date_range.start_date.day / 100,
        sharpe_ratio=float(date_range.start_date.day),
    )
    run = BacktestRun(
        backtest_window=window, backtest_metrics=metrics,
        initial_unallocated=1000,
    )
    backtest = Backtest(algorithm_id=strategy.algorithm_id)
    study = Study(name="default")
    slot = study.get_engine("vector")
    slot.runs = [run]
    slot.summary = generate_backtest_summary_metrics([metrics])
    backtest._studies["default"] = study
    return [backtest]


class TestBoundedVectorSweep(unittest.TestCase):
    def setUp(self):
        self.directory = Path.cwd() / f".bounded-vector-test-{uuid4().hex}"
        self.directory.mkdir()
        self.addCleanup(shutil.rmtree, self.directory)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.windows = [
            BacktestWindow(train_range=BacktestDateRange(
                start_date=start + timedelta(days=3 * offset),
                end_date=start + timedelta(days=3 * offset + 2),
            )) for offset in range(2)
        ]
        self.study = Study(
            name="memory-test", description="bounded sweep",
            initial_capital=1000, backtest_windows=self.windows,
            universe=Universe(
                symbols=["BTC"], market="TEST", trading_symbol="USD"
            ),
        )
        self.strategies = [
            SimpleNamespace(
                algorithm_id=identifier, data_sources=[],
                symbols=["BTC"], market="TEST",
            ) for identifier in ("first", "second", "third")
        ]
        self.service = BacktestService(
            data_provider_service=SimpleNamespace(), order_service=None,
            portfolio_service=None, portfolio_snapshot_service=None,
            position_repository=None, trade_service=None,
            configuration_service=None,
            portfolio_configuration_service=SimpleNamespace(
                get_all=lambda: []
            ),
        )

    def run_sweep(self, **kwargs):
        defaults = dict(
            strategies=self.strategies, study=self.study,
            backtest_storage_directory=self.directory,
            skip_data_sources_initialization=True,
            result_mode="index",
            batch_size=1,
        )
        defaults.update(kwargs)
        return self.service.run_vector_backtests(**defaults)

    def test_index_equals_legacy_over_two_windows_and_is_reopenable(self):
        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=_result
        ), patch.object(
            self.service, "_load_backtests_from_session",
            side_effect=AssertionError("index must not load final bundles"),
        ):
            index = self.run_sweep()
        reopened = BacktestIndex.open(
            self.directory, filename="backtest_session_index.parquet"
        )
        pd.testing.assert_frame_equal(index.df, reopened.df)
        self.assertEqual(index.df["algorithm_id"].nunique(), 3)
        self.assertEqual(set(index.df["number_of_runs"]), {2})
        self.assertEqual(set(index.df["window_sharpe_ratio"]), {4.0})
        for row in index.df.to_dict("records"):
            self.assertTrue(all(
                value is None or isinstance(value, (str, int, float, bool))
                for value in row.values()
            ))
        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=_result
        ):
            legacy = self.run_sweep(result_mode="list")
        for backtest in legacy:
            study = backtest.get_study(self.study.name)
            self.assertEqual(study.initial_capital, 1000)
            self.assertEqual(len(study.backtest_windows), 2)
            self.assertEqual(study.universe.symbols, ["BTC"])
            flat = next(
                row.to_flat_dict() for row in backtest.index_rows()
                if row.study_name == self.study.name
                and row.engine_type == "vector" and row.universe_key is None
            )
            actual = index.df[
                (index.df["algorithm_id"] == backtest.algorithm_id)
                & index.df["universe_key"].isna()
            ].iloc[0]
            for key, value in flat.items():
                if key.startswith("summary.") and isinstance(
                    value, (int, float)
                ):
                    if pd.isna(value):
                        self.assertTrue(pd.isna(actual[key]))
                    else:
                        self.assertAlmostEqual(actual[key], value)

    def test_resumed_pruning_does_not_see_future_windows(self):
        observed = []

        def capture(index, date_range):
            observed.append(set(index.df["summary.number_of_windows"]))
            return index

        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=_result
        ):
            self.run_sweep(window_metrics_filter_function=capture)
        self.assertEqual(observed, [{1}, {2}])
        observed.clear()
        with patch.object(
            self.service, "_run_batch_backtest_worker",
            side_effect=AssertionError("completed strategy rerun"),
        ):
            self.run_sweep(window_metrics_filter_function=capture)
        self.assertEqual(observed, [{1}, {2}])

    def test_index_sweep_does_not_overwrite_global_index(self):
        global_index = self.directory / "index.parquet"
        original = pd.DataFrame({"algorithm_id": ["unrelated"]})
        original.to_parquet(global_index, index=False)
        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=_result
        ):
            self.run_sweep()
        pd.testing.assert_frame_equal(pd.read_parquet(global_index), original)

    def test_resume_skipped_checkpoints_and_pruning(self):
        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=_result
        ):
            self.run_sweep()
        windows_seen = []

        def prune(index, date_range):
            windows_seen.append(date_range)
            return index.filter(lambda row: row["algorithm_id"] != "third")

        with patch.object(
            self.service, "_run_batch_backtest_worker",
            side_effect=AssertionError("completed strategy rerun"),
        ), patch.object(
            self.service, "_load_backtests_from_session",
            side_effect=AssertionError("bulk reload"),
        ):
            index = self.run_sweep(
                window_metrics_filter_function=prune,
                final_metrics_filter_function=lambda index: index.filter(
                    lambda row: row["algorithm_id"] == "first"
                ),
            )
        self.assertEqual(len(windows_seen), 2)
        self.assertEqual(set(index.df["algorithm_id"]), {"first"})
        cache = json.loads(
            (self.directory / "backtest_session.json").read_text()
        )
        self.assertEqual(set(cache["backtests"]), {"first"})
        for identifier in ("second", "third"):
            self.assertTrue(
                Backtest.open(self.directory / f"{identifier}.obtf")
                .metadata["filtered_out"]
            )

    def test_prompt_checkpoint_and_full_results_released(self):
        refs = []

        def worker(args):
            gc.collect()
            self.assertTrue(all(ref() is None for ref in refs))
            if refs:
                cache = json.loads(
                    (self.directory / "checkpoints.json").read_text()
                )
                self.assertTrue(cache)
            result = _result(args)
            refs.append(weakref.ref(result[0]))
            return result

        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=worker
        ):
            self.run_sweep(batch_size=1, checkpoint_batch_size=100)
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_worker_failure_preserves_completed_checkpoint(self):
        calls = []

        def worker(args):
            calls.append(args[0][0].algorithm_id)
            if len(calls) == 2:
                raise BacktestResourceError("resource failed")
            return _result(args)

        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=worker
        ), self.assertRaisesRegex(BacktestResourceError, "resource failed"):
            self.run_sweep(continue_on_error=True)
        checkpoint = json.loads(
            (self.directory / "checkpoints.json").read_text()
        )
        self.assertEqual(set(next(iter(checkpoint.values()))), {"first"})
        self.assertTrue((self.directory / "first.obtf").exists())

    def test_empty_index_and_empty_pruning(self):
        index = self.run_sweep(strategies=[])
        self.assertEqual(len(index.filter(lambda _: False)), 0)
        self.assertEqual(list(index.iter_backtests()), [])
        with patch.object(
            self.service, "_run_batch_backtest_worker", side_effect=_result
        ) as worker:
            index = self.run_sweep(
                window_metrics_filter_function=lambda index, _: index.filter(
                    lambda row: False
                )
            )
        self.assertEqual(len(index), 0)
        self.assertEqual(worker.call_count, 3)

    def test_validation(self):
        for name in (
            "batch_size", "checkpoint_batch_size", "memory_budget_mb",
            "min_available_memory_mb", "max_tasks_per_child",
        ):
            for value in (0, -1, True, 1.2, float("inf"), "2"):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(OperationalException):
                        self.run_sweep(**{name: value})
        for value in (-2, True, 1.2, "2"):
            with self.assertRaises(OperationalException):
                self.run_sweep(n_workers=value)
        with self.assertRaises(OperationalException):
            self.run_sweep(backtest_storage_directory=None)
        with self.assertRaises(OperationalException):
            self.run_sweep(window_filter_function=lambda *args: [])
        with self.assertRaises(OperationalException):
            self.run_sweep(
                result_mode="list", final_metrics_filter_function=lambda x: x
            )

    def test_filter_rejects_foreign_identity_and_bad_return(self):
        index = make_index(self.directory, [{
            "algorithm_id": "a", "study_name": "ours", "engine_type": "vector",
            "universe_key": None, "bundle_path": "a.obtf",
        }])
        for key, value in (
            ("algorithm_id", "foreign"), ("study_name", "foreign"),
            ("engine_type", "event"),
        ):
            def corrupt(candidate, key=key, value=value):
                candidate.df[key] = value
                return candidate
            with self.assertRaises(OperationalException):
                validated_filter(index, corrupt)
        with self.assertRaises(OperationalException):
            validated_filter(index, lambda index: [])

    def test_memory_error_not_swallowed_by_worker(self):
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.vector_backtest_service import VectorBacktestService
        with patch.object(
            VectorBacktestService, "run", side_effect=MemoryError("allocation")
        ), self.assertRaises(MemoryError):
            self.service._run_batch_backtest_worker((
                self.strategies[:1], self.windows[0].train_range,
                None, None, 0.0, True, SimpleNamespace(), False, False,
            ))
