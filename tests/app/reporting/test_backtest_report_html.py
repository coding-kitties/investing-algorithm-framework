import os
import tempfile
import shutil
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.app.reporting import BacktestReport
from investing_algorithm_framework.domain import (
    Backtest, BacktestRun, BacktestMetrics, PortfolioSnapshot,
    BacktestDateRange, OperationalException,
)


def _make_backtest(algorithm_id="test_algo", n_runs=1, with_metrics=True):
    """Helper to build a Backtest with realistic data."""
    runs = []
    for j in range(n_runs):
        start = datetime(2023, 1 + j, 1, tzinfo=timezone.utc)
        end = datetime(2023, 6 + j, 1, tzinfo=timezone.utc)
        snapshots = [
            PortfolioSnapshot(
                created_at=start.strftime("%Y-%m-%d %H:%M:%S"),
                total_value=1000,
                trading_symbol="EUR",
                unallocated=1000,
            ),
            PortfolioSnapshot(
                created_at=end.strftime("%Y-%m-%d %H:%M:%S"),
                total_value=1200,
                trading_symbol="EUR",
                unallocated=200,
            ),
        ]
        metrics = None
        if with_metrics:
            metrics = BacktestMetrics(
                backtest_start_date=start,
                backtest_end_date=end,
                equity_curve=[
                    (1000, start),
                    (1200, end),
                ],
                drawdown_series=[
                    (0, start),
                    (-0.05, end),
                ],
                rolling_sharpe_ratio=[
                    (1.0, start),
                    (1.5, end),
                ],
                monthly_returns=[
                    (0.03, datetime(2023, 1, 31, tzinfo=timezone.utc)),
                    (0.02, datetime(2023, 2, 28, tzinfo=timezone.utc)),
                ],
                yearly_returns=[
                    (0.20, datetime(2023, 12, 31, tzinfo=timezone.utc)),
                ],
                total_net_gain=200,
                total_net_gain_percentage=0.20,
                cagr=0.40,
                sharpe_ratio=1.5,
                sortino_ratio=1.8,
                profit_factor=2.0,
                calmar_ratio=2.5,
                annual_volatility=0.15,
                max_drawdown=-0.10,
                max_drawdown_absolute=100,
                max_daily_drawdown=-0.03,
                win_rate=0.60,
                trades_per_year=50,
            )
        runs.append(
            BacktestRun(
                backtest_start_date=start,
                backtest_end_date=end,
                backtest_date_range_name=f"window_{j}",
                orders=[],
                trades=[],
                positions=[],
                portfolio_snapshots=snapshots,
                trading_symbol="EUR",
                initial_unallocated=1000,
                created_at=datetime.now(tz=timezone.utc),
                backtest_metrics=metrics,
            )
        )
    return Backtest(
        algorithm_id=algorithm_id,
        backtest_runs=runs,
        risk_free_rate=0.0,
    )


class TestBacktestReportInit(TestCase):
    """Test BacktestReport construction and backward compatibility."""

    def test_single_backtest_positional(self):
        bt = _make_backtest()
        report = BacktestReport(bt)
        self.assertEqual(len(report.backtests), 1)

    def test_backtests_list(self):
        report = BacktestReport(
            backtests=[_make_backtest("a"), _make_backtest("b")]
        )
        self.assertEqual(len(report.backtests), 2)

    def test_backward_compat_backtest_kwarg_single(self):
        bt = _make_backtest()
        report = BacktestReport(backtest=bt)
        self.assertEqual(len(report.backtests), 1)

    def test_backward_compat_backtest_kwarg_list(self):
        bts = [_make_backtest("a"), _make_backtest("b")]
        report = BacktestReport(backtest=bts)
        self.assertEqual(len(report.backtests), 2)

    def test_empty_raises(self):
        report = BacktestReport()
        with self.assertRaises(OperationalException):
            report.show()


class TestBacktestReportHtml(TestCase):
    """Test HTML generation for single and multi-strategy reports."""

    def test_single_strategy_html_contains_key_elements(self):
        report = BacktestReport(backtests=[_make_backtest()])
        html = report._build_html()
        # Title
        self.assertIn("Backtest Report", html)
        # CSS inlined
        self.assertIn("--bg:", html)
        # JS data constants
        self.assertIn("const IS_SINGLE = true", html)
        self.assertIn("const STRATEGIES", html)
        self.assertIn("const RUN_DATA", html)
        self.assertIn("const WINDOWS_META", html)
        self.assertIn("const RUN_LABELS", html)
        # Strategy name present
        self.assertIn("test_alg", html)
        # No compare page for single
        self.assertNotIn('id="page-compare"', html)

    def test_multi_strategy_html_contains_compare(self):
        report = BacktestReport(
            backtests=[_make_backtest("alpha"), _make_backtest("beta")]
        )
        html = report._build_html()
        self.assertIn("Strategy Comparison", html)
        self.assertIn("const IS_SINGLE = false", html)
        self.assertIn('id="page-compare"', html)
        self.assertIn("alpha", html)
        self.assertIn("beta", html)

    def test_html_has_overview_kpis(self):
        report = BacktestReport(backtests=[_make_backtest()])
        html = report._build_html()
        self.assertIn("Best CAGR", html)
        self.assertIn("Best Sharpe", html)
        self.assertIn("Lowest Max DD", html)

    def test_html_has_strategy_pages(self):
        bt1 = _make_backtest("strat_a")
        bt2 = _make_backtest("strat_b")
        report = BacktestReport(backtests=[bt1, bt2])
        html = report._build_html()
        self.assertIn('id="page-strat-0"', html)
        self.assertIn('id="page-strat-1"', html)

    def test_html_has_finterion_page(self):
        report = BacktestReport(backtests=[_make_backtest()])
        html = report._build_html()
        self.assertIn('id="page-finterion"', html)
        self.assertIn("finterion.com", html)

    def test_html_self_contained_no_external_deps(self):
        report = BacktestReport(backtests=[_make_backtest()])
        html = report._build_html()
        # No CDN/external script or stylesheet links
        self.assertNotIn("cdn.jsdelivr", html)
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("plotly", html.lower().split("finterion")[0])
        # CSS is inline, not linked
        self.assertNotIn('<link rel="stylesheet"', html)

    def test_without_metrics(self):
        report = BacktestReport(
            backtests=[_make_backtest(with_metrics=False)]
        )
        html = report._build_html()
        self.assertIn("Backtest Report", html)
        self.assertIn("const STRATEGIES", html)


