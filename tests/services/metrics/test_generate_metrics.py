import os
from unittest import TestCase

from investing_algorithm_framework import create_backtest_metrics, BacktestRun

class TestGenerateMetrics(TestCase):
    def setUp(self):
        # Must point to /tests/resources
        self.resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        self.test_data_directory = os.path.join(
            self.resource_directory, 'test_data'
        )
        self.backtest_run_directory = os.path.join(
            self.test_data_directory, 'backtest_runs'
        )

    def test_generate_metrics(self):
        # This is a placeholder for the actual test implementation
        backtest_run = BacktestRun.open(
            os.path.join(self.backtest_run_directory, 'backtest_run_one')
        )
        backtest_metrics = create_backtest_metrics(
            backtest_run, risk_free_rate=0.024
        )
        print(backtest_metrics.win_rate)
        print(backtest_metrics.win_loss_ratio)
        print(backtest_metrics.profit_factor)
