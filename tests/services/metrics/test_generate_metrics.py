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

    def test_total_loss_is_gross_loss_magnitude(self):
        """Regression test for issue #511 (B1).

        Per-run ``BacktestMetrics.total_loss`` must equal the gross
        loss magnitude (``sum(abs(net_gain))`` over losing trades),
        not the snapshot net-return clamped at zero. In particular,
        ``total_loss`` must equal the ``gross_loss`` field, and
        ``total_loss_percentage`` must be ``total_loss /
        initial_unallocated`` (a non-negative decimal).
        """
        backtest_run = BacktestRun.open(
            os.path.join(self.backtest_run_directory, 'backtest_run_one')
        )
        metrics = create_backtest_metrics(
            backtest_run, risk_free_rate=0.024
        )

        # total_loss is a non-negative magnitude.
        self.assertIsNotNone(metrics.total_loss)
        self.assertGreaterEqual(metrics.total_loss, 0.0)

        # total_loss equals gross_loss (same definition).
        self.assertAlmostEqual(
            metrics.total_loss, metrics.gross_loss or 0.0, places=6
        )

        # total_loss_percentage is non-negative and consistent with
        # total_loss / initial_unallocated.
        if backtest_run.initial_unallocated:
            expected_pct = metrics.total_loss / backtest_run.initial_unallocated
            self.assertAlmostEqual(
                metrics.total_loss_percentage, expected_pct, places=6
            )
            self.assertGreaterEqual(metrics.total_loss_percentage, 0.0)
