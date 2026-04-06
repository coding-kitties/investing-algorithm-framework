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
- Strategy ranking table (sortable by CAGR, Sharpe, Max DD, etc.)
- Normalized equity curves overlay
- Per-strategy detail pages with Summary, Runs, and Performance tabs
- Compare mode for selected strategies

### From Saved Backtests on Disk

Load previously saved backtests from a directory:

```python
report = BacktestReport.open(directory_path="./my_backtests")
report.show()
```

The `open()` method recursively finds all valid backtest directories (containing `results.json` and `metrics.json`) and loads them into a single report.

You can also combine disk and in-memory backtests:

```python
report = BacktestReport.open(
    backtests=[my_new_backtest],
    directory_path="./saved_backtests"
)
report.show()
```

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
- **KPI cards**: Strategies count, backtest windows, best CAGR, best Sharpe, lowest max drawdown
- **Backtest windows table**: Date ranges, duration, number of strategies per window
- **Strategy ranking table**: Sortable by any metric, with best-in-class highlighting
- **Equity curves**: Normalized percentage growth overlay for all strategies

### Strategy Pages
Each strategy gets a dedicated page with three tabs:

| Tab | Contents |
|-----|----------|
| **Summary** | Full KPI grid (CAGR, Sharpe, Sortino, Calmar, Max DD, Profit Factor, Win Rate, Volatility, etc.) |
| **Runs** | Backtest run comparison table, equity overlay across runs |
| **Performance** | Monthly returns heatmap, yearly returns bar chart |

Use the run selector pills to switch between summary view and individual backtest runs.

### Compare Mode (Multi-Strategy)
Select strategies via checkboxes in the ranking table, then click **Compare Selected** to see:
- Side-by-side equity curves
- Metric bar charts (CAGR, Sharpe, Max DD, Win Rate)
- Monthly and yearly return comparisons

### Dark / Light Theme
Toggle between dark and light mode using the sun icon in the top-right corner.

## Example: Full Workflow

```python
from datetime import datetime, timezone
from investing_algorithm_framework import (
    create_app, BacktestDateRange, BacktestReport
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
