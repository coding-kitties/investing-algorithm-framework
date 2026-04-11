---
sidebar_position: 9
---

# Backtest Reports

The framework generates self-contained HTML dashboard reports for analyzing backtest results. Reports work for both single and multi-strategy backtests — no external dependencies required.

## Quick Start

```python
from investing_algorithm_framework import BacktestReport

# Single strategy report
report = BacktestReport(backtest)
report.show()  # Opens in browser (or renders inline in Jupyter)
```

## Creating Reports

### From a Backtest Object

After running a backtest, pass the result directly:

```python
backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)

report = BacktestReport(backtest)
report.show(browser=True)
```

### From Multiple Backtests

Compare strategies side by side in a single dashboard:

```python
backtest_a = app.run_backtest(...)
backtest_b = app.run_backtest(...)

report = BacktestReport(backtests=[backtest_a, backtest_b])
report.show()
```

This generates a multi-strategy comparison dashboard with:
- Strategy ranking tables (Key Metrics, Trading Activity)
- Return Scenarios projections (Good/Average/Bad/Very Bad Year)
- Normalized equity curves overlay
- Per-strategy detail pages with Summary, Runs, and Performance tabs
- Compare mode with monthly return distribution (Rows/Heatmap × Returns/Growth toggles)

### From Saved Backtests on Disk

Load previously saved backtests from a directory:

```python
report = BacktestReport.open(directory_path="./my_backtests")
report.show()
```

The `open()` method recursively finds all valid backtest directories (containing `algorithm_id.json` and a `runs/` folder) and loads them into a single report.

You can also combine disk and in-memory backtests:

```python
report = BacktestReport.open(
    backtests=[my_new_backtest],
    directory_path="./saved_backtests"
)
report.show()
```

## Recalculating Metrics

When metric calculations are updated in a newer framework version, previously saved backtests may have stale metrics. Use `recalculate_backtests` to recompute all per-run and summary metrics from the raw portfolio snapshots and trades:

```python
from investing_algorithm_framework import BacktestReport, recalculate_backtests

report = BacktestReport.open(directory_path="./my_backtests")

# Recalculate all metrics for all backtests
recalculate_backtests(report.backtests)

report.show()
```

