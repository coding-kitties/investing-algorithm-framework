"""
Tests for Backtest.save() and BacktestRun.save() domain operations.

These tests construct domain objects manually and verify that the
save method produces the expected directory structure and files.

Moved from: tests/app/reporting/test_backtest_report.py
"""
import json
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

    def _make_run(self, start, end, name, total_net_gain, trades_closed,
                  win_rate, gross_profit, gross_loss):
        """Helper: build a BacktestRun with pre-computed metrics."""
        date_range = BacktestDateRange(
            start_date=start, end_date=end, name=name
        )
        return BacktestRun(
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
                backtest_start_date=start.replace(tzinfo=None),
                backtest_end_date=end.replace(tzinfo=None),
                total_net_gain=total_net_gain,
                total_net_gain_percentage=total_net_gain / 1000.0,
                number_of_trades=trades_closed,
                number_of_trades_closed=trades_closed,
                win_rate=win_rate,
                gross_profit=gross_profit,
                gross_loss=gross_loss,
                total_number_of_days=365,
            ),
        )

    def test_save_multi_window_summary_aggregates_all_runs(self):
        """Regression test for issue #511.

        When saving a Backtest containing multiple BacktestRun instances
        (e.g. a walk-forward run), `summary.json` must reflect the
        aggregate of all runs — not just one of them. Specifically:
        - number_of_windows == len(runs)
        - total_net_gain == sum(per-run total_net_gain)
        - number_of_trades_closed == sum(per-run number_of_trades_closed)
        """
        runs = [
            self._make_run(
                start=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end=datetime(2023, 12, 31, tzinfo=timezone.utc),
                name="window-1",
                total_net_gain=499.21,
                trades_closed=56,
                win_rate=0.393,
                gross_profit=900.0,
                gross_loss=-400.79,
            ),
            self._make_run(
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 12, 31, tzinfo=timezone.utc),
                name="window-2",
                total_net_gain=222.75,
                trades_closed=63,
                win_rate=0.333,
                gross_profit=600.0,
                gross_loss=-377.25,
            ),
            self._make_run(
                start=datetime(2025, 1, 1, tzinfo=timezone.utc),
                end=datetime(2025, 12, 31, tzinfo=timezone.utc),
                name="window-3",
                total_net_gain=-24.75,
                trades_closed=57,
                win_rate=0.316,
                gross_profit=300.0,
                gross_loss=-324.75,
            ),
        ]

        # Simulate the buggy upstream pre-condition: backtest_summary
        # was set from a single window only.
        from investing_algorithm_framework.domain.backtesting \
            .combine_backtests import generate_backtest_summary_metrics

        stale_summary = generate_backtest_summary_metrics(
            [runs[-1].backtest_metrics]
        )

        backtest = Backtest(
            algorithm_id="alg-511",
            backtest_runs=runs,
            backtest_summary=stale_summary,
            risk_free_rate=0.0,
        )
        backtest.save(self.output_path)

        summary_path = os.path.join(self.output_path, "summary.json")
        self.assertTrue(os.path.exists(summary_path))

        with open(summary_path, "r") as f:
            summary = json.load(f)

        self.assertEqual(summary["number_of_windows"], 3)
        self.assertAlmostEqual(
            summary["total_net_gain"],
            499.21 + 222.75 + -24.75,
            places=4,
        )
        self.assertEqual(
            summary["number_of_trades_closed"], 56 + 63 + 57
        )
        self.assertEqual(summary["number_of_profitable_windows"], 2)
        self.assertEqual(summary["number_of_windows_with_trades"], 3)

    def test_merge_rebuilds_summary_from_all_runs(self):
        """Regression test for issue #511.

        `Backtest.merge()` previously called the non-existent
        `BacktestSummaryMetrics.add()` method, which silently produced
        a wrong / stale summary. After merging, the summary must
        aggregate the runs from both backtests.
        """
        run_a = self._make_run(
            start=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end=datetime(2023, 12, 31, tzinfo=timezone.utc),
            name="window-a",
            total_net_gain=100.0,
            trades_closed=10,
            win_rate=0.5,
            gross_profit=200.0,
            gross_loss=-100.0,
        )
        run_b = self._make_run(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, tzinfo=timezone.utc),
            name="window-b",
            total_net_gain=50.0,
            trades_closed=20,
            win_rate=0.4,
            gross_profit=150.0,
            gross_loss=-100.0,
        )

        bt_a = Backtest(algorithm_id="alg-511", backtest_runs=[run_a])
        bt_b = Backtest(algorithm_id="alg-511", backtest_runs=[run_b])

        merged = bt_a.merge(bt_b)

        self.assertEqual(len(merged.backtest_runs), 2)
        self.assertIsNotNone(merged.backtest_summary)
        self.assertEqual(merged.backtest_summary.number_of_windows, 2)
        self.assertAlmostEqual(
            merged.backtest_summary.total_net_gain, 150.0, places=4
        )
        self.assertEqual(
            merged.backtest_summary.number_of_trades_closed, 30
        )