class TestBacktestReportSave(TestCase):
    """Test saving the HTML report to disk."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_save_creates_file(self):
        report = BacktestReport(backtests=[_make_backtest()])
        path = os.path.join(self.tmp_dir, "report.html")
        report.save(path)
        self.assertTrue(os.path.isfile(path))

        with open(path) as f:
            content = f.read()
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("const STRATEGIES", content)

    def test_save_caches_html(self):
        report = BacktestReport(backtests=[_make_backtest()])
        path = os.path.join(self.tmp_dir, "report.html")
        report.save(path)
        # html_report should be cached now
        self.assertIsNotNone(report.html_report)


class TestBacktestReportDataTransform(TestCase):
    """Test data transformation methods."""

    def setUp(self):
        self.report = BacktestReport(
            backtests=[_make_backtest("algo_x", n_runs=2)]
        )

    def test_strategies_data(self):
        strategies = self.report._build_strategies_data()
        self.assertEqual(len(strategies), 1)
        s = strategies[0]
        self.assertEqual(s["id"], "strat-0")
        self.assertEqual(s["name"], "algo_x")
        self.assertEqual(s["color"], "#22d3ee")
        self.assertEqual(len(s["runIds"]), 2)
        self.assertIn("summary", s)
        self.assertIn("repEQ", s)
        # repEQ should have percentage values
        if s["repEQ"]:
            self.assertEqual(s["repEQ"][0][0], 0.0)  # starts at 0%

    def test_run_data(self):
        run_data = self.report._build_run_data()
        self.assertEqual(len(run_data), 2)
        self.assertIn("run-0-0", run_data)
        self.assertIn("run-0-1", run_data)
        r = run_data["run-0-0"]
        self.assertIn("EQ", r)
        self.assertIn("DD", r)
        self.assertIn("RS", r)
        self.assertIn("MR", r)
        self.assertIn("YR", r)
        self.assertIn("MONTHLY_HEATMAP", r)
        self.assertIn("TRADES", r)
        self.assertIn("metrics", r)
        self.assertIn("snapshot", r)

    def test_windows_meta(self):
        windows = self.report._build_windows_meta()
        self.assertEqual(len(windows), 2)
        w = windows[0]
        self.assertIn("label", w)
        self.assertIn("start", w)
        self.assertIn("end", w)
        self.assertIn("days", w)

    def test_run_labels(self):
        labels = self.report._build_run_labels()
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0][0], "window_0")
        self.assertEqual(labels[1][0], "window_1")

    def test_equity_curve_pct_growth(self):
        run_data = self.report._build_run_data()
        eq = run_data["run-0-0"]["EQ"]
        # First point: (1000/1000 - 1)*100 = 0%
        self.assertAlmostEqual(eq[0][0], 0.0)
        # Second point: (1200/1000 - 1)*100 = 20%
        self.assertAlmostEqual(eq[1][0], 20.0)

    def test_multi_strategy_data(self):
        report = BacktestReport(
            backtests=[_make_backtest("a"), _make_backtest("b")]
        )
        strategies = report._build_strategies_data()
        self.assertEqual(len(strategies), 2)
        self.assertEqual(strategies[0]["name"], "a")
        self.assertEqual(strategies[1]["name"], "b")
        self.assertNotEqual(
            strategies[0]["color"], strategies[1]["color"]
        )
        run_data = report._build_run_data()
        self.assertIn("run-0-0", run_data)
        self.assertIn("run-1-0", run_data)


class TestBacktestReportOpen(TestCase):
    """Test loading backtests from disk via open()."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_open_with_backtest_objects(self):
        bt = _make_backtest()
        report = BacktestReport.open(backtests=[bt])
        self.assertEqual(len(report.backtests), 1)

    def test_open_empty_directory_raises(self):
        with self.assertRaises(OperationalException):
            BacktestReport.open(directory_path=self.tmp_dir)

    def test_open_invalid_backtest_raises(self):
        with self.assertRaises(OperationalException):
            BacktestReport.open(backtests=["not_a_backtest"])