You can specify a custom risk-free rate (otherwise each backtest's stored rate is used):

```python
recalculate_backtests(report.backtests, risk_free_rate=0.04)
```

Or limit which metrics are recomputed:

```python
recalculate_backtests(
    report.backtests,
    metrics=["cagr", "sharpe_ratio", "max_drawdown", "win_rate"]
)
```

`recalculate_backtests` works on any list of `Backtest` objects, not just those loaded from disk:

```python
from investing_algorithm_framework import recalculate_backtests

backtests = [backtest_a, backtest_b, backtest_c]
recalculate_backtests(backtests, risk_free_rate=0.027)
```

For each backtest, the function:
1. Recomputes per-run `BacktestMetrics` from raw `portfolio_snapshots` and `trades`
2. Regenerates `BacktestSummaryMetrics` by aggregating the updated per-run metrics

## Saving Reports

Save the report as a standalone HTML file you can share or open later:

```python
report = BacktestReport(backtests=[backtest_a, backtest_b])
report.save("strategy_comparison.html")
```

The output is a single `.html` file with all CSS, JavaScript, and data embedded — no server or internet connection needed to view it.

## Viewing in Jupyter

`show()` automatically detects Jupyter notebooks and renders the dashboard inline:

```python
# In a Jupyter notebook cell:
report = BacktestReport.open(directory_path="./backtests")
report.show()           # Renders inline in the notebook
report.show(browser=True)  # Also opens in the browser
```

## Dashboard Features

### Overview Page
- **KPI cards**: Best CAGR, best Sharpe, lowest max drawdown (with dual values when a window is selected)
- **Window Coverage**: Strategy × window matrix showing data coverage
- **Key Metrics table**: Sortable ranking with CAGR, Sharpe, Sortino, Calmar, Max DD, Volatility, Recovery Factor, Net Gain %
- **Trading Activity table**: Profit Factor, Win Rate, Trades/yr, Trades/mo, Trades/wk, # Trades, Avg Return, Avg Duration
- **Return Scenarios**: Good/Average/Bad/Very Bad Year projections based on CAGR ± volatility
- **Equity curves**: Normalized percentage growth overlay
- **Collapsible cards**: All chart sections can be collapsed/expanded

### Strategy Pages
Each strategy gets a dedicated page with three tabs:

| Tab | Contents |
|-----|----------|
| **Summary** | Full KPI grid (CAGR, Sharpe, Sortino, Calmar, Max DD, Profit Factor, Win Rate, Volatility, Recovery Factor, etc.) |
| **Runs** | Backtest run comparison table, equity overlay across runs |
| **Performance** | Monthly returns heatmap, yearly returns bar chart, return distribution |

Use the run selector pills to switch between summary view and individual backtest runs.

### Compare Mode (Multi-Strategy)
Open the strategy selection modal to pick strategies for comparison. You can set a challenger strategy for highlighting. The compare page includes:
- **Key Metrics** and **Trading Activity** ranking tables
- **Return Scenarios** projections
- **Monthly Returns** with four view modes (Returns/Growth × Rows/Heatmap), plus a year filter
- Side-by-side equity curves and drawdown overlays
- Metric bar charts (CAGR, Sharpe, Sortino, Calmar, Max DD, Win Rate, Profit Factor)
- Return distribution histograms and correlation matrix
- Rolling Sharpe ratio chart
- Yearly returns bar charts

### Sticky Navigation
The page title bar with the window selector stays visible as you scroll.

### Dark / Light Theme
Toggle between dark and light mode using the sun icon in the top-right corner.

## Example: Full Workflow

```python
from datetime import datetime, timezone
from investing_algorithm_framework import (
    create_app, BacktestDateRange, BacktestReport, recalculate_backtests
)

app = create_app()
# ... configure strategies, market, portfolio ...

# Run backtests across multiple time periods
date_ranges = [
    BacktestDateRange(
        start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2022, 12, 31, tzinfo=timezone.utc),
        name="2022"
    ),
    BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
        name="2023"
    ),
]

backtests = app.run_vector_backtests(
    strategies=my_strategies,
    backtest_date_ranges=date_ranges,
    initial_amount=1000,
    backtest_storage_directory="./backtests"
)

# Optional: recalculate metrics with updated calculations
recalculate_backtests(backtests, risk_free_rate=0.04)

# Generate and save the comparison report
report = BacktestReport(backtests=backtests)
report.save("comparison_report.html")
report.show(browser=True)
```

## API Reference

### `BacktestReport`

| Method | Description |
|--------|-------------|
| `BacktestReport(backtests=[...])` | Create a report from one or more Backtest objects |
| `BacktestReport(backtest)` | Create a report from a single Backtest (backward compatible) |
| `BacktestReport.open(directory_path=..., backtests=[...])` | Load backtests from disk and/or combine with in-memory backtests |
| `report.show(browser=False)` | Display the report. In Jupyter: renders inline. Otherwise: opens browser. Set `browser=True` to force browser. |
| `report.save(path)` | Save the report as a self-contained HTML file |

### `recalculate_backtests`

| Parameter | Type | Description |
|-----------|------|-------------|
| `backtests` | `List[Backtest]` | The backtests to recalculate (mutated in place and returned) |
| `risk_free_rate` | `float`, optional | Override risk-free rate. If `None`, uses each backtest's stored rate (falls back to `0.0`) |
| `metrics` | `List[str]`, optional | Specific metrics to compute. If `None`, computes all default metrics |

**Returns:** `List[Backtest]` — the same backtest objects with updated metrics.

Recalculates all per-run `BacktestMetrics` from raw portfolio snapshots and trades, then regenerates `BacktestSummaryMetrics` for each backtest.
