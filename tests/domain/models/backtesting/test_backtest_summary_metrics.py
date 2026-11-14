from unittest import TestCase
from datetime import datetime, date
import tempfile
from pathlib import Path

from investing_algorithm_framework.domain import BacktestSummaryMetrics, \
    Trade, BacktestMetrics


class TestBacktestMetrics(TestCase):

    def setUp(self):
        # Create a temporary directory for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save(self):
        backtest_metrics = BacktestSummaryMetrics(
            aggregation_semantics_version=2,
            aggregation_mode="independent_windows",
            return_definition="net_pnl_over_initial_capital",
            drawdown_definition="worst_window_positive_magnitude",
            window_count_expected=3,
            window_count_evaluated=3,
            window_count_missing=0,
            complete=True,
            capital_weighted_window_return=0.125,
            median_window_return=0.20,
            worst_window_return=-0.10,
            best_window_return=0.30,
            mean_window_duration_days=60.33,
            duration_weighted_mean_window_cagr=0.42,
            worst_window_max_drawdown=0.25,
            cagr = 0.0,
            sharpe_ratio = 0.0,
            sortino_ratio = 0.0,
            calmar_ratio = 0.0,
            profit_factor = 0.0,
            annual_volatility = 0.0,
            max_drawdown = 0.0,
            max_drawdown_duration = 0,
            trades_per_year = 0.0,
            number_of_trades = 0,
            win_rate = 0.0,
            win_loss_ratio = 0.0,
        )

        file_path = self.dir_path / "summary_metrics.json"
        backtest_metrics.save(file_path)

    def test_open(self):
        backtest_metrics = BacktestSummaryMetrics(
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            annual_volatility=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
        )

        file_path = self.dir_path / "summary_metrics.json"
        backtest_metrics.save(file_path)

        loaded_metrics = BacktestSummaryMetrics.open(file_path)
        self.assertEqual(backtest_metrics.to_dict(), loaded_metrics.to_dict())

    def test_unversioned_summary_remains_legacy_unknown(self):
        loaded_metrics = BacktestSummaryMetrics.from_dict({
            "cagr": 1.5,
            "max_drawdown": 0.2,
        })

        self.assertIsNone(loaded_metrics.aggregation_semantics_version)
        self.assertIsNone(loaded_metrics.aggregation_mode)
        self.assertEqual(loaded_metrics.cagr, 1.5)
