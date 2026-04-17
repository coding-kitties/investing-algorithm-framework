"""
MCP Server for Backtest Analysis

Exposes backtest data to LLMs (GitHub Copilot, Claude, ChatGPT)
via the Model Context Protocol.

Usage:
    # Standalone (single directory)
    python -m investing_algorithm_framework.cli.mcp_server \
        -d examples/batch_one

    # Multiple directories
    python -m investing_algorithm_framework.cli.mcp_server \
        -d examples/batch_one -d examples/batch_two

    # Via CLI
    investing-algorithm-framework mcp -d examples/batch_one

Configure in VS Code (.vscode/mcp.json):
    {
      "servers": {
        "backtest-analysis": {
          "command": "python",
          "args": [
            "-m", "investing_algorithm_framework.cli.mcp_server",
            "-d", "examples/batch_one",
            "-d", "examples/batch_two"
          ]
        }
      }
    }
"""
import sys
import json
import os
import argparse
from typing import Optional, List, Union


def _load_backtests(directory: Union[str, List[str]]):
    """Load and recalculate backtests from directory(ies)."""
    from investing_algorithm_framework import (
        BacktestReport, recalculate_backtests,
    )

    # Normalize to a list of directories
    if isinstance(directory, str):
        # Support comma-separated directories for backward compatibility
        dirs = [d.strip() for d in directory.split(',') if d.strip()]
    else:
        dirs = [d.strip() for d in directory if d.strip()]

    if len(dirs) == 1:
        report = BacktestReport.open(directory_path=dirs[0])
    else:
        report = BacktestReport.open(directory_path=dirs)
    recalculate_backtests(report.backtests)
    return report.backtests, report._source_tags


def _fmt_pct(v):
    if v is None:
        return "—"
    return f"{v * 100:.2f}%"


def _fmt_dec(v, decimals=2):
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def _strategy_summary(bt):
    """Build a summary dict for one Backtest."""
    s = bt.backtest_summary
    summary = {}
    if s:
        summary = s.to_dict()
    return {
        "algorithm_id": bt.algorithm_id,
        "parameters": bt.parameters or {},
        "num_windows": len(bt.backtest_runs),
        "summary": summary,
    }


def _metrics_table(bt):
    """Build a markdown metrics table for a strategy."""
    s = bt.backtest_summary
    if not s:
        return "No summary metrics available."
    d = s.to_dict()
    lines = []
    for k, v in sorted(d.items()):
        if v is not None:
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)


def _per_window_table(bt):
    """Markdown table of per-window metrics."""
    runs = bt.get_all_backtest_runs()
    if not runs:
        return "No runs available."
    header = (
        "| Window | CAGR | Sharpe | Sortino"
        " | Max DD | Win Rate | Trades |"
    )
    sep = "|--------|------|--------|---------|--------|----------|--------|"
    rows = [header, sep]
    for run in runs:
        m = run.backtest_metrics
        name = run.backtest_date_range_name or "—"
        if m:
            rows.append(
                f"| {name} "
                f"| {_fmt_pct(m.cagr)} "
                f"| {_fmt_dec(m.sharpe_ratio)} "
                f"| {_fmt_dec(m.sortino_ratio)} "
                f"| {_fmt_pct(abs(m.max_drawdown) if m.max_drawdown else None)} "  # noqa: E501
                f"| {_fmt_pct(m.win_rate)} "
                f"| {m.number_of_trades or 0} |"
            )
        else:
            rows.append(f"| {name} | — | — | — | — | — | — |")
    return "\n".join(rows)


def _trading_activity_table(backtests, tags=None):
    """Markdown table of trading-activity metrics."""
    has_tags = tags and any(tags.values())
    tag_hdr = "| Batch " if has_tags else ""
    tag_sep = "|-------" if has_tags else ""
    header = (
        "| Strategy " + tag_hdr
        + "| Profit Factor | Win Rate"
        " | Trades/yr | Trades/mo "
        "| Trades/wk | # Trades"
        " | Avg Return | Median Return "
        "| Avg Duration | Win Streak"
        " | Loss Streak | % Win Months |"
    )
    sep = (
        "|----------" + tag_sep
        + "|---------------|----------"
        "|-----------|----------"
        "|-----------|----------"
        "|------------|---------------"
        "|--------------|------------"
        "|-------------|--------------|"
    )
    rows = [header, sep]
    for bt in backtests:
        s = bt.backtest_summary
        tag_col = ""
        if has_tags:
            t = (tags or {}).get(bt.algorithm_id, '')
            tag_col = f"| {t} "
        if not s:
            rows.append(
                f"| {bt.algorithm_id} "
                f"{tag_col}|" + " — |" * 12
            )
            continue
        tpy = getattr(s, "trades_per_year", None)
        tpw = (tpy / 52) if tpy is not None else None
        rows.append(
            f"| {bt.algorithm_id} "
            f"{tag_col}"
            f"| {_fmt_dec(getattr(s, 'profit_factor', None))} "
            f"| {_fmt_pct(getattr(s, 'win_rate', None))} "
            f"| {_fmt_dec(tpy)} "
            f"| {_fmt_dec(getattr(s, 'trades_per_month', None))} "
            f"| {_fmt_dec(tpw)} "
            f"| {getattr(s, 'number_of_trades', None) or 0} "
            f"| {_fmt_pct(getattr(s, 'average_trade_return_percentage', None))} "  # noqa: E501
            f"| {_fmt_pct(getattr(s, 'median_trade_return_percentage', None))} "  # noqa: E501
            f"| {_fmt_dec(getattr(s, 'average_trade_duration', None))} "
            f"| {getattr(s, 'max_consecutive_wins', None) or 0} "
            f"| {getattr(s, 'max_consecutive_losses', None) or 0} "
            f"| {_fmt_pct(getattr(s, 'percentage_winning_months', None))} |"
        )
    return "\n".join(rows)


def _ranking_table(
    backtests, metric="sharpe_ratio", ascending=False, tags=None
):
    """Rank strategies by a metric across all windows (summary)."""
    has_tags = tags and any(tags.values())
    entries = []
    for bt in backtests:
        s = bt.backtest_summary
        val = getattr(s, metric, None) if s else None
        entries.append({
            "algorithm_id": bt.algorithm_id,
            "value": val,
        })
    entries.sort(
        key=lambda x: (x["value"] is None, x["value"] or 0),
        reverse=not ascending,
    )
    tag_hdr = "| Batch " if has_tags else ""
    tag_sep = "|-------" if has_tags else ""
    header = f"| Rank | Strategy {tag_hdr}| {metric} |"
    sep = (
        "|------|----------"
        + tag_sep
        + "|" + "-" * (len(metric) + 2) + "|"
    )
    rows = [header, sep]
    for i, e in enumerate(entries):
        v = _fmt_dec(e["value"]) if e["value"] is not None else "—"
        tag_col = ""
        if has_tags:
            t = (tags or {}).get(e["algorithm_id"], '')
            tag_col = f"| {t} "
        rows.append(
            f"| {i + 1} | {e['algorithm_id']} {tag_col}| {v} |"
        )
    return "\n".join(rows)


def _top_trades(bt, n=10):
    """Get top trades by magnitude for a strategy."""
    all_trades = []
    for run in bt.get_all_backtest_runs():
        for t in (run.trades or []):
            cost = getattr(t, 'cost', 0) or 0
            ng = getattr(t, 'net_gain', 0) or 0
            pct = (ng / cost * 100) if cost else 0
            all_trades.append({
                "symbol": getattr(t, 'target_symbol', '—'),
                "opened": str(t.opened_at)[:10] if t.opened_at else "—",
                "closed": str(t.closed_at)[:10] if t.closed_at else "—",
                "return_pct": round(pct, 2),
                "net_gain": round(ng, 2),
                "window": run.backtest_date_range_name or "—",
            })
    all_trades.sort(key=lambda x: abs(x["return_pct"]), reverse=True)
    return all_trades[:n]


def _all_orders(bt, window=None, limit=50, order_reason=None):
    """Get all orders for a strategy across windows."""
    orders = []
    for run in bt.get_all_backtest_runs():
        if window and run.backtest_date_range_name != window:
            continue
        wname = run.backtest_date_range_name or "—"
        for o in (run.orders or []):
            meta = getattr(o, 'metadata', None) or {}
            reason = meta.get('order_reason', '—')
            if order_reason and reason != order_reason:
                continue
            price = getattr(o, 'price', 0) or 0
            amount = getattr(o, 'amount', 0) or 0
            filled = getattr(o, 'filled', 0) or 0
            fee = getattr(o, 'order_fee', 0) or 0
            fee_rate = getattr(o, 'order_fee_rate', 0) or 0
            slippage = getattr(o, 'slippage', 0) or 0
            created = getattr(o, 'created_at', None)
            orders.append({
                "symbol": getattr(o, 'target_symbol', '—'),
                "side": str(getattr(o, 'order_side', '—')),
                "type": str(getattr(o, 'order_type', '—')),
                "status": str(getattr(o, 'status', '—')),
                "price": round(float(price), 4),
                "amount": round(float(amount), 6),
                "filled": round(float(filled), 6),
                "cost": round(float(amount) * float(price), 2),
                "fee": round(float(fee), 4),
                "fee_rate": round(float(fee_rate), 4),
                "slippage": round(float(slippage), 4),
                "order_reason": reason,
                "metadata": meta,
                "created": _fmt_date(created),
                "window": wname,
            })
    orders.sort(
        key=lambda x: x["created"] if x["created"] != "—" else "",
        reverse=True,
    )
    return orders[:limit]


def _all_positions(bt, window=None):
    """Get all positions for a strategy across windows."""
    positions = []
    for run in bt.get_all_backtest_runs():
        if window and run.backtest_date_range_name != window:
            continue
        wname = run.backtest_date_range_name or "—"
        for p in (run.positions or []):
            amount = getattr(p, 'amount', 0) or 0
            cost = getattr(p, 'cost', 0) or 0
            positions.append({
                "symbol": getattr(p, 'symbol', '—'),
                "amount": round(float(amount), 6),
                "cost": round(float(cost), 2),
                "window": wname,
            })
    return positions


def _full_analysis(backtests, tags=None):
    """Generate a complete analysis markdown document."""
    has_tags = tags and any(tags.values())
    md = "# Backtest Analysis Data\n\n"
    md += f"**Strategies:** {len(backtests)}\n"
    windows = set()
    for bt in backtests:
        for r in bt.get_all_backtest_runs():
            windows.add(r.backtest_date_range_name or "—")
    md += f"**Windows:** {len(windows)}\n\n"

    # Ranking table
    md += "## Strategy Ranking (by Sharpe Ratio)\n\n"
    md += _ranking_table(
        backtests, "sharpe_ratio", tags=tags
    ) + "\n\n"

    # Per strategy
    for bt in backtests:
        md += f"## {bt.algorithm_id}\n\n"
        if has_tags:
            t = (tags or {}).get(bt.algorithm_id, '')
            if t:
                md += f"**Batch:** {t}\n\n"
        if bt.parameters:
            params = ", ".join(f"{k}={v}" for k, v in bt.parameters.items())
            md += f"**Parameters:** {params}\n\n"
        md += "### Summary Metrics\n\n"
        md += _metrics_table(bt) + "\n\n"
        md += "### Per-Window Breakdown\n\n"
        md += _per_window_table(bt) + "\n\n"
        trades = _top_trades(bt, 5)
        if trades:
            md += "### Top Trades\n\n"
            md += (
                "| Symbol | Opened | Closed"
                " | Return % | Net Gain | Window |\n"
            )
            md += (
                "|--------|--------|--------"
                "|----------|----------|--------|\n"
            )
            for t in trades:
                md += (
                    f"| {t['symbol']} | {t['opened']} | {t['closed']} "
                    f"| {t['return_pct']}% | {t['net_gain']} "
                    f"| {t['window']} |\n"
                )
            md += "\n"
    return md


