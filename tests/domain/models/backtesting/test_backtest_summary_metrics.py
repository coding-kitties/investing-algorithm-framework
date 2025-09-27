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

    def test_save(self):
        backtest_metrics = BacktestSummaryMetrics(
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
