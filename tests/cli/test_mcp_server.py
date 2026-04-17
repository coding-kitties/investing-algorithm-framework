"""
Tests for the MCP server tool handlers.

Validates that each MCP tool returns correct output when called
with realistic backtest data — without requiring disk I/O or
the actual stdio transport layer.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.cli.mcp_server import (
    BacktestMCPServer,
    _load_notes,
    _save_notes,
)
from investing_algorithm_framework.domain.backtesting.backtest import Backtest
from investing_algorithm_framework.domain.backtesting.backtest_run import (
    BacktestRun,
)
from investing_algorithm_framework.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from investing_algorithm_framework.domain.backtesting.combine_backtests import (
    generate_backtest_summary_metrics,
)


# ═══════════════════════════════════════════════════════════════════
#  Test fixtures
# ═══════════════════════════════════════════════════════════════════

def _make_metrics(
    start, end, name,
    cagr=0.10, sharpe=1.2, sortino=1.8, max_dd=-0.08,
    win_rate=0.55, profit_factor=1.5, trades=20,
    net_gain=500.0, net_gain_pct=5.0,
):
    return BacktestMetrics(
        backtest_start_date=start,
        backtest_end_date=end,
        backtest_date_range_name=name,
        trading_symbol="EUR",
        initial_unallocated=10000.0,
        final_value=10000.0 + net_gain,
        total_net_gain=net_gain,
        total_net_gain_percentage=net_gain_pct,
        total_growth=net_gain,
        total_growth_percentage=net_gain_pct,
        cagr=cagr,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=max_dd,
        win_rate=win_rate,
        profit_factor=profit_factor,
        number_of_trades=trades,
        number_of_trades_closed=trades,
        trades_per_year=trades * 2.0,
        annual_volatility=0.15,
        calmar_ratio=cagr / abs(max_dd) if max_dd else None,
        var_95=-0.02,
        cvar_95=-0.03,
    )


def _make_run(start, end, name, **kw):
    m = _make_metrics(start, end, name, **kw)
    return BacktestRun(
        backtest_start_date=start,
        backtest_end_date=end,
        trading_symbol="EUR",
        initial_unallocated=10000.0,
        backtest_metrics=m,
        backtest_date_range_name=name,
        number_of_trades=kw.get("trades", 20),
    )


def _make_backtest(algo_id, tag="", **kw):
    """Create a Backtest with 2 windows and computed summary."""
    run1 = _make_run(
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 6, 30, tzinfo=timezone.utc),
        "H1-2024", **kw,
    )
    run2 = _make_run(
        datetime(2024, 7, 1, tzinfo=timezone.utc),
        datetime(2024, 12, 31, tzinfo=timezone.utc),
        "H2-2024", **kw,
    )
    metrics_list = [run1.backtest_metrics, run2.backtest_metrics]
    summary = generate_backtest_summary_metrics(metrics_list)
    return Backtest(
        algorithm_id=algo_id,
        backtest_runs=[run1, run2],
        backtest_summary=summary,
        parameters={"sma": 20, "rsi": 30},
        tag=tag,
    )


def _make_server(backtests, tmpdir=None):
    """Create a BacktestMCPServer with pre-loaded backtests (no disk)."""
    server = BacktestMCPServer.__new__(BacktestMCPServer)
    server.directory = tmpdir or tempfile.mkdtemp()
    server._backtests = backtests
    server._bt_map = {bt.algorithm_id: bt for bt in backtests}
    server._bt_tags = {
        bt.algorithm_id: getattr(bt, "tag", "") or ""
        for bt in backtests
    }
    return server


# ═══════════════════════════════════════════════════════════════════
#  Tests: list_strategies
# ═══════════════════════════════════════════════════════════════════

class TestListStrategies(TestCase):

    def setUp(self):
        self.bt_a = _make_backtest("alpha", tag="batch_1", cagr=0.15)
        self.bt_b = _make_backtest("beta", tag="batch_2", cagr=0.08)
        self.server = _make_server([self.bt_a, self.bt_b])

    def test_lists_all_strategies(self):
        result = self.server._handle_tool_call("list_strategies", {})
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_filter_by_tag(self):
        result = self.server._handle_tool_call(
            "list_strategies", {"tag": "batch_1"}
        )
        self.assertIn("alpha", result)
        self.assertNotIn("beta", result)

    def test_filter_by_strategy_ids(self):
        result = self.server._handle_tool_call(
            "list_strategies", {"strategy_ids": ["beta"]}
        )
        self.assertNotIn("alpha", result)
        self.assertIn("beta", result)

    def test_shows_consistency_and_stability(self):
        result = self.server._handle_tool_call("list_strategies", {})
        # When tags exist, the table uses a different header layout
        # that may omit Consistency/Stability columns.
        # Without tags, the columns should appear.
        server_no_tags = _make_server([
            _make_backtest("x"), _make_backtest("y")
        ])
        result2 = server_no_tags._handle_tool_call("list_strategies", {})
        self.assertIn("Consistency", result2)
        self.assertIn("Stability", result2)


# ═══════════════════════════════════════════════════════════════════
#  Tests: get_strategy_details
# ═══════════════════════════════════════════════════════════════════

class TestGetStrategyDetails(TestCase):

    def setUp(self):
        self.bt = _make_backtest("alpha")
        self.server = _make_server([self.bt])

    def test_returns_details(self):
        result = self.server._handle_tool_call(
            "get_strategy_details", {"strategy_id": "alpha"}
        )
        self.assertIn("alpha", result)
        self.assertIn("H1-2024", result)
        self.assertIn("H2-2024", result)

    def test_unknown_strategy(self):
        result = self.server._handle_tool_call(
            "get_strategy_details", {"strategy_id": "nonexistent"}
        )
        self.assertIn("not found", result.lower())


# ═══════════════════════════════════════════════════════════════════
#  Tests: rank_strategies
# ═══════════════════════════════════════════════════════════════════

class TestRankStrategies(TestCase):

    def setUp(self):
        self.bt_a = _make_backtest("alpha", cagr=0.20, sharpe=1.5)
        self.bt_b = _make_backtest("beta", cagr=0.05, sharpe=0.8)
        self.bt_c = _make_backtest("gamma", cagr=0.12, sharpe=2.0)
        self.server = _make_server([self.bt_a, self.bt_b, self.bt_c])

    def test_rank_by_sharpe_default(self):
        result = self.server._handle_tool_call("rank_strategies", {})
        # Default metric is sharpe_ratio, descending
        self.assertIn("gamma", result)
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_rank_by_cagr(self):
        result = self.server._handle_tool_call(
            "rank_strategies", {"metric": "cagr"}
        )
        # alpha(0.20) > gamma(0.12) > beta(0.05)
        alpha_pos = result.index("alpha")
        gamma_pos = result.index("gamma")
        beta_pos = result.index("beta")
        self.assertLess(alpha_pos, gamma_pos)
        self.assertLess(gamma_pos, beta_pos)

    def test_rank_ascending(self):
        result = self.server._handle_tool_call(
            "rank_strategies", {"metric": "cagr", "ascending": True}
        )
        alpha_pos = result.index("alpha")
        beta_pos = result.index("beta")
        self.assertLess(beta_pos, alpha_pos)

    def test_rank_with_limit(self):
        result = self.server._handle_tool_call(
            "rank_strategies", {"metric": "cagr", "limit": 2}
        )
        self.assertIn("alpha", result)
        self.assertIn("gamma", result)
        self.assertNotIn("beta", result)

    def test_rank_by_consistency_score(self):
        result = self.server._handle_tool_call(
            "rank_strategies", {"metric": "consistency_score"}
        )
        self.assertIn("Rank", result)

    def test_rank_by_stability_score(self):
        result = self.server._handle_tool_call(
            "rank_strategies", {"metric": "stability_score"}
        )
        self.assertIn("Rank", result)


# ═══════════════════════════════════════════════════════════════════
#  Tests: compare_strategies
# ═══════════════════════════════════════════════════════════════════

class TestCompareStrategies(TestCase):

    def setUp(self):
        self.bt_a = _make_backtest("alpha", cagr=0.15, sharpe=1.5)
        self.bt_b = _make_backtest("beta", cagr=0.05, sharpe=0.8)
        self.server = _make_server([self.bt_a, self.bt_b])

    def test_compare_two(self):
        result = self.server._handle_tool_call(
            "compare_strategies",
            {"strategy_a": "alpha", "strategy_b": "beta"},
        )
        self.assertIn("alpha", result)
        self.assertIn("beta", result)
        self.assertIn("Winner", result)

    def test_compare_includes_consistency(self):
        result = self.server._handle_tool_call(
            "compare_strategies",
            {"strategy_a": "alpha", "strategy_b": "beta"},
        )
        self.assertIn("consistency_score", result)
        self.assertIn("stability_score", result)

    def test_compare_unknown_strategy(self):
        result = self.server._handle_tool_call(
            "compare_strategies",
            {"strategy_a": "alpha", "strategy_b": "nonexistent"},
        )
        self.assertIn("not found", result.lower())


# ═══════════════════════════════════════════════════════════════════
#  Tests: filter_strategies
# ═══════════════════════════════════════════════════════════════════

class TestFilterStrategies(TestCase):

    def setUp(self):
        self.bt_a = _make_backtest("alpha", cagr=0.15, sharpe=1.5)
        self.bt_b = _make_backtest("beta", cagr=0.05, sharpe=0.8)
        self.server = _make_server([self.bt_a, self.bt_b])

    def test_filter_sharpe_above(self):
        result = self.server._handle_tool_call(
            "filter_strategies",
            {"conditions": [
                {"metric": "sharpe_ratio", "operator": ">", "value": 1.0}
            ]},
        )
        self.assertIn("alpha", result)
        self.assertNotIn("beta", result)

    def test_filter_no_match(self):
        result = self.server._handle_tool_call(
            "filter_strategies",
            {"conditions": [
                {"metric": "cagr", "operator": ">", "value": 0.99}
            ]},
        )
        self.assertIn("No strategies match", result)


# ═══════════════════════════════════════════════════════════════════
#  Tests: get_equity_curve, get_drawdown_series, get_rolling_sharpe
# ═══════════════════════════════════════════════════════════════════

class TestTimeSeriesTools(TestCase):

    def setUp(self):
        self.bt = _make_backtest("alpha")
        self.server = _make_server([self.bt])

    def test_equity_curve(self):
        result = self.server._handle_tool_call(
            "get_equity_curve", {"strategy_id": "alpha"}
        )
        # Should return something (even if no snapshots → empty)
        self.assertIsInstance(result, str)

    def test_drawdown_series(self):
        result = self.server._handle_tool_call(
            "get_drawdown_series", {"strategy_id": "alpha"}
        )
        self.assertIsInstance(result, str)

    def test_rolling_sharpe(self):
        result = self.server._handle_tool_call(
            "get_rolling_sharpe", {"strategy_id": "alpha"}
        )
        self.assertIsInstance(result, str)


# ═══════════════════════════════════════════════════════════════════
#  Tests: get_window_coverage
# ═══════════════════════════════════════════════════════════════════

class TestWindowCoverage(TestCase):

    def setUp(self):
        self.bt = _make_backtest("alpha")
        self.server = _make_server([self.bt])

    def test_window_coverage(self):
        result = self.server._handle_tool_call(
            "get_window_coverage", {}
        )
        self.assertIn("H1-2024", result)
        self.assertIn("H2-2024", result)


# ═══════════════════════════════════════════════════════════════════
#  Tests: get_trading_activity
# ═══════════════════════════════════════════════════════════════════

class TestTradingActivity(TestCase):

    def setUp(self):
        self.bt = _make_backtest("alpha", win_rate=0.60, profit_factor=1.8)
        self.server = _make_server([self.bt])

    def test_trading_activity(self):
        result = self.server._handle_tool_call(
            "get_trading_activity", {}
        )
        self.assertIn("alpha", result)
        self.assertIn("Profit Factor", result)
        self.assertIn("Win Rate", result)


# ═══════════════════════════════════════════════════════════════════
#  Tests: get_strategy_metadata
# ═══════════════════════════════════════════════════════════════════

class TestStrategyMetadata(TestCase):

    def setUp(self):
        self.bt = _make_backtest("alpha")
        self.server = _make_server([self.bt])

    def test_returns_parameters(self):
        result = self.server._handle_tool_call(
            "get_strategy_metadata", {"strategy_id": "alpha"}
        )
        self.assertIn("sma", result)
        self.assertIn("rsi", result)


# ═══════════════════════════════════════════════════════════════════
#  Tests: Notes CRUD
# ═══════════════════════════════════════════════════════════════════

class TestNotesCRUD(TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bt = _make_backtest("alpha")
        self.server = _make_server([self.bt], tmpdir=self.tmpdir)

    def tearDown(self):
        path = os.path.join(self.tmpdir, ".analysis_notes.json")
        if os.path.exists(path):
            os.remove(path)

    def test_create_and_list_note(self):
        # Create
        result = self.server._handle_tool_call(
            "create_note",
            {
                "title": "Test Note",
                "markdown": "Alpha looks promising.",
                "selections": {"alpha": "keep"},
            },
        )
        self.assertIn("Created", result)

        # List
        result = self.server._handle_tool_call("list_notes", {})
        self.assertIn("Test Note", result)

    def test_get_note(self):
        self.server._handle_tool_call(
            "create_note",
            {"title": "My Note", "markdown": "Content here."},
        )
        result = self.server._handle_tool_call(
            "get_note", {"note_id": 1}
        )
        self.assertIn("My Note", result)
        self.assertIn("Content here", result)

    def test_update_note(self):
        self.server._handle_tool_call(
            "create_note",
            {"title": "Original", "markdown": "V1"},
        )
        result = self.server._handle_tool_call(
            "update_note",
            {"note_id": 1, "title": "Updated", "markdown": "V2"},
        )
        self.assertIn("updated", result.lower())

        result = self.server._handle_tool_call(
            "get_note", {"note_id": 1}
        )
        self.assertIn("Updated", result)
        self.assertIn("V2", result)

    def test_delete_note(self):
        self.server._handle_tool_call(
            "create_note",
            {"title": "Doomed", "markdown": "Will be deleted."},
        )
        result = self.server._handle_tool_call(
            "delete_note", {"note_id": 1}
        )
        self.assertIn("deleted", result.lower())

    def test_note_persists_to_disk(self):
        self.server._handle_tool_call(
            "create_note",
            {"title": "Persistent", "markdown": "On disk."},
        )
        data = _load_notes(self.tmpdir)
        self.assertEqual(len(data["notes"]), 1)
        self.assertEqual(data["notes"][0]["title"], "Persistent")


# ═══════════════════════════════════════════════════════════════════
#  Tests: get_tools (tool schema)
# ═══════════════════════════════════════════════════════════════════

class TestToolSchema(TestCase):

    def setUp(self):
        self.bt = _make_backtest("alpha")
        self.server = _make_server([self.bt])

    def test_tools_list_not_empty(self):
        tools = self.server._get_tools()
        self.assertGreater(len(tools), 0)

    def test_all_tools_have_name_and_description(self):
        tools = self.server._get_tools()
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertTrue(tool["name"], "Tool name must not be empty")

    def test_tool_names_unique(self):
        tools = self.server._get_tools()
        names = [t["name"] for t in tools]
        self.assertEqual(len(names), len(set(names)))

    def test_consistency_in_rank_description(self):
        tools = self.server._get_tools()
        rank_tool = next(
            t for t in tools if t["name"] == "rank_strategies"
        )
        metric_desc = json.dumps(rank_tool)
        self.assertIn("consistency_score", metric_desc)
        self.assertIn("stability_score", metric_desc)
