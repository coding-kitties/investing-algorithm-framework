"""
Tests for Backtest.save() and BacktestRun.save() domain operations.

These tests construct domain objects manually and verify that the
save method produces the expected directory structure and files.

Moved from: tests/app/reporting/test_backtest_report.py
"""
import os
import shutil
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.domain import BacktestRun, \
    BacktestDateRange, PortfolioSnapshot, Backtest, BacktestMetrics


class TestBacktestSave(TestCase):

    def setUp(self):
        self.resource_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "resources"
        )
        self.output_path = os.path.join(self.resource_dir, "backtest_report")

    def tearDown(self):
        if os.path.exists(self.output_path):
            shutil.rmtree(self.output_path)

    def _create_snapshots(self):
        return [
            PortfolioSnapshot(
                created_at="2023-08-07 07:00:00",
                total_value=1000,
                trading_symbol="EUR",
                unallocated=1000,
            ),
            PortfolioSnapshot(
                created_at="2023-12-02 00:00:00",
                total_value=1200,
                trading_symbol="EUR",
                unallocated=200,
            )
        ]

    def _create_date_range(self):
        return BacktestDateRange(
            start_date=datetime(2023, 8, 7, 7, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc),
            name="Test Backtest Date Range"
        )

    def test_save_without_metrics(self):
        """Test saving a Backtest with a BacktestRun that has no
        pre-computed metrics (metrics are computed during save)."""
        date_range = self._create_date_range()
        run = BacktestRun(
            backtest_start_date=date_range.start_date,
            backtest_end_date=date_range.end_date,
            backtest_date_range_name=date_range.name,
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=self._create_snapshots(),
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000,
            created_at=datetime.now(tz=timezone.utc)
        )
        backtest = Backtest(
            algorithm_id="alg-025",
            backtest_runs=[run],
        )
        backtest.save(self.output_path)

        # Check directory structure
        self.assertTrue(os.path.exists(self.output_path))
        runs_dir = os.path.join(self.output_path, "runs")
        self.assertTrue(os.path.exists(runs_dir))

        backtest_run_dir = os.path.join(
            runs_dir, run.create_directory_name()
        )
        self.assertTrue(os.path.exists(backtest_run_dir))
        self.assertTrue(
            os.path.exists(os.path.join(backtest_run_dir, "run.json"))
        )
        # metrics.json is only created when backtest_metrics is provided
        self.assertFalse(
            os.path.exists(os.path.join(backtest_run_dir, "metrics.json"))
        )

    def test_save_with_precomputed_metrics(self):
        """Test saving a Backtest with a BacktestRun that has
        pre-computed BacktestMetrics."""
        date_range = self._create_date_range()
        run = BacktestRun(
            backtest_start_date=date_range.start_date,
            backtest_end_date=date_range.end_date,
            backtest_date_range_name=date_range.name,
            created_at=datetime.now(tz=timezone.utc),
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=self._create_snapshots(),
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000,
            backtest_metrics=BacktestMetrics(
                backtest_start_date=datetime(
                    2023, 8, 7, 7, 59, tzinfo=None
                ),
                backtest_end_date=datetime(
                    2023, 12, 2, 0, 0, tzinfo=None
                ),
                equity_curve=[],
                total_net_gain=0.2,
                cagr=0.1,
                sharpe_ratio=1.5,
                rolling_sharpe_ratio=[],
                sortino_ratio=1.2,
                profit_factor=1.5,
                calmar_ratio=0.8,
                annual_volatility=0.2,
                monthly_returns=[],
                yearly_returns=[],
                drawdown_series=[],
                max_drawdown=0.15,
                max_drawdown_absolute=0.2,
                max_daily_drawdown=0.05
            )
        )
        backtest = Backtest(
            algorithm_id="alg-025",
            backtest_runs=[run],
            risk_free_rate=0.0
        )
        backtest.save(self.output_path)

        # Check directory structure
        self.assertTrue(os.path.exists(self.output_path))
        runs_dir = os.path.join(self.output_path, "runs")
        self.assertTrue(os.path.exists(runs_dir))

        backtest_run_dir = os.path.join(
            runs_dir, run.create_directory_name()
        )
        self.assertTrue(os.path.exists(backtest_run_dir))
        self.assertTrue(
            os.path.exists(os.path.join(backtest_run_dir, "run.json"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(backtest_run_dir, "metrics.json"))
        )