def _fmt_date(d):
    """Format a datetime to YYYY-MM-DD."""
    if d is None:
        return "—"
    if hasattr(d, 'strftime'):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _equity_curve_table(bt, window=None, sample=50):
    """Equity curve as a markdown table, sampled to limit size."""
    runs = bt.get_all_backtest_runs()
    if window:
        runs = [r for r in runs if r.backtest_date_range_name == window]
    if not runs:
        return "No runs found."
    md = ""
    for run in runs:
        m = run.backtest_metrics
        if not m or not m.equity_curve:
            continue
        ec = m.equity_curve
        name = run.backtest_date_range_name or "—"
        md += f"### {name}\n\n"
        md += "| Date | Value | Growth % |\n"
        md += "|------|-------|----------|\n"
        initial = ec[0][0] if ec else 1
        if initial == 0:
            initial = 1
        step = max(1, len(ec) // sample)
        for i in range(0, len(ec), step):
            v, d = ec[i]
            growth = (v / initial - 1) * 100
            md += f"| {_fmt_date(d)} | {v:.2f} | {growth:.2f}% |\n"
        # Always include last point
        if (len(ec) - 1) % step != 0:
            v, d = ec[-1]
            growth = (v / initial - 1) * 100
            md += f"| {_fmt_date(d)} | {v:.2f} | {growth:.2f}% |\n"
        md += "\n"
    return md or "No equity curve data."


def _equity_curves_stacked(backtests, sids, window=None, sample=50):
    """Multi-strategy equity curves as a stacked markdown table."""
    # Collect per-window data for each strategy
    windows = {}
    for bt, sid in zip(backtests, sids):
        runs = bt.get_all_backtest_runs()
        if window:
            runs = [r for r in runs if r.backtest_date_range_name == window]
        for run in runs:
            m = run.backtest_metrics
            if not m or not m.equity_curve:
                continue
            wname = run.backtest_date_range_name or "—"
            ec = m.equity_curve
            initial = ec[0][0] if ec else 1
            if initial == 0:
                initial = 1
            step = max(1, len(ec) // sample)
            points = []
            for i in range(0, len(ec), step):
                v, d = ec[i]
                points.append((_fmt_date(d), (v / initial - 1) * 100))
            if (len(ec) - 1) % step != 0:
                v, d = ec[-1]
                points.append((_fmt_date(d), (v / initial - 1) * 100))
            windows.setdefault(wname, {})[sid] = points

    if not windows:
        return "No equity curve data."

    md = f"# Equity Curves — {', '.join(sids)}\n\n"
    for wname, strats in sorted(windows.items()):
        md += f"### {wname}\n\n"
        md += "| Date |"
        for sid in sids:
            if sid in strats:
                md += f" {sid} |"
        md += "\n|------|"
        for sid in sids:
            if sid in strats:
                md += "--------|"
        md += "\n"
        # Merge dates
        all_dates = []
        for sid in sids:
            if sid in strats:
                for d, _ in strats[sid]:
                    if d not in all_dates:
                        all_dates.append(d)
        all_dates.sort()
        date_map = {}
        for sid in sids:
            if sid in strats:
                date_map[sid] = {d: v for d, v in strats[sid]}
        for d in all_dates:
            md += f"| {d} |"
            for sid in sids:
                if sid in strats:
                    v = date_map[sid].get(d)
                    md += f" {v:.2f}% |" if v is not None else " — |"
            md += "\n"
        md += "\n"
    return md


def _drawdown_series_stacked(backtests, sids, window=None, sample=50):
    """Multi-strategy drawdown series as a stacked markdown table."""
    windows = {}
    for bt, sid in zip(backtests, sids):
        runs = bt.get_all_backtest_runs()
        if window:
            runs = [r for r in runs if r.backtest_date_range_name == window]
        for run in runs:
            m = run.backtest_metrics
            if not m or not m.drawdown_series:
                continue
            wname = run.backtest_date_range_name or "—"
            dd = m.drawdown_series
            step = max(1, len(dd) // sample)
            points = []
            for i in range(0, len(dd), step):
                v, d = dd[i]
                pct = v * 100 if abs(v) < 1 else v
                points.append((_fmt_date(d), pct))
            if (len(dd) - 1) % step != 0:
                v, d = dd[-1]
                pct = v * 100 if abs(v) < 1 else v
                points.append((_fmt_date(d), pct))
            windows.setdefault(wname, {})[sid] = points

    if not windows:
        return "No drawdown data."

    md = f"# Drawdown Series — {', '.join(sids)}\n\n"
    for wname, strats in sorted(windows.items()):
        md += f"### {wname}\n\n"
        md += "| Date |"
        for sid in sids:
            if sid in strats:
                md += f" {sid} |"
        md += "\n|------|"
        for sid in sids:
            if sid in strats:
                md += "--------|"
        md += "\n"
        all_dates = []
        for sid in sids:
            if sid in strats:
                for d, _ in strats[sid]:
                    if d not in all_dates:
                        all_dates.append(d)
        all_dates.sort()
        date_map = {sid: {d: v for d, v in strats[sid]}
                    for sid in sids if sid in strats}
        for d in all_dates:
            md += f"| {d} |"
            for sid in sids:
                if sid in strats:
                    v = date_map[sid].get(d)
                    md += f" {v:.2f}% |" if v is not None else " — |"
            md += "\n"
        md += "\n"
    return md


def _rolling_sharpe_stacked(backtests, sids, window=None, sample=50):
    """Multi-strategy rolling Sharpe as a stacked markdown table."""
    windows = {}
    for bt, sid in zip(backtests, sids):
        runs = bt.get_all_backtest_runs()
        if window:
            runs = [r for r in runs if r.backtest_date_range_name == window]
        for run in runs:
            m = run.backtest_metrics
            if not m or not m.rolling_sharpe_ratio:
                continue
            wname = run.backtest_date_range_name or "—"
            rs = m.rolling_sharpe_ratio
            step = max(1, len(rs) // sample)
            points = []
            for i in range(0, len(rs), step):
                v, d = rs[i]
                points.append((_fmt_date(d), v))
            if (len(rs) - 1) % step != 0:
                v, d = rs[-1]
                points.append((_fmt_date(d), v))
            windows.setdefault(wname, {})[sid] = points

    if not windows:
        return "No rolling Sharpe data."

    md = f"# Rolling Sharpe — {', '.join(sids)}\n\n"
    for wname, strats in sorted(windows.items()):
        md += f"### {wname}\n\n"
        md += "| Date |"
        for sid in sids:
            if sid in strats:
                md += f" {sid} |"
        md += "\n|------|"
        for sid in sids:
            if sid in strats:
                md += "--------|"
        md += "\n"
        all_dates = []
        for sid in sids:
            if sid in strats:
                for d, _ in strats[sid]:
                    if d not in all_dates:
                        all_dates.append(d)
        all_dates.sort()
        date_map = {sid: {d: v for d, v in strats[sid]}
                    for sid in sids if sid in strats}
        for d in all_dates:
            md += f"| {d} |"
            for sid in sids:
                if sid in strats:
                    v = date_map[sid].get(d)
                    md += f" {v:.3f} |" if v is not None else " — |"
            md += "\n"
        md += "\n"
    return md


def _yearly_returns_stacked(backtests, sids, window=None):
    """Multi-strategy yearly returns as a stacked markdown table."""
    windows = {}
    for bt, sid in zip(backtests, sids):
        runs = bt.get_all_backtest_runs()
        if window:
            runs = [r for r in runs if r.backtest_date_range_name == window]
        for run in runs:
            m = run.backtest_metrics
            if not m or not m.yearly_returns:
                continue
            wname = run.backtest_date_range_name or "—"
            points = []
            for v, d in m.yearly_returns:
                yr = d.year if hasattr(d, 'year') else str(d)
                pct = v * 100 if abs(v) < 1 else v
                points.append((str(yr), pct))
            windows.setdefault(wname, {})[sid] = points

    if not windows:
        return "No yearly returns data."

    md = f"# Yearly Returns — {', '.join(sids)}\n\n"
    for wname, strats in sorted(windows.items()):
        md += f"### {wname}\n\n"
        md += "| Year |"
        for sid in sids:
            if sid in strats:
                md += f" {sid} |"
        md += "\n|------|"
        for sid in sids:
            if sid in strats:
                md += "--------|"
        md += "\n"
        all_years = []
        for sid in sids:
            if sid in strats:
                for yr, _ in strats[sid]:
                    if yr not in all_years:
                        all_years.append(yr)
        all_years.sort()
        year_map = {sid: {yr: v for yr, v in strats[sid]}
                    for sid in sids if sid in strats}
        for yr in all_years:
            md += f"| {yr} |"
            for sid in sids:
                if sid in strats:
                    v = year_map[sid].get(yr)
                    md += f" {v:.2f}% |" if v is not None else " — |"
            md += "\n"
        md += "\n"
    return md


def _monthly_returns_stacked(backtests, sids, window=None):
    """Multi-strategy monthly returns — sequential tables per strategy."""
    md = f"# Monthly Returns — {', '.join(sids)}\n\n"
    found = False
    for bt, sid in zip(backtests, sids):
        sub = _monthly_returns_table(bt, window=window)
        if sub and sub != "No monthly returns data.":
            md += f"## {sid}\n\n{sub}\n"
            found = True
    return md if found else "No monthly returns data."


def _portfolio_snapshots_stacked(backtests, sids, window=None):
    """Multi-strategy portfolio snapshots as a stacked table."""
    md = f"# Portfolio Snapshots — {', '.join(sids)}\n\n"
    md += "| Strategy | Window | Initial | Final | Net Gain | Growth % |\n"
    md += "|----------|--------|---------|-------|----------|----------|\n"
    found = False
    for bt, sid in zip(backtests, sids):
        runs = bt.get_all_backtest_runs()
        if window:
            runs = [r for r in runs if r.backtest_date_range_name == window]
        for run in runs:
            wname = run.backtest_date_range_name or "—"
            if run.portfolio_snapshots:
                first = run.portfolio_snapshots[0]
                last = run.portfolio_snapshots[-1]
                iv = getattr(first, 'trading_symbol_balance', 0) or 0
                fv = getattr(last, 'trading_symbol_balance', 0) or 0
                ng = fv - iv
                gr = (fv / iv - 1) * 100 if iv else 0
                md += (
                    f"| {sid} | {wname} | {iv:.2f} | {fv:.2f} "
                    f"| {ng:.2f} | {gr:.2f}% |\n"
                )
                found = True
    return md if found else "No portfolio snapshot data."


def _drawdown_series_table(bt, window=None, sample=50):
    """Drawdown series as a markdown table."""
    runs = bt.get_all_backtest_runs()
    if window:
        runs = [r for r in runs if r.backtest_date_range_name == window]
    md = ""
    for run in runs:
        m = run.backtest_metrics
        if not m or not m.drawdown_series:
            continue
        dd = m.drawdown_series
        name = run.backtest_date_range_name or "—"
        md += f"### {name}\n\n"
        md += "| Date | Drawdown % |\n"
        md += "|------|------------|\n"
        step = max(1, len(dd) // sample)
        for i in range(0, len(dd), step):
            v, d = dd[i]
            pct = v * 100 if abs(v) < 1 else v
            md += f"| {_fmt_date(d)} | {pct:.2f}% |\n"
        if (len(dd) - 1) % step != 0:
            v, d = dd[-1]
            pct = v * 100 if abs(v) < 1 else v
            md += f"| {_fmt_date(d)} | {pct:.2f}% |\n"
        md += "\n"
    return md or "No drawdown data."


def _monthly_returns_table(bt, window=None):
    """Monthly returns heatmap data as markdown."""
    runs = bt.get_all_backtest_runs()
    if window:
        runs = [r for r in runs if r.backtest_date_range_name == window]
    md = ""
    for run in runs:
        m = run.backtest_metrics
        if not m or not m.monthly_returns:
            continue
        name = run.backtest_date_range_name or "—"
        md += f"### {name}\n\n"
        # Build heatmap: {year: {month: value}}
        heatmap = {}
        for v, d in m.monthly_returns:
            y = d.year if hasattr(d, 'year') else int(str(d)[:4])
            mo = d.month if hasattr(d, 'month') else int(str(d)[5:7])
            pct = v * 100 if abs(v) < 1 else v
            heatmap.setdefault(y, {})[mo] = round(pct, 2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        md += "| Year | " + " | ".join(months) + " | Total |\n"
        md += "|------|" + "|".join(["------"] * 12) + "|-------|\n"
        for y in sorted(heatmap.keys()):
            row = [f"| {y} "]
            total = 0
            for mo in range(1, 13):
                val = heatmap[y].get(mo)
                if val is not None:
                    row.append(f" {val:.1f}% ")
                    total += val
                else:
                    row.append(" — ")
            row.append(f" {total:.1f}% |")
            md += "|".join(row) + "\n"
        md += "\n"
    return md or "No monthly returns data."


def _yearly_returns_table(bt, window=None):
    """Yearly returns as markdown."""
    runs = bt.get_all_backtest_runs()
    if window:
        runs = [r for r in runs if r.backtest_date_range_name == window]
    md = ""
    for run in runs:
        m = run.backtest_metrics
        if not m or not m.yearly_returns:
            continue
        name = run.backtest_date_range_name or "—"
        md += f"### {name}\n\n"
        md += "| Year | Return % |\n"
        md += "|------|----------|\n"
        for v, d in m.yearly_returns:
            yr = d.year if hasattr(d, 'year') else str(d)
            pct = v * 100 if abs(v) < 1 else v
            md += f"| {yr} | {pct:.2f}% |\n"
        md += "\n"
    return md or "No yearly returns data."


def _rolling_sharpe_table(bt, window=None, sample=50):
    """Rolling Sharpe ratio as markdown."""
    runs = bt.get_all_backtest_runs()
    if window:
        runs = [r for r in runs if r.backtest_date_range_name == window]
    md = ""
    for run in runs:
        m = run.backtest_metrics
        if not m or not m.rolling_sharpe_ratio:
            continue
        rs = m.rolling_sharpe_ratio
        name = run.backtest_date_range_name or "—"
        md += f"### {name}\n\n"
        md += "| Date | Sharpe |\n"
        md += "|------|--------|\n"
        step = max(1, len(rs) // sample)
        for i in range(0, len(rs), step):
            v, d = rs[i]
            md += f"| {_fmt_date(d)} | {v:.3f} |\n"
        if (len(rs) - 1) % step != 0:
            v, d = rs[-1]
            md += f"| {_fmt_date(d)} | {v:.3f} |\n"
        md += "\n"
    return md or "No rolling Sharpe data."


def _symbol_breakdown(bt):
    """Per-symbol trade breakdown."""
    sym_stats = {}
    for run in bt.get_all_backtest_runs():
        for t in (run.trades or []):
            sym = getattr(t, 'target_symbol', '') or '—'
            ng = getattr(t, 'net_gain', 0) or 0
            entry = sym_stats.setdefault(sym, {
                'count': 0, 'gain': 0.0, 'wins': 0, 'losses': 0
            })
            entry['count'] += 1
            entry['gain'] += ng
            if ng > 0:
                entry['wins'] += 1
            elif ng < 0:
                entry['losses'] += 1
    if not sym_stats:
        return "No trade data available."
    md = "| Symbol | Trades | Net Gain | Wins | Losses | Win Rate |\n"
    md += "|--------|--------|----------|------|--------|----------|\n"
    for sym, s in sorted(sym_stats.items(),
                         key=lambda x: x[1]['gain'], reverse=True):
        wr = (s['wins'] / s['count'] * 100) if s['count'] else 0
        md += (
            f"| {sym} | {s['count']} | {s['gain']:.2f} "
            f"| {s['wins']} | {s['losses']} | {wr:.1f}% |\n"
        )
    return md


def _return_scenarios(bt):
    """Return scenario analysis (best/worst month/year, etc.)."""
    s = bt.backtest_summary
    md = ""
    if not s:
        return "No summary data."

    # Best/worst from per-run metrics
    all_months, all_years = [], []
    for run in bt.get_all_backtest_runs():
        m = run.backtest_metrics
        if not m:
            continue
        if m.best_month and m.best_month[0] is not None:
            v = m.best_month[0]
            pct = v * 100 if abs(v) < 1 else v
            all_months.append(("Best Month", pct, m.best_month[1],
                               run.backtest_date_range_name))
        if m.worst_month and m.worst_month[0] is not None:
            v = m.worst_month[0]
            pct = v * 100 if abs(v) < 1 else v
            all_months.append(("Worst Month", pct, m.worst_month[1],
                               run.backtest_date_range_name))
        if m.best_year and m.best_year[0] is not None:
            v = m.best_year[0]
            pct = v * 100 if abs(v) < 1 else v
            all_years.append(("Best Year", pct, m.best_year[1],
                              run.backtest_date_range_name))
        if m.worst_year and m.worst_year[0] is not None:
            v = m.worst_year[0]
            pct = v * 100 if abs(v) < 1 else v
            all_years.append(("Worst Year", pct, m.worst_year[1],
                              run.backtest_date_range_name))

    if all_months or all_years:
        md += "| Scenario | Return % | Date | Window |\n"
        md += "|----------|----------|------|--------|\n"
        for label, pct, d, win in all_months + all_years:
            md += f"| {label} | {pct:.2f}% | {_fmt_date(d)} | {win or '—'} |\n"
        md += "\n"

    # Key risk stats
    md += "**Risk Summary:**\n"
    md += f"- Max Drawdown: {_fmt_pct(s.max_drawdown)}\n"
    md += f"- VaR 95%: {_fmt_pct(getattr(s, 'var_95', None))}\n"
    md += f"- CVaR 95%: {_fmt_pct(getattr(s, 'cvar_95', None))}\n"
    win_mo = _fmt_pct(
        getattr(s, 'percentage_winning_months', None)
    )
    win_yr = _fmt_pct(
        getattr(s, 'percentage_winning_years', None)
    )
    md += f"- % Winning Months: {win_mo}\n"
    md += f"- % Winning Years: {win_yr}\n"
    cons_w = getattr(s, 'max_consecutive_wins', '—')
    cons_l = getattr(s, 'max_consecutive_losses', '—')
    md += f"- Max Consecutive Wins: {cons_w}\n"
    md += f"- Max Consecutive Losses: {cons_l}\n"

    return md


def _correlation_matrix(backtests, window=None):
    """Cross-strategy return correlation matrix."""
    # Collect monthly return series per strategy
    series = {}
    for bt in backtests:
        runs = bt.get_all_backtest_runs()
        if window:
            runs = [r for r in runs if r.backtest_date_range_name == window]
        returns = {}
        for run in runs:
            m = run.backtest_metrics
            if m and m.monthly_returns:
                for v, d in m.monthly_returns:
                    key = f"{d.year}-{d.month:02d}" if hasattr(d, 'year') \
                        else str(d)[:7]
                    returns[key] = v
        if returns:
            series[bt.algorithm_id] = returns

    if len(series) < 2:
        return "Need at least 2 strategies with return data for correlation."

    ids = list(series.keys())
    # Find common months
    common = set(series[ids[0]].keys())
    for sid in ids[1:]:
        common &= set(series[sid].keys())
    common = sorted(common)

    if len(common) < 3:
        return "Insufficient overlapping return data for correlation."

    # Compute Pearson correlation
    def _mean(vals):
        return sum(vals) / len(vals) if vals else 0

    def _corr(x, y):
        mx, my = _mean(x), _mean(y)
        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        dx = sum((a - mx) ** 2 for a in x) ** 0.5
        dy = sum((b - my) ** 2 for b in y) ** 0.5
        return num / (dx * dy) if dx * dy > 0 else 0

    md = f"Correlation matrix based on {len(common)} common months.\n\n"
    md += "| | " + " | ".join(ids) + " |\n"
    md += "|" + "|".join(["---"] * (len(ids) + 1)) + "|\n"
    for i, a in enumerate(ids):
        row = [f"| **{a}** "]
        x = [series[a].get(m, 0) for m in common]
        for j, b in enumerate(ids):
            y = [series[b].get(m, 0) for m in common]
            c = _corr(x, y)
            row.append(f" {c:.2f} ")
        md += "|".join(row) + "|\n"
    return md


def _window_coverage(backtests):
    """Window coverage summary — which strategies ran in which windows."""
    windows = {}
    for bt in backtests:
        for run in bt.get_all_backtest_runs():
            name = run.backtest_date_range_name or "—"
            start = _fmt_date(run.backtest_start_date)
            end = _fmt_date(run.backtest_end_date)
            days = 0
            if run.backtest_start_date and run.backtest_end_date:
                days = (run.backtest_end_date - run.backtest_start_date).days
            entry = windows.setdefault(name, {
                'start': start, 'end': end, 'days': days,
                'strategies': []
            })
            entry['strategies'].append(bt.algorithm_id)
    md = "| Window | Start | End | Days | Strategies |\n"
    md += "|--------|-------|-----|------|------------|\n"
    for name, w in sorted(windows.items()):
        md += (
            f"| {name} | {w['start']} | {w['end']} | {w['days']} "
            f"| {len(w['strategies'])} |\n"
        )
    return md


def _portfolio_snapshots(bt, window=None):
    """Portfolio snapshot summaries per window."""
    runs = bt.get_all_backtest_runs()
    if window:
        runs = [r for r in runs if r.backtest_date_range_name == window]
    md = "| Window | Initial | Final | Net Gain | Growth % |\n"
    md += "|--------|---------|-------|----------|----------|\n"
    for run in runs:
        name = run.backtest_date_range_name or "—"
        if run.portfolio_snapshots:
            first = run.portfolio_snapshots[0]
            last = run.portfolio_snapshots[-1]
            fv = getattr(first, 'total_value', 0) or 0
            lv = getattr(last, 'total_value', 0) or 0
            ng = lv - fv
            growth = ((lv / fv - 1) * 100) if fv else 0
            md += (
                f"| {name} | {fv:.2f} | {lv:.2f} "
                f"| {ng:.2f} | {growth:.2f}% |\n"
            )
        else:
            md += f"| {name} | — | — | — | — |\n"
    return md


# ── Notes Storage ──


def _notes_path(directory):
    """Path to the notes JSON file in the backtest directory."""
    return os.path.join(directory, ".analysis_notes.json")


def _load_notes(directory):
    """Load notes from disk. Returns dict with notes list + counters."""
    path = _notes_path(directory)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        return data
    return {"notes": [], "noteIdCounter": 0, "snapshotIdCounter": 0}


def _save_notes(directory, data):
    """Save notes to disk."""
    path = _notes_path(directory)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _filter_strategies(backtests, conditions):
    """Filter strategies by metric conditions.

    conditions: list of dicts with {metric, operator, value}
    operator: >, <, >=, <=, ==
    """
    ops = {
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: abs(a - b) < 1e-9,
    }
    result = []
    for bt in backtests:
        s = bt.backtest_summary
        if not s:
            continue
        passes = True
        for cond in conditions:
            metric = cond.get("metric", "")
            op = cond.get("operator", ">")
            val = cond.get("value", 0)
            actual = getattr(s, metric, None)
            if actual is None:
                passes = False
                break
            fn = ops.get(op)
            if fn is None:
                passes = False
                break
            if not fn(actual, val):
                passes = False
                break
        if passes:
            result.append(bt)
    return result


# ── MCP Protocol Implementation ──


class BacktestMCPServer:
    """Minimal MCP server using stdio transport (JSON-RPC 2.0)."""

    def __init__(self, directory: Union[str, List[str]]):
        self.directory = directory
        self._backtests = None
        self._bt_map = {}
        self._bt_tags = {}

    def _ensure_loaded(self):
        if self._backtests is None:
            _log(f"Loading backtests from: {self.directory}")
            try:
                backtests, tags = _load_backtests(self.directory)
            except Exception as exc:
                _log(f"ERROR loading backtests: {exc}")
                raise
            self._backtests = backtests
            self._bt_map = {
                bt.algorithm_id: bt
                for bt in self._backtests
            }
            for i, bt in enumerate(self._backtests):
                # Prefer persisted bt.tag, fall back to dir tag
                tag = getattr(bt, 'tag', None) or ''
                if not tag:
                    tag = tags[i] if i < len(tags) else ''
                self._bt_tags[bt.algorithm_id] = tag
            _log(
                f"Loaded {len(self._backtests)} backtests: "
                f"{list(self._bt_map.keys())}"
            )

    def _get_tools(self):
        return [
            {
                "name": "list_strategies",
                "description": (
                    "List all backtest strategies with their key summary "
                    "metrics (CAGR, Sharpe, Max DD, Win Rate, etc.). "
                    "Use this first to get an overview. "
                    "Optionally filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_strategy_details",
                "description": (
                    "Get detailed metrics, parameters, per-window breakdown, "
                    "and top trades for a specific strategy."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "The algorithm_id of the strategy",
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "rank_strategies",
                "description": (
                    "Rank strategies by a specific metric. "
                    "Useful for finding the best/worst performers. "
                    "Optionally filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "metric": {
                            "type": "string",
                            "description": (
                                "Metric to rank by, e.g.: sharpe_ratio, "
                                "cagr, sortino_ratio, calmar_ratio, "
                                "max_drawdown, win_rate, profit_factor, "
                                "annual_volatility, trades_per_year, "
                                "consistency_score, stability_score"
                            ),
                        },
                        "ascending": {
                            "type": "boolean",
                            "description": (
                                "Sort ascending (True) or descending "
                                "(False, default)"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": (
                                "Max number of strategies to return "
                                "(default: all). Use e.g. 20 to get "
                                "top 20."
                            ),
                        },
                    },
                    "required": ["metric"],
                },
            },
            {
                "name": "compare_strategies",
                "description": (
                    "Compare two strategies side-by-side across all metrics "
                    "and windows."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_a": {
                            "type": "string",
                            "description": "First strategy algorithm_id",
                        },
                        "strategy_b": {
                            "type": "string",
                            "description": "Second strategy algorithm_id",
                        },
                    },
                    "required": ["strategy_a", "strategy_b"],
                },
            },
            {
                "name": "get_full_analysis",
                "description": (
                    "Get a complete analysis document with all strategies, "
                    "metrics, rankings, per-window breakdowns and top trades. "
                    "Use this for comprehensive analysis. "
                    "Optionally filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_trading_activity",
                "description": (
                    "Get a Trading Activity table with "
                    "12 trading metrics: Profit Factor, Win Rate, "
                    "Trades/yr, Trades/mo, Trades/wk, # Trades, "
                    "Avg Return, Median Return, Avg Duration, Win Streak, "
                    "Loss Streak, % Win Months. Matches the dashboard "
                    "Trading Activity view exactly. "
                    "Optionally filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_trades",
                "description": (
                    "Get trades for a strategy, optionally filtered by "
                    "window. Returns top trades by return magnitude."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "The algorithm_id of the strategy",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max trades to return (default 20)",
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "get_orders",
                "description": (
                    "Get all orders for a strategy — symbol, side, type, "
                    "status, price, amount, filled, cost, fee, fee_rate, "
                    "slippage, order_reason, metadata, and creation date. "
                    "Optionally filter by window or order_reason "
                    "(buy_signal, sell_signal, scale_in, scale_out, "
                    "stop_loss, take_profit). "
                    "Sorted by date (newest first)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "The algorithm_id of the strategy"
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: specific window name "
                                "to filter by"
                            ),
                        },
                        "order_reason": {
                            "type": "string",
                            "description": (
                                "Optional: filter by order_reason "
                                "metadata. Values: buy_signal, "
                                "sell_signal, scale_in, scale_out, "
                                "stop_loss, take_profit"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": (
                                "Max orders to return (default 50)"
                            ),
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "get_positions",
                "description": (
                    "Get all positions for a strategy — symbol, amount, "
                    "and cost. Optionally filter by window."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "The algorithm_id of the strategy"
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: specific window name "
                                "to filter by"
                            ),
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "get_equity_curve",
                "description": (
                    "Get equity curve time-series data for one or more "
                    "strategies (portfolio value over time). Use "
                    "strategy_id for a single strategy, or strategy_ids "
                    "for a stacked multi-strategy comparison. Sampled to "
                    "~50 points. Shows date, value, and cumulative "
                    "growth %. Use window to filter by a specific "
                    "backtest window. Use tag to filter by batch."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids, not both."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids for a "
                                "stacked comparison. Use this OR "
                                "strategy_id, not both."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: specific window name to filter by"
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_drawdown_series",
                "description": (
                    "Get drawdown time-series for one or more strategies "
                    "(how far below peak at each point). Use strategy_id "
                    "for one, or strategy_ids for a stacked comparison. "
                    "Sampled to ~50 pts. Use tag to filter by batch."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids for a "
                                "stacked comparison."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": "Optional: specific window name",
                        },
                    },
                },
            },
            {
                "name": "get_monthly_returns",
                "description": (
                    "Get monthly returns heatmap for one or more "
                    "strategies. Use strategy_id for one, or "
                    "strategy_ids for sequential tables per strategy. "
                    "Great for seasonality analysis. "
                    "Use tag to filter by batch."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids for "
                                "comparison."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": "Optional: specific window name",
                        },
                    },
                },
            },
            {
                "name": "get_yearly_returns",
                "description": (
                    "Get yearly returns for one or more strategies. "
                    "Use strategy_id for one, or strategy_ids for a "
                    "stacked comparison table. Use tag to filter by batch."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids for a "
                                "stacked comparison."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": "Optional: specific window name",
                        },
                    },
                },
            },
            {
                "name": "get_rolling_sharpe",
                "description": (
                    "Get rolling Sharpe ratio time-series for one or more "
                    "strategies. Use strategy_id for one, or strategy_ids "
                    "for a stacked comparison. Shows how risk-adjusted "
                    "performance evolves over time. "
                    "Use tag to filter by batch."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids for a "
                                "stacked comparison."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": "Optional: specific window name",
                        },
                    },
                },
            },
            {
                "name": "get_symbol_breakdown",
                "description": (
                    "Get per-symbol trade breakdown for a "
                    "strategy — how many trades per symbol, "
                    "net gain, win rate. Useful for "
                    "understanding concentration."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "The algorithm_id of the strategy",
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "get_return_scenarios",
                "description": (
                    "Get return scenario analysis for a strategy — "
                    "best/worst months and years, key risk statistics."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "The algorithm_id of the strategy",
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "get_correlation_matrix",
                "description": (
                    "Get cross-strategy return correlation matrix. "
                    "Shows how correlated different strategies are — "
                    "useful for portfolio construction. "
                    "Optionally filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: specific window to compute "
                                "correlations for"
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_window_coverage",
                "description": (
                    "Get a summary of all backtest windows — dates, "
                    "duration, and how many strategies ran in each. "
                    "Optionally filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_portfolio_snapshots",
                "description": (
                    "Get portfolio value snapshots for one or more "
                    "strategies — initial value, final value, net gain, "
                    "and growth per window. Use strategy_id for one, or "
                    "strategy_ids for a stacked comparison. "
                    "Use tag to filter by batch."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids for a "
                                "stacked comparison."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": "Optional: specific window name",
                        },
                    },
                },
            },
            {
                "name": "create_note",
                "description": (
                    "Create a new analysis note with markdown content "
                    "and optional strategy selections (keep/maybe/reject). "
                    "Notes are persisted to disk and appear in the "
                    "dashboard Report Builder pane. "
                    "The markdown supports standard formatting (headers, "
                    "lists, tables, bold, italic, code blocks) plus "
                    "inline snapshot embeds: ![[snap:ID]] — this renders "
                    "a captured chart/table snapshot directly in the note. "
                    "Snapshots are added by users via the dashboard capture "
                    "button. Use get_note to see existing snapshot IDs. "
                    "Strategy selections let you tag strategies as "
                    "keep/maybe/reject. The dashboard 'Apply Selection' "
                    "button filters all charts to only show the selected "
                    "strategies. Structure notes like an analysis report: "
                    "title, key findings, per-strategy analysis, "
                    "conclusion with selections."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Title for the note",
                        },
                        "markdown": {
                            "type": "string",
                            "description": (
                                "Markdown content for the note body. "
                                "Supports headers, lists, tables, bold, "
                                "italic, code blocks, blockquotes. "
                                "To embed a snapshot inline, use "
                                "![[snap:ID]] where ID is the snapshot's "
                                "numeric ID (visible via get_note). "
                                "Example: '## Equity Curve\n\n"
                                "![[snap:3]]\n\nThe curve shows...' "
                                "Snapshots referenced inline are shown "
                                "in the rendered note at that position "
                                "instead of at the bottom."
                            ),
                        },
                        "selections": {
                            "type": "object",
                            "description": (
                                "Strategy selections as {strategy_id: tag} "
                                "where tag is 'keep', 'maybe', or 'reject'. "
                                "E.g. {'my_strategy': 'keep', "
                                "'other': 'reject'}. "
                                "When a user clicks "
                                "'Apply Selection' on this "
                                "note, the dashboard filters "
                                "to show only these "
                                "strategies."
                            ),
                        },
                    },
                    "required": ["title"],
                },
            },
            {
                "name": "list_notes",
                "description": (
                    "List all analysis notes with their titles, "
                    "selection counts, and creation dates."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_note",
                "description": (
                    "Get the full content of a specific analysis note "
                    "by its ID — including markdown, selections, "
                    "and snapshot metadata with IDs. Snapshot IDs can "
                    "be used in markdown via ![[snap:ID]] to embed "
                    "charts/tables inline in the note content."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "note_id": {
                            "type": "integer",
                            "description": "The note ID",
                        },
                    },
                    "required": ["note_id"],
                },
            },
            {
                "name": "update_note",
                "description": (
                    "Update an existing note's title, markdown content, "
                    "or strategy selections. Use ![[snap:ID]] in "
                    "markdown to embed existing snapshots inline. "
                    "Tip: use get_note first to see current content "
                    "and available snapshot IDs, then update with "
                    "revised markdown that places snapshots where "
                    "they make sense in the analysis."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "note_id": {
                            "type": "integer",
                            "description": "The note ID to update",
                        },
                        "title": {
                            "type": "string",
                            "description": "New title (optional)",
                        },
                        "markdown": {
                            "type": "string",
                            "description": (
                                "New markdown content (optional). "
                                "Use ![[snap:ID]] to embed snapshot "
                                "images/tables inline at any position."
                            ),
                        },
                        "selections": {
                            "type": "object",
                            "description": (
                                "New selections to merge. Use "
                                "{strategy_id: null} to remove a selection."
                            ),
                        },
                    },
                    "required": ["note_id"],
                },
            },
            {
                "name": "delete_note",
                "description": "Delete an analysis note by its ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "note_id": {
                            "type": "integer",
                            "description": "The note ID to delete",
                        },
                    },
                    "required": ["note_id"],
                },
            },
            {
                "name": "filter_strategies",
                "description": (
                    "Filter strategies by metric conditions. "
                    "Returns strategies matching ALL conditions. "
                    "Example: Sharpe > 1.0 AND Max DD < 0.15. "
                    "Optionally pre-filter by strategy_ids or tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional: filter to specific "
                                "strategy algorithm_ids "
                                "before applying conditions."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name "
                                "before applying conditions."
                            ),
                        },
                        "conditions": {
                            "type": "array",
                            "description": (
                                "Array of conditions, each with metric, "
                                "operator (>, <, >=, <=, ==), and value. "
                                "E.g. [{\"metric\":"
                                "\"sharpe_ratio\","
                                "\"operator\":\">\","
                                "\"value\":1.0}]"
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "metric": {
                                        "type": "string",
                                        "description": (
                                            "Metric name, e.g. sharpe_ratio, "
                                            "cagr, max_drawdown, win_rate, "
                                            "consistency_score, stability_score"
                                        ),
                                    },
                                    "operator": {
                                        "type": "string",
                                        "enum": [">", "<", ">=", "<=", "=="],
                                    },
                                    "value": {
                                        "type": "number",
                                        "description": "Threshold value",
                                    },
                                },
                                "required": ["metric", "operator", "value"],
                            },
                        },
                    },
                    "required": ["conditions"],
                },
            },
            {
                "name": "get_strategy_metadata",
                "description": (
                    "Get all metadata for a specific strategy, including "
                    "parameters, grid profile tags, symbols, market, "
                    "and any other stored metadata."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "The algorithm_id of the strategy"
                            ),
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "list_tags",
                "description": (
                    "List all unique tags across all backtests, with "
                    "the count of strategies per tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_strategies_by_tag",
                "description": (
                    "Get all strategy IDs that match a given tag. "
                    "Tags come from the batch/directory name or "
                    "the strategy's stored tag."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tag": {
                            "type": "string",
                            "description": "The tag to filter by.",
                        },
                    },
                    "required": ["tag"],
                },
            },
            {
                "name": "get_scaled_trades",
                "description": (
                    "Find scaling (pyramiding) activity for a strategy by "
                    "detecting overlapping trades on the same symbol. "
                    "Shows grouped entries with combined cost, net gain, "
                    "and per-entry breakdown."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "The algorithm_id of the strategy"
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: filter to a specific "
                                "backtest window name."
                            ),
                        },
                    },
                    "required": ["strategy_id"],
                },
            },
            {
                "name": "get_stop_loss_take_profit_activity",
                "description": (
                    "Find trades where stop losses or take profits "
                    "were triggered for one or more strategies. "
                    "Shows which trades hit their stop loss or take "
                    "profit, with trigger prices, dates, and trade "
                    "details. Use strategy_ids or tag to check "
                    "multiple strategies at once."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids/tag."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: filter to a specific "
                                "backtest window name."
                            ),
                        },
                        "triggered_only": {
                            "type": "boolean",
                            "description": (
                                "If true (default), only show trades "
                                "where a stop loss or take profit was "
                                "actually triggered. If false, show all "
                                "trades with SL/TP configured."
                            ),
                        },
                    },
                },
            },
            {
                "name": "get_scaling_activity",
                "description": (
                    "Find scaling (pyramiding) activity across one or "
                    "more strategies. Detects trades with multiple buy "
                    "orders (scale-in entries). Use strategy_ids or tag "
                    "to check multiple strategies at once and get a "
                    "summary of which strategies used scaling."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": (
                                "Single strategy algorithm_id. "
                                "Use this OR strategy_ids/tag."
                            ),
                        },
                        "strategy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Multiple strategy algorithm_ids."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": (
                                "Optional: filter to strategies "
                                "with this tag/batch name."
                            ),
                        },
                        "window": {
                            "type": "string",
                            "description": (
                                "Optional: filter to a specific "
                                "backtest window name."
                            ),
                        },
                    },
                },
            },
        ]

    def _resolve_backtests(self, arguments):
        """Filter backtests by strategy_ids and/or tag."""
        backtests = self._backtests
        tag = arguments.get("tag")
        if tag:
            backtests = [
                bt for bt in backtests
                if self._bt_tags.get(bt.algorithm_id) == tag
            ]
        sids = arguments.get("strategy_ids")
        if sids:
            sid_set = set(sids)
            backtests = [
                bt for bt in backtests
                if bt.algorithm_id in sid_set
            ]
        return backtests

    def _resolve_sids(self, arguments):
        """Resolve strategy_ids from strategy_id, strategy_ids, or tag."""
        sids = arguments.get("strategy_ids") or []
        sid = arguments.get("strategy_id", "")
        tag = arguments.get("tag")
        if tag and not sids and not sid:
            sids = [
                bt.algorithm_id for bt in self._backtests
                if self._bt_tags.get(bt.algorithm_id) == tag
            ]
        if sid and not sids:
            sids = [sid]
        return sids

    def _handle_tool_call(self, name, arguments):
        self._ensure_loaded()

        if name == "list_strategies":
            backtests = self._resolve_backtests(arguments)
            has_tags = any(self._bt_tags.values())
            lines = ["# Strategies Overview\n"]
            if has_tags:
                lines.append(
                    "| Strategy | Batch | CAGR | Sharpe"
                    " | Sortino | Max DD "
                    "| Win Rate | Consistency"
                    " | Stability | Profit Factor"
                    " | Trades/Yr | Parameters |"
                )
                lines.append(
                    "|----------|-------|------|-------"
                    "|---------|--------"
                    "|----------|-------------"
                    "|-----------|---------------"
                    "|-----------|------------|"
                )
            else:
                lines.append(
                    "| Strategy | CAGR | Sharpe"
                    " | Sortino | Max DD "
                    "| Win Rate | Consistency"
                    " | Stability | Profit Factor"
                    " | Trades/Yr | Parameters |"
                )
                lines.append(
                    "|----------|------|-------"
                    "|---------|--------"
                    "|----------|-------------"
                    "|-----------|---------------"
                    "|-----------|------------|"
                )
            for bt in backtests:
                s = bt.backtest_summary
                tag = self._bt_tags.get(
                    bt.algorithm_id, ''
                )
                params = ""
                p = bt.parameters
                if not p and bt.metadata and 'params' in bt.metadata:
                    p = {
                        k: v for k, v in bt.metadata['params'].items()
                        if not k.startswith('_')
                    }
                if p:
                    params = ", ".join(
                        f"{k}={v}"
                        for k, v in list(
                            p.items()
                        )[:3]
                    )
                    if len(p) > 3:
                        params += ", ..."
                tag_col = f"| {tag} " if has_tags else ""
                if s:
                    cs = getattr(s, 'consistency_score', None)
                    cs_str = f"{cs:.1%}" if cs is not None else "—"
                    ss = getattr(s, 'stability_score', None)
                    ss_str = f"{ss:.1%}" if ss is not None else "—"
                    lines.append(
                        f"| {bt.algorithm_id} "
                        f"{tag_col}"
                        f"| {_fmt_pct(s.cagr)} "
                        f"| {_fmt_dec(s.sharpe_ratio)} "
                        f"| {_fmt_dec(s.sortino_ratio)} "
                        f"| {_fmt_pct(abs(s.max_drawdown) if s.max_drawdown else None)} "  # noqa: E501
                        f"| {_fmt_pct(s.win_rate)} "
                        f"| {cs_str} "
                        f"| {ss_str} "
                        f"| {_fmt_dec(s.profit_factor)} "
                        f"| {_fmt_dec(s.trades_per_year, 0)} "
                        f"| {params} |"
                    )
                else:
                    lines.append(
                        f"| {bt.algorithm_id} "
                        f"{tag_col}"
                        "| — | — | — | — | — | — | — "
                        f"| {params} |"
                    )
            return "\n".join(lines)

        elif name == "get_strategy_details":
            sid = arguments.get("strategy_id", "")
            bt = self._bt_map.get(sid)
            if not bt:
                avail = list(self._bt_map.keys())
                return (
                    f"Strategy '{sid}' not found."
                    f" Available: {avail}"
                )
            md = f"# {bt.algorithm_id}\n\n"
            tag = self._bt_tags.get(bt.algorithm_id, '')
            if tag:
                md += f"**Batch:** {tag}\n\n"
            p = bt.parameters
            if not p and bt.metadata and 'params' in bt.metadata:
                p = {
                    k: v for k, v in bt.metadata['params'].items()
                    if not k.startswith('_')
                }
            if p:
                params = ", ".join(
                    f"{k}={v}" for k, v in p.items()
                )
                md += f"**Parameters:** {params}\n\n"
            md += "## Summary Metrics\n\n"
            md += _metrics_table(bt) + "\n\n"
            md += "## Per-Window Breakdown\n\n"
            md += _per_window_table(bt) + "\n\n"
            trades = _top_trades(bt, 10)
            if trades:
                md += "## Top Trades\n\n"
                md += (
                    "| Symbol | Opened | Closed"
                    " | Return % | Net Gain"
                    " | Window |\n"
                )
                md += (
                    "|--------|--------|--------"
                    "|----------|----------"
                    "|--------|\n"
                )
                for t in trades:
                    md += (
                        f"| {t['symbol']} | {t['opened']} | {t['closed']} "
                        f"| {t['return_pct']}% | {t['net_gain']} "
                        f"| {t['window']} |\n"
                    )
            return md

        elif name == "rank_strategies":
            backtests = self._resolve_backtests(arguments)
            metric = arguments.get("metric", "sharpe_ratio")
            ascending = arguments.get("ascending", False)
            limit = arguments.get("limit")
            table = _ranking_table(
                backtests, metric, ascending,
                tags=self._bt_tags,
            )
            if limit:
                lines = table.split("\n")
                # Keep header (2 lines) + limit data rows
                table = "\n".join(lines[:2 + limit])
            return table

        elif name == "compare_strategies":
            a_id = arguments.get("strategy_a", "")
            b_id = arguments.get("strategy_b", "")
            bt_a = self._bt_map.get(a_id)
            bt_b = self._bt_map.get(b_id)
            if not bt_a:
                return f"Strategy '{a_id}' not found."
            if not bt_b:
                return f"Strategy '{b_id}' not found."

            sa = bt_a.backtest_summary
            sb = bt_b.backtest_summary
            md = f"# {a_id} vs {b_id}\n\n"

            metrics = [
                "cagr", "sharpe_ratio", "sortino_ratio", "calmar_ratio",
                "profit_factor", "annual_volatility", "max_drawdown",
                "win_rate", "win_loss_ratio", "trades_per_year",
                "trades_per_month", "total_net_gain_percentage",
                "exposure_ratio", "var_95", "cvar_95",
                "average_trade_return_percentage",
                "average_trade_duration",
                "max_consecutive_wins", "max_consecutive_losses",
                "consistency_score", "return_consistency",
                "win_rate_consistency", "sharpe_consistency",
                "stability_score", "return_stability",
                "win_rate_stability", "sharpe_stability",
            ]
            md += f"| Metric | {a_id} | {b_id} | Winner |\n"
            md += "|--------|" + "-" * (len(a_id) + 2) + "|"
            md += "-" * (len(b_id) + 2) + "|--------|\n"
            for m in metrics:
                va = getattr(sa, m, None) if sa else None
                vb = getattr(sb, m, None) if sb else None
                # Determine winner (higher is better, except drawdown/vol)
                lower_better = m in (
                    "max_drawdown", "annual_volatility",
                    "var_95", "cvar_95", "max_consecutive_losses",
                    "average_trade_duration",
                )
                winner = "—"
                if va is not None and vb is not None:
                    if lower_better:
                        winner = a_id if abs(va) < abs(vb) else b_id
                    else:
                        winner = a_id if va > vb else b_id
                md += (
                    f"| {m} | {_fmt_dec(va)} "
                    f"| {_fmt_dec(vb)} | {winner} |\n"
                )
            return md

        elif name == "get_full_analysis":
            backtests = self._resolve_backtests(arguments)
            return _full_analysis(
                backtests, tags=self._bt_tags
            )

        elif name == "get_trading_activity":
            backtests = self._resolve_backtests(arguments)
            return _trading_activity_table(
                backtests, tags=self._bt_tags
            )

        elif name == "get_trades":
            sid = arguments.get("strategy_id", "")
            limit = arguments.get("limit", 20)
            bt = self._bt_map.get(sid)
            if not bt:
                return f"Strategy '{sid}' not found."
            trades = _top_trades(bt, limit)
            if not trades:
                return "No trades found."
            md = f"# Trades for {sid}\n\n"
            md += (
                "| Symbol | Opened | Closed"
                " | Return % | Net Gain"
                " | Window |\n"
            )
            md += (
                "|--------|--------|--------"
                "|----------|----------"
                "|--------|\n"
            )
            for t in trades:
                md += (
                    f"| {t['symbol']} | {t['opened']} | {t['closed']} "
                    f"| {t['return_pct']}% | {t['net_gain']} "
                    f"| {t['window']} |\n"
                )
            return md

        elif name == "get_orders":
            sid = arguments.get("strategy_id", "")
            bt = self._bt_map.get(sid)
            if not bt:
                return f"Strategy '{sid}' not found."
            window = arguments.get("window")
            order_reason = arguments.get("order_reason")
            limit = arguments.get("limit", 50)
            orders = _all_orders(
                bt, window=window, limit=limit,
                order_reason=order_reason,
            )
            if not orders:
                filter_msg = ""
                if order_reason:
                    filter_msg = f" with order_reason='{order_reason}'"
                return f"No orders found{filter_msg}."
            md = f"# Orders for {sid}\n\n"
            if order_reason:
                md += f"*Filtered by order_reason: {order_reason}*\n\n"
            md += (
                "| Symbol | Side | Type | Status"
                " | Price | Amount | Filled"
                " | Cost | Fee | Fee Rate"
                " | Slippage | Reason"
                " | Created | Window |\n"
            )
            md += (
                "|--------|------|------|--------"
                "|-------|--------|--------"
                "|------|-----|----------"
                "|----------|--------"
                "|---------|--------|\n"
            )
            for o in orders:
                md += (
                    f"| {o['symbol']} "
                    f"| {o['side']} "
                    f"| {o['type']} "
                    f"| {o['status']} "
                    f"| {o['price']} "
                    f"| {o['amount']} "
                    f"| {o['filled']} "
                    f"| {o['cost']} "
                    f"| {o['fee']} "
                    f"| {o['fee_rate']} "
                    f"| {o['slippage']} "
                    f"| {o['order_reason']} "
                    f"| {o['created']} "
                    f"| {o['window']} |\n"
                )
            md += (
                f"\n*Showing {len(orders)} orders"
                f" (limit: {limit})*\n"
            )
            return md

        elif name == "get_positions":
            sid = arguments.get("strategy_id", "")
            bt = self._bt_map.get(sid)
            if not bt:
                return f"Strategy '{sid}' not found."
            window = arguments.get("window")
            positions = _all_positions(bt, window=window)
            if not positions:
                return "No positions found."
            md = f"# Positions for {sid}\n\n"
            md += "| Symbol | Amount | Cost | Window |\n"
            md += "|--------|--------|------|--------|\n"
            for p in positions:
                md += (
                    f"| {p['symbol']} "
                    f"| {p['amount']} "
                    f"| {p['cost']} "
                    f"| {p['window']} |\n"
                )
            return md

        elif name == "get_equity_curve":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                return "Provide strategy_id, strategy_ids, or tag."
            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )
            if len(sids) == 1:
                bt = self._bt_map[sids[0]]
                return (
                    f"# Equity Curve — {sids[0]}\n\n"
                    + _equity_curve_table(bt, window=window)
                )
            # Multi-strategy stacked comparison
            return _equity_curves_stacked(
                [self._bt_map[s] for s in sids], sids, window=window
            )

        elif name == "get_drawdown_series":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                return "Provide strategy_id, strategy_ids, or tag."
            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )
            if len(sids) == 1:
                bt = self._bt_map[sids[0]]
                return (
                    f"# Drawdown Series — {sids[0]}\n\n"
                    + _drawdown_series_table(bt, window=window)
                )
            return _drawdown_series_stacked(
                [self._bt_map[s] for s in sids], sids, window=window
            )

        elif name == "get_monthly_returns":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                return "Provide strategy_id, strategy_ids, or tag."
            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )
            if len(sids) == 1:
                bt = self._bt_map[sids[0]]
                return (
                    f"# Monthly Returns — {sids[0]}\n\n"
                    + _monthly_returns_table(bt, window=window)
                )
            return _monthly_returns_stacked(
                [self._bt_map[s] for s in sids], sids, window=window
            )

        elif name == "get_yearly_returns":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                return "Provide strategy_id, strategy_ids, or tag."
            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )
            if len(sids) == 1:
                bt = self._bt_map[sids[0]]
                return (
                    f"# Yearly Returns — {sids[0]}\n\n"
                    + _yearly_returns_table(bt, window=window)
                )
            return _yearly_returns_stacked(
                [self._bt_map[s] for s in sids], sids, window=window
            )

        elif name == "get_rolling_sharpe":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                return "Provide strategy_id, strategy_ids, or tag."
            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )
            if len(sids) == 1:
                bt = self._bt_map[sids[0]]
                return (
                    f"# Rolling Sharpe — {sids[0]}\n\n"
                    + _rolling_sharpe_table(bt, window=window)
                )
            return _rolling_sharpe_stacked(
                [self._bt_map[s] for s in sids], sids, window=window
            )

        elif name == "get_symbol_breakdown":
            sid = arguments.get("strategy_id", "")
            bt = self._bt_map.get(sid)
            if not bt:
                avail = list(self._bt_map.keys())
                return (
                    f"Strategy '{sid}' not found."
                    f" Available: {avail}"
                )
            return (
                f"# Symbol Breakdown — {sid}\n\n"
                + _symbol_breakdown(bt)
            )

        elif name == "get_return_scenarios":
            sid = arguments.get("strategy_id", "")
            bt = self._bt_map.get(sid)
            if not bt:
                avail = list(self._bt_map.keys())
                return (
                    f"Strategy '{sid}' not found."
                    f" Available: {avail}"
                )
            return f"# Return Scenarios — {sid}\n\n" + _return_scenarios(bt)

        elif name == "get_correlation_matrix":
            backtests = self._resolve_backtests(arguments)
            window = arguments.get("window")
            return "# Correlation Matrix\n\n" + _correlation_matrix(
                backtests, window=window
            )

        elif name == "get_window_coverage":
            backtests = self._resolve_backtests(arguments)
            return "# Window Coverage\n\n" + _window_coverage(
                backtests
            )

        elif name == "get_portfolio_snapshots":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                return "Provide strategy_id, strategy_ids, or tag."
            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )
            if len(sids) == 1:
                bt = self._bt_map[sids[0]]
                return (
                    f"# Portfolio Snapshots — {sids[0]}\n\n"
                    + _portfolio_snapshots(bt, window=window)
                )
            return _portfolio_snapshots_stacked(
                [self._bt_map[s] for s in sids], sids, window=window
            )

        elif name == "create_note":
            data = _load_notes(self.directory)
            data["noteIdCounter"] = data.get("noteIdCounter", 0) + 1
            note_id = data["noteIdCounter"]
            title = arguments.get("title", "Untitled Note")
            markdown = arguments.get("markdown", "")
            selections = arguments.get("selections", {})
            # Validate selections reference real strategies
            valid_selections = {}
            for sid, tag in selections.items():
                if sid in self._bt_map and tag in ("keep", "maybe", "reject"):
                    valid_selections[sid] = tag
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            note = {
                "id": note_id,
                "title": title,
                "markdown": markdown,
                "selections": valid_selections,
                "snapshots": [],
                "createdAt": now,
                "updatedAt": now,
            }
            data["notes"].insert(0, note)
            _save_notes(self.directory, data)
            return (
                f"# Note Created (ID: {note_id})\n\n"
                f"**Title:** {title}\n"
                f"**Selections:** {len(valid_selections)}\n\n"
                f"The note has been saved. It will appear in the dashboard "
                f"Report Builder pane when you reload the report.\n\n"
                f"**Tip:** If the user captures chart snapshots in the "
                f"dashboard, you can use `get_note` to see their IDs, "
                f"then `update_note` to embed them in the markdown with "
                f"`![[snap:ID]]`."
            )

        elif name == "list_notes":
            data = _load_notes(self.directory)
            notes = data.get("notes", [])
            if not notes:
                return "No analysis notes found."
            md = "# Analysis Notes\n\n"
            md += "| ID | Title | Selections | Snapshots | Updated |\n"
            md += "|----|-------|------------|-----------|----------|\n"
            for n in notes:
                sel_count = len(n.get("selections", {}))
                snap_count = len(n.get("snapshots", []))
                updated = n.get("updatedAt", "")[:10]
                md += (
                    f"| {n['id']} | {n['title']} "
                    f"| {sel_count} | {snap_count} | {updated} |\n"
                )
            return md

        elif name == "get_note":
            note_id = arguments.get("note_id")
            data = _load_notes(self.directory)
            note = None
            for n in data.get("notes", []):
                if n["id"] == note_id:
                    note = n
                    break
            if not note:
                ids = [n["id"] for n in data.get("notes", [])]
                return f"Note {note_id} not found. Available IDs: {ids}"
            md = f"# {note['title']} (ID: {note['id']})\n\n"
            md += f"**Created:** {note.get('createdAt', '')[:10]}\n"
            md += f"**Updated:** {note.get('updatedAt', '')[:10]}\n\n"
            sels = note.get("selections", {})
            if sels:
                md += "## Strategy Selections\n\n"
                for sid, tag in sels.items():
                    icon = (
                        "✅" if tag == "keep"
                        else "❓" if tag == "maybe"
                        else "❌"
                    )
                    md += f"- {icon} **{sid}**: {tag}\n"
                md += "\n"
            if note.get("markdown", "").strip():
                md += "## Content\n\n"
                md += note["markdown"] + "\n\n"
            snaps = note.get("snapshots", [])
            if snaps:
                md += f"## Snapshots ({len(snaps)})\n\n"
                md += (
                    "Use `![[snap:ID]]` in the note's markdown to "
                    "embed a snapshot inline.\n\n"
                )
                md += "| ID | Title | Type | Embedded? |\n"
                md += "|----|-------|------|-----------|\n"
                for s in snaps:
                    sid = s.get("id", "?")
                    title = s.get("title", "Untitled")
                    stype = s.get("type", "unknown")
                    ref = f"![[snap:{sid}]]"
                    is_embedded = ref in note.get("markdown", "")
                    md += (
                        f"| {sid} | {title} | {stype} "
                        f"| {'Yes' if is_embedded else 'No'} |\n"
                    )
                md += (
                    "\nTo embed a snapshot, place `![[snap:ID]]` on its "
                    "own line in the markdown. It will render as the full "
                    "chart image or table inline.\n"
                )
            return md

        elif name == "update_note":
            note_id = arguments.get("note_id")
            data = _load_notes(self.directory)
            note = None
            for n in data.get("notes", []):
                if n["id"] == note_id:
                    note = n
                    break
            if not note:
                return f"Note {note_id} not found."
            if "title" in arguments:
                note["title"] = arguments["title"]
            if "markdown" in arguments:
                note["markdown"] = arguments["markdown"]
            if "selections" in arguments:
                new_sels = arguments["selections"]
                for sid, tag in new_sels.items():
                    if tag is None:
                        note["selections"].pop(sid, None)
                    elif tag in ("keep", "maybe", "reject"):
                        note["selections"][sid] = tag
            from datetime import datetime, timezone
            note["updatedAt"] = datetime.now(timezone.utc).isoformat()
            _save_notes(self.directory, data)
            return f"Note {note_id} updated successfully."

        elif name == "delete_note":
            note_id = arguments.get("note_id")
            data = _load_notes(self.directory)
            original_count = len(data.get("notes", []))
            data["notes"] = [
                n for n in data.get("notes", []) if n["id"] != note_id
            ]
            if len(data["notes"]) == original_count:
                return f"Note {note_id} not found."
            _save_notes(self.directory, data)
            return f"Note {note_id} deleted."

        elif name == "filter_strategies":
            backtests = self._resolve_backtests(arguments)
            conditions = arguments.get("conditions", [])
            if not conditions:
                return "No conditions provided."
            matched = _filter_strategies(backtests, conditions)
            if not matched:
                return "No strategies match all conditions."
            total = len(backtests)
            md = (
                f"# Filtered Strategies"
                f" ({len(matched)} of {total})\n\n"
            )
            md += "**Conditions:** "
            md += ", ".join(
                f"{c['metric']} {c['operator']} {c['value']}"
                for c in conditions
            )
            md += "\n\n"
            md += (
                "| Strategy | CAGR | Sharpe | Sortino | Max DD "
                "| Win Rate | Profit Factor |\n"
            )
            md += (
                "|----------|------|--------|---------|--------"
                "|----------|---------------|\n"
            )
            for bt in matched:
                s = bt.backtest_summary
                if s:
                    md += (
                        f"| {bt.algorithm_id} "
                        f"| {_fmt_pct(s.cagr)} "
                        f"| {_fmt_dec(s.sharpe_ratio)} "
                        f"| {_fmt_dec(s.sortino_ratio)} "
                        f"| {_fmt_pct(abs(s.max_drawdown) if s.max_drawdown else None)} "  # noqa: E501
                        f"| {_fmt_pct(s.win_rate)} "
                        f"| {_fmt_dec(s.profit_factor)} |\n"
                    )
            return md

        elif name == "get_strategy_metadata":
            sid = arguments.get("strategy_id", "")
            bt = self._bt_map.get(sid)
            if not bt:
                avail = list(self._bt_map.keys())
                return (
                    f"Strategy '{sid}' not found."
                    f" Available: {avail}"
                )
            md = f"# Metadata for {bt.algorithm_id}\n\n"
            tag = self._bt_tags.get(bt.algorithm_id, '')
            if tag:
                md += f"**Tag:** {tag}\n\n"
            if bt.parameters:
                md += "## Parameters\n\n"
                for k, v in bt.parameters.items():
                    md += f"- **{k}**: {v}\n"
                md += "\n"
            if bt.metadata:
                md += "## Metadata\n\n"
                for k, v in bt.metadata.items():
                    if isinstance(v, dict):
                        md += f"### {k}\n\n"
                        for dk, dv in v.items():
                            md += f"- **{dk}**: {dv}\n"
                        md += "\n"
                    elif isinstance(v, list):
                        md += f"- **{k}**: {', '.join(str(x) for x in v)}\n"
                    else:
                        md += f"- **{k}**: {v}\n"
            return md

        elif name == "list_tags":
            tag_counts = {}
            for bt in self._backtests:
                tag = self._bt_tags.get(bt.algorithm_id, '')
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if not tag_counts:
                return "No tags found across any strategies."
            md = "# Tags Overview\n\n"
            md += "| Tag | Strategies |\n"
            md += "|-----|------------|\n"
            for tag, count in sorted(tag_counts.items()):
                md += f"| {tag} | {count} |\n"
            md += f"\n**Total:** {len(tag_counts)} tags, "
            md += f"{sum(tag_counts.values())} strategies\n"
            return md

        elif name == "get_strategies_by_tag":
            tag = arguments.get("tag", "")
            matched = [
                bt for bt in self._backtests
                if self._bt_tags.get(bt.algorithm_id) == tag
            ]
            if not matched:
                all_tags = set(
                    t for t in self._bt_tags.values() if t
                )
                return (
                    f"No strategies found with tag '{tag}'. "
                    f"Available tags: {sorted(all_tags)}"
                )
            md = f"# Strategies with tag: {tag}\n\n"
            md += f"**Count:** {len(matched)}\n\n"
            md += "| Strategy | CAGR | Sharpe | Trades/Yr |\n"
            md += "|----------|------|--------|----------|\n"
            for bt in matched:
                s = bt.backtest_summary
                if s:
                    md += (
                        f"| {bt.algorithm_id} "
                        f"| {_fmt_pct(s.cagr)} "
                        f"| {_fmt_dec(s.sharpe_ratio)} "
                        f"| {_fmt_dec(s.trades_per_year, 0)} |\n"
                    )
                else:
                    md += f"| {bt.algorithm_id} | — | — | — |\n"
            return md

        elif name == "get_scaled_trades":
            sid = arguments.get("strategy_id", "")
            window = arguments.get("window")
            bt = self._bt_map.get(sid)
            if not bt:
                avail = list(self._bt_map.keys())
                return (
                    f"Strategy '{sid}' not found."
                    f" Available: {avail}"
                )

            # Find scaling activity by detecting overlapping open trades
            # for the same symbol (multiple concurrent positions = scaling)
            scaled_groups = []
            for run in bt.get_all_backtest_runs():
                if window and run.backtest_date_range_name != window:
                    continue
                wname = run.backtest_date_range_name or "—"
                trades = run.trades or []

                # Group trades by symbol
                by_symbol = {}
                for t in trades:
                    sym = getattr(t, 'target_symbol', '—')
                    by_symbol.setdefault(sym, []).append(t)

                for sym, sym_trades in by_symbol.items():
                    if len(sym_trades) < 2:
                        continue

                    # Sort by opened_at
                    sym_trades.sort(
                        key=lambda t: t.opened_at or t.opened_at
                    )

                    # Find groups of overlapping trades (scaling)
                    # A trade overlaps if it opened before the previous
                    # trade closed
                    group = [sym_trades[0]]
                    for t in sym_trades[1:]:
                        prev = group[-1]
                        prev_closed = getattr(prev, 'closed_at', None)
                        t_opened = getattr(t, 'opened_at', None)

                        # Overlapping if previous not closed yet when
                        # this one opened, or both open at same time
                        if (prev_closed is None
                                or (t_opened and t_opened <= prev_closed)):
                            group.append(t)
                        else:
                            if len(group) > 1:
                                scaled_groups.append(
                                    (sym, wname, list(group))
                                )
                            group = [t]

                    if len(group) > 1:
                        scaled_groups.append(
                            (sym, wname, list(group))
                        )

            if not scaled_groups:
                return (
                    f"No scaling activity found for strategy "
                    f"{sid}. No overlapping trades for the "
                    f"same symbol were detected."
                )

            md = f"# Scaling Activity for {sid}\n\n"
            md += (
                f"**{len(scaled_groups)} scaling group(s)** found "
                f"(overlapping trades on the same symbol)\n\n"
            )

            for i, (sym, wname, group) in enumerate(scaled_groups, 1):
                total_cost = sum(
                    float(getattr(t, 'cost', 0) or 0) for t in group
                )
                total_ng = sum(
                    float(getattr(t, 'net_gain', 0) or 0) for t in group
                )
                total_pct = (
                    (total_ng / total_cost * 100) if total_cost else 0
                )
                first_open = min(
                    t.opened_at for t in group if t.opened_at
                )
                last_close = None
                closes = [
                    t.closed_at for t in group
                    if getattr(t, 'closed_at', None)
                ]
                if closes:
                    last_close = max(closes)

                md += f"## Group {i}: {sym} ({wname})\n\n"
                md += f"- **Entries:** {len(group)}\n"
                md += f"- **First opened:** {_fmt_date(first_open)}\n"
                md += (
                    f"- **Last closed:** "
                    f"{_fmt_date(last_close)}\n"
                )
                md += f"- **Combined cost:** {total_cost:.2f}\n"
                md += f"- **Combined net gain:** {total_ng:.2f}\n"
                md += f"- **Combined return:** {total_pct:.2f}%\n\n"

                md += (
                    "| # | Opened | Closed | Price "
                    "| Cost | Net Gain | Return |\n"
                )
                md += (
                    "|---|--------|--------|-------"
                    "|------|----------|--------|\n"
                )
                for j, t in enumerate(group, 1):
                    cost = float(getattr(t, 'cost', 0) or 0)
                    ng = float(getattr(t, 'net_gain', 0) or 0)
                    pct = (ng / cost * 100) if cost else 0
                    md += (
                        f"| {j} "
                        f"| {_fmt_date(t.opened_at)} "
                        f"| {_fmt_date(getattr(t, 'closed_at', None))} "
                        f"| {float(getattr(t, 'open_price', 0) or 0):.4f} "
                        f"| {cost:.2f} "
                        f"| {ng:.2f} "
                        f"| {pct:.2f}% |\n"
                    )
                md += "\n"

            return md

        elif name == "get_stop_loss_take_profit_activity":
            window = arguments.get("window")
            triggered_only = arguments.get("triggered_only", True)
            sids = self._resolve_sids(arguments)
            if not sids:
                # If no specific IDs, use all backtests
                # (possibly filtered by tag)
                backtests = self._resolve_backtests(arguments)
                sids = [bt.algorithm_id for bt in backtests]

            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )

            md = "# Stop Loss & Take Profit Activity\n\n"
            any_found = False

            for sid in sids:
                bt = self._bt_map[sid]
                sl_trades = []
                tp_trades = []

                for run in bt.get_all_backtest_runs():
                    if window and run.backtest_date_range_name != window:
                        continue
                    wname = run.backtest_date_range_name or "—"
                    for t in (run.trades or []):
                        # Check stop losses
                        for sl in (t.stop_losses or []):
                            if triggered_only and not getattr(
                                sl, 'triggered', False
                            ):
                                continue
                            sl_trades.append({
                                "symbol": getattr(
                                    t, 'target_symbol', '—'),
                                "opened": _fmt_date(t.opened_at),
                                "closed": _fmt_date(
                                    getattr(t, 'closed_at', None)),
                                "open_price": float(
                                    getattr(t, 'open_price', 0) or 0),
                                "sl_price": float(
                                    getattr(sl, 'stop_loss_price', 0)
                                    or 0),
                                "sl_pct": float(
                                    getattr(sl, 'percentage', 0) or 0),
                                "trailing": getattr(
                                    sl, 'trailing', False),
                                "triggered": getattr(
                                    sl, 'triggered', False),
                                "triggered_at": _fmt_date(
                                    getattr(sl, 'triggered_at', None)),
                                "net_gain": float(
                                    getattr(t, 'net_gain', 0) or 0),
                                "window": wname,
                            })
                        # Check take profits
                        for tp in (t.take_profits or []):
                            if triggered_only and not getattr(
                                tp, 'triggered', False
                            ):
                                continue
                            tp_trades.append({
                                "symbol": getattr(
                                    t, 'target_symbol', '—'),
                                "opened": _fmt_date(t.opened_at),
                                "closed": _fmt_date(
                                    getattr(t, 'closed_at', None)),
                                "open_price": float(
                                    getattr(t, 'open_price', 0) or 0),
                                "tp_price": float(
                                    getattr(tp, 'take_profit_price', 0)
                                    or 0),
                                "tp_pct": float(
                                    getattr(tp, 'percentage', 0) or 0),
                                "trailing": getattr(
                                    tp, 'trailing', False),
                                "triggered": getattr(
                                    tp, 'triggered', False),
                                "triggered_at": _fmt_date(
                                    getattr(tp, 'triggered_at', None)),
                                "net_gain": float(
                                    getattr(t, 'net_gain', 0) or 0),
                                "window": wname,
                            })

                if not sl_trades and not tp_trades:
                    continue

                any_found = True
                md += f"## {sid}\n\n"

                if sl_trades:
                    md += (
                        f"### Stop Losses "
                        f"({len(sl_trades)} "
                        f"{'triggered' if triggered_only else 'configured'})"
                        f"\n\n"
                    )
                    md += (
                        "| Symbol | Opened | Closed | Open Price"
                        " | SL Price | SL % | Trailing"
                        " | Triggered | Triggered At"
                        " | Net Gain | Window |\n"
                    )
                    md += (
                        "|--------|--------|--------|----------"
                        "|----------|------|----------"
                        "|-----------|-------------|"
                        "----------|--------|\n"
                    )
                    for s in sl_trades:
                        md += (
                            f"| {s['symbol']} "
                            f"| {s['opened']} "
                            f"| {s['closed']} "
                            f"| {s['open_price']:.4f} "
                            f"| {s['sl_price']:.4f} "
                            f"| {s['sl_pct']:.1f}% "
                            f"| {'Yes' if s['trailing'] else 'No'} "
                            f"| {'Yes' if s['triggered'] else 'No'} "
                            f"| {s['triggered_at']} "
                            f"| {s['net_gain']:.2f} "
                            f"| {s['window']} |\n"
                        )
                    md += "\n"

                if tp_trades:
                    md += (
                        f"### Take Profits "
                        f"({len(tp_trades)} "
                        f"{'triggered' if triggered_only else 'configured'})"
                        f"\n\n"
                    )
                    md += (
                        "| Symbol | Opened | Closed | Open Price"
                        " | TP Price | TP % | Trailing"
                        " | Triggered | Triggered At"
                        " | Net Gain | Window |\n"
                    )
                    md += (
                        "|--------|--------|--------|----------"
                        "|----------|------|----------"
                        "|-----------|-------------|"
                        "----------|--------|\n"
                    )
                    for s in tp_trades:
                        md += (
                            f"| {s['symbol']} "
                            f"| {s['opened']} "
                            f"| {s['closed']} "
                            f"| {s['open_price']:.4f} "
                            f"| {s['tp_price']:.4f} "
                            f"| {s['tp_pct']:.1f}% "
                            f"| {'Yes' if s['trailing'] else 'No'} "
                            f"| {'Yes' if s['triggered'] else 'No'} "
                            f"| {s['triggered_at']} "
                            f"| {s['net_gain']:.2f} "
                            f"| {s['window']} |\n"
                        )
                    md += "\n"

            if not any_found:
                trig_msg = (
                    "triggered" if triggered_only
                    else "configured"
                )
                return (
                    f"No stop loss or take profit activity "
                    f"({trig_msg}) found for the requested "
                    f"strategies."
                )
            return md

        elif name == "get_scaling_activity":
            window = arguments.get("window")
            sids = self._resolve_sids(arguments)
            if not sids:
                backtests = self._resolve_backtests(arguments)
                sids = [bt.algorithm_id for bt in backtests]

            missing = [s for s in sids if s not in self._bt_map]
            if missing:
                return (
                    f"Strategy not found: {missing}. "
                    f"Available: {list(self._bt_map.keys())}"
                )

            md = "# Scaling Activity Summary\n\n"
            any_found = False

            # Summary table first
            summary_rows = []
            for sid in sids:
                bt = self._bt_map[sid]
                total_trades = 0
                scaled_trades = 0

                for run in bt.get_all_backtest_runs():
                    if window and run.backtest_date_range_name != window:
                        continue
                    for t in (run.trades or []):
                        total_trades += 1
                        # A scaled trade has multiple buy orders
                        buy_orders = [
                            o for o in (t.orders or [])
                            if str(getattr(o, 'order_side', ''))
                            .upper() in ('BUY', 'ORDERSID.BUY')
                        ]
                        if len(buy_orders) > 1:
                            scaled_trades += 1

                if scaled_trades > 0:
                    any_found = True
                summary_rows.append({
                    "sid": sid,
                    "total": total_trades,
                    "scaled": scaled_trades,
                })

            md += (
                "| Strategy | Total Trades | Scaled Trades"
                " | Scaling Rate |\n"
            )
            md += (
                "|----------|-------------|---------------"
                "|--------------|\n"
            )
            for r in summary_rows:
                rate = (
                    f"{r['scaled'] / r['total'] * 100:.1f}%"
                    if r['total'] else "—"
                )
                md += (
                    f"| {r['sid']} | {r['total']} "
                    f"| {r['scaled']} | {rate} |\n"
                )
            md += "\n"

            if not any_found:
                md += (
                    "No scaling activity detected. "
                    "No trades had multiple buy orders.\n"
                )
                return md

            # Detailed breakdown for strategies with scaling
            for sid in sids:
                bt = self._bt_map[sid]
                scaled_details = []

                for run in bt.get_all_backtest_runs():
                    if window and run.backtest_date_range_name != window:
                        continue
                    wname = run.backtest_date_range_name or "—"
                    for t in (run.trades or []):
                        buy_orders = [
                            o for o in (t.orders or [])
                            if str(getattr(o, 'order_side', ''))
                            .upper() in ('BUY', 'ORDERSID.BUY')
                        ]
                        if len(buy_orders) <= 1:
                            continue
                        sym = getattr(t, 'target_symbol', '—')
                        cost = float(getattr(t, 'cost', 0) or 0)
                        ng = float(getattr(t, 'net_gain', 0) or 0)
                        pct = (ng / cost * 100) if cost else 0
                        scaled_details.append({
                            "symbol": sym,
                            "entries": len(buy_orders),
                            "opened": _fmt_date(t.opened_at),
                            "closed": _fmt_date(
                                getattr(t, 'closed_at', None)),
                            "cost": cost,
                            "net_gain": ng,
                            "return_pct": pct,
                            "window": wname,
                        })

                if not scaled_details:
                    continue

                md += f"## {sid} — Scaled Trades\n\n"
                md += (
                    "| Symbol | Entries | Opened | Closed"
                    " | Cost | Net Gain | Return"
                    " | Window |\n"
                )
                md += (
                    "|--------|---------|--------|--------"
                    "|------|----------|--------"
                    "|--------|\n"
                )
                for d in scaled_details:
                    md += (
                        f"| {d['symbol']} "
                        f"| {d['entries']} "
                        f"| {d['opened']} "
                        f"| {d['closed']} "
                        f"| {d['cost']:.2f} "
                        f"| {d['net_gain']:.2f} "
                        f"| {d['return_pct']:.2f}% "
                        f"| {d['window']} |\n"
                    )
                md += "\n"

            return md

        return f"Unknown tool: {name}"

    def handle_request(self, request):
        """Handle a single JSON-RPC 2.0 request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": "backtest-analysis",
                        "version": "1.0.0",
                    },
                },
            }

        elif method == "notifications/initialized":
            return None  # No response for notifications

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self._get_tools(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                result_text = self._handle_tool_call(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": result_text},
                        ],
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error: {e}"},
                        ],
                        "isError": True,
                    },
                }

        else:
            # Unknown method
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    def run(self):
        """Run the MCP server on stdio."""
        _log("Run loop started, waiting for JSON-RPC requests on stdin...")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    _log("stdin closed (EOF), shutting down.")
                    break
                line = line.strip()
                if not line:
                    continue
                _log(f"Received request: {line[:200]}")
                request = json.loads(line)
                response = self.handle_request(request)
                if response is not None:
                    out = json.dumps(response)
                    _log(f"Sending response: {out[:200]}")
                    sys.stdout.write(out + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError as exc:
                _log(f"JSON decode error: {exc}")
                continue
            except KeyboardInterrupt:
                _log("Interrupted (KeyboardInterrupt), shutting down.")
                break
        _log("Server stopped.")


def _log(msg):
    """Write a debug message to stderr (stdout is reserved for JSON-RPC)."""
    sys.stderr.write(f"[MCP-DEBUG] {msg}\n")
    sys.stderr.flush()


def main(directory: Optional[Union[str, List[str]]] = None):
    """Entry point for the MCP server."""
    _log("MCP server starting...")
    _log(f"Python: {sys.executable} ({sys.version})")
    _log(f"CWD: {os.getcwd()}")
    _log(f"directory arg (from caller): {directory}")

    parser = argparse.ArgumentParser(
        description="Backtest Analysis MCP Server"
    )
    parser.add_argument(
        "--directory", "-d",
        action="append",
        required=directory is None,
        default=None,
        help=(
            "Path to a backtest directory (batch folder). "
            "Can be specified multiple times for multiple directories."
        ),
    )
    args = parser.parse_args()
    dirs = args.directory or (
        [directory] if isinstance(directory, str)
        else directory
    ) or []

    _log(f"Resolved directories: {dirs}")
    for d in dirs:
        abs_d = os.path.abspath(d)
        _log(f"  {d} -> {abs_d} (exists={os.path.isdir(abs_d)})")

    if len(dirs) == 1:
        server = BacktestMCPServer(dirs[0])
    else:
        server = BacktestMCPServer(dirs)

    _log("Server created, entering run loop (listening on stdin)...")
    server.run()


if __name__ == "__main__":
    main()
