import unittest

from investing_algorithm_framework import (
    BacktestRunConfiguration, SnapshotInterval,
)
from investing_algorithm_framework.domain import ImproperlyConfigured


class TestBacktestRunConfiguration(unittest.TestCase):

    def test_defaults_enable_resumable_visible_runs(self):
        configuration = BacktestRunConfiguration()

        self.assertTrue(configuration.continue_on_error)
        self.assertTrue(configuration.use_checkpoints)
        self.assertTrue(configuration.show_progress)
        self.assertEqual(
            configuration.snapshot_interval, SnapshotInterval.DAILY,
        )
        self.assertFalse(configuration.skip_data_sources_initialization)
        self.assertFalse(configuration.dynamic_position_sizing)
        self.assertTrue(configuration.fill_missing_data)
        self.assertEqual(configuration.max_tasks_per_child, 16)
        self.assertIsNone(configuration.backtest_storage_directory)
        self.assertIsNone(configuration.n_workers)

    def test_from_env_parses_all_settings(self):
        configuration = BacktestRunConfiguration.from_env(
            environment={
                "IAF_BACKTEST_CONTINUE_ON_ERROR": "false",
                "IAF_BACKTEST_USE_CHECKPOINTS": "0",
                "IAF_BACKTEST_STORAGE_DIRECTORY": "/tmp/backtests",
                "IAF_BACKTEST_SHOW_PROGRESS": "no",
                "IAF_BACKTEST_N_WORKERS": "8",
                "IAF_BACKTEST_MEMORY_BUDGET_MB": "16384",
                "IAF_BACKTEST_MIN_AVAILABLE_MEMORY_MB": "4096",
                "IAF_BACKTEST_SNAPSHOT_INTERVAL": "strategy_iteration",
                "IAF_BACKTEST_SKIP_DATA_SOURCES_INITIALIZATION": "true",
                "IAF_BACKTEST_DYNAMIC_POSITION_SIZING": "yes",
                "IAF_BACKTEST_FILL_MISSING_DATA": "off",
                "IAF_BACKTEST_MAX_TASKS_PER_CHILD": "3",
            }
        )

        self.assertFalse(configuration.continue_on_error)
        self.assertFalse(configuration.use_checkpoints)
        self.assertEqual(
            configuration.backtest_storage_directory, "/tmp/backtests"
        )
        self.assertFalse(configuration.show_progress)
        self.assertEqual(configuration.n_workers, 8)
        self.assertEqual(configuration.memory_budget_mb, 16384)
        self.assertEqual(configuration.min_available_memory_mb, 4096)
        self.assertEqual(
            configuration.snapshot_interval,
            SnapshotInterval.STRATEGY_ITERATION,
        )
        self.assertTrue(configuration.skip_data_sources_initialization)
        self.assertTrue(configuration.dynamic_position_sizing)
        self.assertFalse(configuration.fill_missing_data)
        self.assertEqual(configuration.max_tasks_per_child, 3)

    def test_from_env_supports_custom_prefix(self):
        configuration = BacktestRunConfiguration.from_env(
            prefix="TEST_",
            environment={"TEST_N_WORKERS": "4"},
        )

        self.assertEqual(configuration.n_workers, 4)

    def test_from_env_rejects_invalid_boolean(self):
        with self.assertRaises(ImproperlyConfigured):
            BacktestRunConfiguration.from_env(
                environment={"IAF_BACKTEST_USE_CHECKPOINTS": "sometimes"}
            )

    def test_removed_summary_flag_is_not_accepted(self):
        with self.assertRaisesRegex(TypeError, "iterative_summary_update"):
            BacktestRunConfiguration(**{"iterative_summary_update": True})

    def test_from_env_can_disable_worker_recycling(self):
        configuration = BacktestRunConfiguration.from_env(
            environment={"IAF_BACKTEST_MAX_TASKS_PER_CHILD": "None"},
        )
        self.assertIsNone(configuration.max_tasks_per_child)

    def test_invalid_runtime_settings_are_rejected(self):
        for settings in (
            {"max_tasks_per_child": 0},
            {"snapshot_interval": "DAILY"},
            {"n_workers": -2},
            {"memory_budget_mb": 0},
        ):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    BacktestRunConfiguration(**settings)


if __name__ == "__main__":
    unittest.main()
