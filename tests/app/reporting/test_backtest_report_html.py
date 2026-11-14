import os
import tempfile
import shutil
import subprocess
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest import TestCase, skipUnless

from investing_algorithm_framework.app.reporting import BacktestReport
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange
from investing_algorithm_framework.domain import (
    Backtest, BacktestRun, BacktestMetrics, PortfolioSnapshot,
    BacktestDateRange, OperationalException, PositionSnapshot,
    Order, Trade,
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
        window = BacktestWindow(
            train_range=BacktestDateRange(
                start_date=start,
                end_date=end,
                name=f"window_{j}",
            )
        )
        metrics = None
        if with_metrics:
            metrics = BacktestMetrics(
                backtest_window=window,
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
                backtest_window=window,
                orders=[],
                trades=[],
                positions=[],
                portfolio_snapshots=snapshots,
                initial_unallocated=1000,
                created_at=datetime.now(tz=timezone.utc),
                backtest_metrics=metrics,
            )
        )
    return Backtest(
        algorithm_id=algorithm_id,
        vector_runs=runs,
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


class TestBacktestReportPrettyPrint(TestCase):

    def test_omits_signal_rejections_when_empty(self):
        output = StringIO()

        with redirect_stdout(output):
            BacktestReport(backtests=[_make_backtest()]).pretty_print()

        self.assertEqual(output.getvalue(), "")

    def test_prints_signal_rejection_summary(self):
        backtest = _make_backtest(n_runs=2)
        first_run, second_run = backtest.vector_runs
        first_run.signal_events = [
            {
                "date": datetime(2023, 1, 2, tzinfo=timezone.utc),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "cooldown",
            },
            {
                "date": datetime(2023, 1, 3, tzinfo=timezone.utc),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "already_in_position",
            },
        ]
        second_run.signal_events = [
            {
                "date": datetime(2023, 2, 2, tzinfo=timezone.utc),
                "symbol": "ETH",
                "signal": "sell",
                "executed": False,
                "reason": "cooldown",
            },
        ]
        output = StringIO()

        with redirect_stdout(output):
            BacktestReport(backtests=[backtest]).pretty_print()

        self.assertEqual(
            output.getvalue(),
            "Signal rejections:\n"
            "  already_in_position : 1\n"
            "  cooldown            : 2\n"
            "  Total rejected      : 3\n",
        )


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
        # Strategy pages are lazy-rendered by JS on first visit;
        # verify the container and strategy data are present.
        self.assertIn('id="strategy-pages-container"', html)
        self.assertIn('strat-0', html)
        self.assertIn('strat-1', html)

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

        with open(path, encoding="utf-8") as f:
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
        self.assertIn("SIGNAL_REJECTIONS", r)
        self.assertIn("metrics", r)
        self.assertIn("snapshot", r)

    def test_run_data_includes_net_gross_and_side_exposure(self):
        run = self.report.backtests[0].vector_runs[0]
        snapshots = run.portfolio_snapshots.materialize()
        snapshots[-1].position_snapshots = [PositionSnapshot(
            symbol="BTC/EUR",
            amount=0.5,
            cost=200.0,
            long_amount=2.0,
            short_amount=1.5,
            long_cost=200.0,
            short_cost=165.0,
        )]
        run.portfolio_snapshots = snapshots

        snapshot = self.report._build_run_data()["run-0-0"]["snapshot"]

        self.assertEqual(200.0, snapshot["long_exposure"])
        self.assertEqual(165.0, snapshot["short_exposure"])
        self.assertEqual(35.0, snapshot["net_exposure"])
        self.assertEqual(365.0, snapshot["gross_exposure"])

    def test_run_data_includes_only_rejected_signal_events(self):
        report = BacktestReport(backtests=[_make_backtest()])
        run = report.backtests[0].vector_runs[0]
        run.signal_events = [
            {
                "date": datetime(2023, 1, 2, 8, 30, tzinfo=timezone.utc),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "cooldown",
            },
            {
                "date": datetime(2023, 1, 3, tzinfo=timezone.utc),
                "symbol": "BTC",
                "signal": "buy",
                "executed": True,
                "reason": "executed",
            },
        ]

        rejections = report._build_run_data()[
            "run-0-0"
        ]["SIGNAL_REJECTIONS"]

        self.assertEqual(rejections, [{
            "date": "2023-01-02T08:30:00+00:00",
            "sym": "BTC",
            "signal": "buy",
            "reason": "cooldown",
        }])

    def test_html_renders_rejections_as_grey_x_markers(self):
        html = self.report._build_html()

        self.assertIn("p.series === 'rejected'", html)
        self.assertIn("color: '#9ca3af', shape: 'x'", html)
        self.assertIn("ctx.lineWidth = 1", html)

    def test_run_data_preserves_intraday_trade_and_order_timestamps(self):
        opened = datetime(2023, 1, 2, 8, 30, tzinfo=timezone.utc)
        updated = opened + timedelta(hours=1)
        closed = opened + timedelta(hours=2)
        order = Order(
            order_type="LIMIT", order_side="BUY", amount=1, price=100,
            target_symbol="BTC", trading_symbol="EUR",
            created_at=opened, updated_at=updated,
        )
        trade = Trade(
            id=1, orders=[order], target_symbol="BTC", trading_symbol="EUR",
            opened_at=opened, closed_at=closed, open_price=100,
            amount=1, available_amount=0, cost=100, remaining=0,
            filled_amount=1, status="CLOSED",
        )
        run = self.report.backtests[0].vector_runs[0]
        run.orders = [order]
        run.trades = [trade]

        data = self.report._build_run_data()["run-0-0"]

        self.assertEqual(data["TRADES"][0]["opened"], opened.isoformat())
        self.assertEqual(data["TRADES"][0]["closed"], closed.isoformat())
        self.assertEqual(data["ORDERS"][0]["created"], opened.isoformat())
        self.assertEqual(data["ORDERS"][0]["updated"], updated.isoformat())

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

    def test_dual_engine_backtest_produces_two_strategy_entries(self):
        """Stage 6: vector + event slots render as separate pages."""
        bt = _make_backtest("dual", n_runs=1)
        # Promote the legacy compat-shimmed runs into both engines.
        vector_runs = list(bt.vector_runs)
        bt.event_runs = list(vector_runs)
        bt.vector_summary = None
        bt.event_summary = None
        # Sanity: bundle now reports both engines populated.
        self.assertEqual(sorted(bt.engines()), ["event", "vector"])

        report = BacktestReport(backtests=[bt])
        strategies = report._build_strategies_data()
        self.assertEqual(len(strategies), 2)
        names = {s["name"] for s in strategies}
        self.assertIn("dual (vector)", names)
        self.assertIn("dual (event)", names)
        # Strategy IDs stay contiguous across engine views.
        self.assertEqual(strategies[0]["id"], "strat-0")
        self.assertEqual(strategies[1]["id"], "strat-1")
        # Each engine view owns its own run IDs.
        run_data = report._build_run_data()
        self.assertIn("run-0-0", run_data)
        self.assertIn("run-1-0", run_data)

        html = report._build_html()
        # Dual-engine bundle behaves as a comparison view.
        self.assertIn("const IS_SINGLE = false", html)
        self.assertIn("dual (vector)", html)
        self.assertIn("dual (event)", html)

    def test_separate_engine_bundles_have_distinct_labels(self):
        vector = _make_backtest("same_algo")
        event = Backtest(
            algorithm_id="same_algo", event_runs=list(vector.vector_runs),
        )
        report = BacktestReport(backtests=[vector, event])

        strategies = report._build_strategies_data()

        self.assertEqual(
            [strategy["name"] for strategy in strategies],
            ["same_alg (vector)", "same_alg (event)"],
        )
        self.assertEqual(
            set(report._build_run_data()), {"run-0-0", "run-1-0"},
        )


@skipUnless(shutil.which("node"), "Dashboard behavior tests require Node.js")
class TestDashboardJavascript(TestCase):
    def run_javascript(self, code):
        dashboard = Path(__file__).parents[3] / (
            "investing_algorithm_framework/app/reporting/templates/dashboard.js"
        )
        harness = """
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
function load(name) {
  const start = source.indexOf('function ' + name + '(');
  assert.ok(start >= 0, name);
  const end = source.indexOf('\\nfunction ', start + 1);
  vm.runInThisContext(source.slice(start, end < 0 ? source.length : end));
}
global.initCollapseButtons = () => {};
"""
        result = subprocess.run(
            ["node", "-e", harness + code, str(dashboard)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_monthly_returns_compound_in_rows_and_heatmap(self):
        self.run_javascript("""
load('compoundMonthlyReturns');
load('buildStratMonthlyReturns');
load('buildCompareMonthlyReturns');
global.STRATEGIES = [
  {name: 'vector', runIds: ['run'], runNameMap: {}},
  {name: 'event', runIds: ['run'], runNameMap: {}},
];
global.stratSelectedRun = {};
global.stratMonthlyData = {};
global.stratMonthlyDisplay = {};
global.stratMonthlyYear = {};
global.compareMonthlyData = 'returns';
global.compareMonthlyYear = 'all';
global.challengerIdx = -1;
global.getViewRunData = () => RUN_DATA.run;
const container = {innerHTML: ''};
global.document = {getElementById: () => container};
for (const [months, expected] of [
  [{1: 10, 2: -10}, '-1.0%'],
  [{1: 10, 3: 10}, '+21.0%'],
  [{1: -100, 2: 50}, '-100.0%'],
]) {
  global.RUN_DATA = {run: {MONTHLY_HEATMAP: {2024: months}}};
  for (const display of ['rows', 'heatmap']) {
    stratMonthlyDisplay[0] = display;
    buildStratMonthlyReturns(0);
    assert.ok(container.innerHTML.includes(expected), container.innerHTML);
    global.compareMonthlyDisplay = display;
    buildCompareMonthlyReturns([0, 1]);
    assert.ok(container.innerHTML.includes(expected), container.innerHTML);
  }
}
""")

    def test_trading_ranking_displays_hour_based_duration(self):
        self.run_javascript("""
load('fmtDuration');
load('rebuildOverviewTradingActivity');
global.selectedForCompare = new Set();
global.tradingSortCol = null;
global.challengerIdx = -1;
global.STRATEGIES = [{name: 'strategy', color: '#fff'}];
global.TRADING_COLS = [['Avg Duration', 'average_trade_duration', 'ratio', 'neutral']];
global.getViewMetrics = () => ({average_trade_duration: 16.128});
const container = {innerHTML: ''};
global.document = {getElementById: id => id === 'overview-trading-activity' ? container : null};
rebuildOverviewTradingActivity();
assert.ok(container.innerHTML.includes('16h'), container.innerHTML);
assert.ok(!container.innerHTML.includes('16.1d'));
""")

    def test_equity_correlations_align_dates_and_keep_engine_labels(self):
        self.run_javascript("""
load('equityCorrelation');
load('buildCorrelationMatrix');
load('buildCompareCorrelation');
const a = [[0, '2024-01-01'], [1, '2024-01-02'], [9, '2024-01-02'], [5, '2024-01-03']];
const b = [[-100, '2023-12-31'], [0, '2024-01-01'], [18, '2024-01-02'], [10, '2024-01-03']];
assert.equal(equityCorrelation(a, b), 1);
assert.equal(equityCorrelation(a, b.slice(0, 2)), null);
assert.equal(equityCorrelation(a, [[1, '2024-01-01'], [1, '2024-01-02'], [1, '2024-01-03']]), null);
global.STRATEGIES = [{name: 'confluen (vector)'}, {name: 'confluen (event)'}];
global.selectedRunView = 'window';
global.selectedForCompare = new Set([0, 1]);
global.getViewEquity = i => i === 0 ? a : b;
global.getViewRunData = i => ({EQ: getViewEquity(i)});
const container = {innerHTML: ''};
global.document = {getElementById: () => container};
for (const render of [buildCorrelationMatrix, () => buildCompareCorrelation([0, 1])]) {
  render();
  for (const strategy of STRATEGIES) {
    assert.ok(container.innerHTML.includes('>' + strategy.name + '</th>'), container.innerHTML);
  }
}
""")

    def test_timeline_retains_asset_on_redraw_and_clears_missing_asset(self):
        self.run_javascript("""
load('buildTimelineScatter');
global.getStratRunData = () => ({
  ORDERS: [{created: '2024-01-01T08:00:00+00:00', price: 100, sym: 'BTC', side: 'BUY'}],
});
const container = {innerHTML: ''};
const select = {value: 'BTC', addEventListener: () => {}};
global.document = {getElementById: id => id === 'strat-0-timeline-scatter' ? container : select};
let selected;
global._drawTimelineCanvas = (sid, points, symbol) => {selected = symbol;};
buildTimelineScatter(0);
assert.equal(selected, 'BTC');
assert.ok(container.innerHTML.includes('value="BTC" selected'));
select.value = 'ETH';
buildTimelineScatter(0);
assert.equal(selected, '');
""")


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
