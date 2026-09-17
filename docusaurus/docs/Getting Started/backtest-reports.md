---
sidebar_position: 10
---

# Backtest Reports

`BacktestReport` turns persisted backtest results into an interactive HTML
dashboard. Use it to compare studies and engines, inspect individual windows,
review trades and risk, and record research decisions. Reports work with one
backtest, many algorithms, and `.obtf` bundles containing multiple studies or
both execution engines.

:::tip Working with hundreds or thousands of backtests?
A `BacktestReport` inlines every backtest into a single HTML file, which becomes too heavy for a browser past a few dozen backtests. Use the [Backtest Storage Layer](./backtest-storage.md) to filter your collection down (in SQLite, sub-100 ms) and render reports only over the winners.
:::

## Quick Start

```python
from investing_algorithm_framework import BacktestReport

# Single strategy report
report = BacktestReport(backtests=[backtest])
report.show()  # Opens a browser, or renders inline in Jupyter.
```

## Creating Reports

### From a Backtest Object

`run_backtest()` returns a `BacktestIndex`. Load the selected bundle before
passing it to `BacktestReport`:

```python
from investing_algorithm_framework import Study, Universe, BacktestWindow

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=backtest_range)],
)

results = app.run_backtest(strategy=strategy, study=study)
backtest = next(results.iter_backtests())

report = BacktestReport(backtest)
report.show(browser=True)
```

`BacktestReport(backtest)` remains supported for compatibility. New code should
prefer the explicit `backtests=[...]` form.

### From Multiple Backtests

Compare strategies side by side in a single dashboard:

```python
results = app.run_backtests(strategies=strategies, study=study)
selected = results.filter(
    lambda row: row["summary.sharpe_ratio"] > 1.0
)
backtests = selected.load_backtests(workers=1)

report = BacktestReport(backtests=backtests)
report.show()
```

Filtering the lightweight index before loading bundles keeps report generation
bounded to the strategies you actually want to compare.

This generates a multi-strategy comparison dashboard with:

- sortable performance and trading-activity tables;
- normalized equity and drawdown overlays;
- return scenarios, distributions, rolling Sharpe, and correlations;
- per-strategy runs, monthly and yearly returns, trades, orders, and positions;
- a window selector for comparing equivalent historical periods.

### Select a study

By default, the report expands every populated `(study, engine)` pair into a
separate dashboard entry. This lets a single `.obtf` bundle compare in-sample
and out-of-sample studies or vector and event evidence side by side.

Scope an in-memory report to one named study when needed:

```python
report = BacktestReport(
    backtests=results.load_backtests(workers=1),
    study="walk_forward_validation",
)
```

### From Saved Backtests on Disk

Load previously saved backtests from a directory:

```python
report = BacktestReport.open(directory_path="./my_backtests")
report.show()
```

The `open()` method recursively finds supported saved backtests, including
`.obtf` bundle files, and loads them into one report.

:::tip Open Backtest Format
Backtests are saved by default as `.obtf` bundles. A bundle preserves studies,
universes, windows, engine results, orders, trades, metrics, and lineage needed
by reports and downstream analysis.

For larger selected sets, opt into parallel loading:

```python
report = BacktestReport.open(directory_path="./my_backtests", workers=4)
```
:::

You can also combine disk and in-memory backtests:

```python
report = BacktestReport.open(
    backtests=[my_new_backtest],
    directory_path="./saved_backtests"
)
report.show()
```

## Recalculating Metrics

When metric calculations are updated in a newer framework version, previously saved backtests may have stale metrics. Use `recalculate_backtests_in_directory` to recompute all per-run and summary metrics from the raw portfolio snapshots and trades — **directly on disk**, without ever loading the full set of backtests into memory:

```python
from investing_algorithm_framework import recalculate_backtests_in_directory

# Rewrites every bundle in ./my_backtests in place
recalculate_backtests_in_directory("./my_backtests")
```

Each backtest is loaded, recalculated, and written back **inside a worker process**, so the parent process's memory footprint stays flat regardless of how many backtests are processed. This is the recommended approach for any non-trivial batch (hundreds to thousands of backtests with portfolio snapshots and trades can otherwise consume tens of GB).

Write to a different directory instead of in place:

```python
recalculate_backtests_in_directory(
    src_dir="./my_backtests",
    dst_dir="./my_backtests_v2",
)
```

Use a custom risk-free rate (otherwise each backtest's stored rate is used):

```python
recalculate_backtests_in_directory("./my_backtests", risk_free_rate=0.04)
```

Limit which metrics are recomputed, or tune parallelism:

```python
recalculate_backtests_in_directory(
    "./my_backtests",
    metrics=["cagr", "sharpe_ratio", "max_drawdown", "win_rate"],
    workers=4,
    show_progress=True,
)
```

For each backtest, the function:
1. Recomputes per-run `BacktestMetrics` from raw `portfolio_snapshots` and `trades`
2. Regenerates `BacktestSummaryMetrics` by aggregating the updated per-run metrics
3. Writes the updated bundle back to disk and (by default) refreshes `index.parquet`

:::warning Deprecated: `recalculate_backtests(List[Backtest])`
The in-memory variant `recalculate_backtests(backtests)` is **deprecated since 8.7.2** and will be removed in a future major release. Holding many backtests in the parent process is memory-unsafe — each `Backtest` carries portfolio snapshots, trades and timeseries, so a list of a few thousand backtests can easily consume tens of GB before any work starts. Use `recalculate_backtests_in_directory(src_dir, ...)` instead.
:::

## Saving Reports

Save the report as a standalone HTML file you can share or open later:

```python
report = BacktestReport(backtests=[backtest_a, backtest_b])
report.save("strategy_comparison.html")
```

The output is a single `.html` file with the report CSS, JavaScript, and
backtest data embedded. Core analysis works without a report server. Connecting
to Finterion from its optional marketplace panel requires internet access and
loads the Finterion authentication SDK.

## Viewing in Jupyter

`show()` automatically detects Jupyter notebooks and renders the dashboard inline:

```python
# In a Jupyter notebook cell:
report = BacktestReport.open(directory_path="./backtests")
report.show()           # Renders inline in the notebook
report.show(browser=True)  # Also opens in the browser
```

## Dashboard Features

The layout adapts to the number of populated study-engine views.

### Single view

A report containing one study and engine uses four tabs:

| Tab | Contents |
| --- | --- |
| **Overview** | Headline KPIs, equity and drawdown, window coverage, and run selection. |
| **Performance** | Monthly/yearly returns, return distribution, rolling Sharpe, and calendar analysis. |
| **Trades** | Trades, orders, positions, activity, and signal rejection details. |
| **Risk** | Drawdown, exposure, risk metrics, and time-weighted views where available. |

### Comparison view

Loading multiple algorithms, studies, or engines enables ranking and comparison.
The overview includes best-result KPIs, a strategy-by-window coverage matrix,
sortable key-metric and trading-activity tables, return scenarios, and
normalized equity and drawdown overlays.

Each study-engine entry has **Summary**, **Runs**, and **Performance** tabs. The
comparison page adds:

- strategy selection and challenger highlighting;
- CAGR, Sharpe, Sortino, Calmar, drawdown, win-rate, and profit-factor charts;
- monthly returns or cumulative growth as rows or a heatmap;
- yearly returns, distributions, rolling Sharpe, and correlation matrices;
- window-specific comparisons through the sticky window selector.

### Report Builder and research notes

The Report Builder stores analysis notes in the report, associates strategies
with keep/maybe/reject decisions, captures chart snapshots, and exports research
context. The MCP setup panel shows how compatible AI clients can query the same
backtest directory for deeper analysis.

### Appearance and marketplace

The dashboard supports light and dark themes and responsive navigation. Its
Finterion panel explains publishing and can connect to the marketplace when the
viewer is online.

## Example: Full Workflow

```python
from investing_algorithm_framework import BacktestRunConfiguration
from datetime import datetime, timezone
from investing_algorithm_framework import (
    create_app, BacktestDateRange, BacktestReport, Study, Universe,
    BacktestWindow, recalculate_backtests_in_directory,
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

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
)

app.run_backtests(
    strategies=my_strategies,
    study=study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./backtests",
    ),
)

# Optional: recalculate metrics with updated calculations (memory-safe, on disk)
recalculate_backtests_in_directory("./backtests", risk_free_rate=0.04)

# Generate and save the comparison report
report = BacktestReport.open(directory_path="./backtests")
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
| `BacktestReport(backtests=[...], study="name")` | Render only one named study from in-memory bundles |
| `report.show(browser=False)` | Display the report. In Jupyter: renders inline. Otherwise: opens browser. Set `browser=True` to force browser. |
| `report.save(path)` | Save the report as a self-contained HTML file |
| `report.pretty_print()` | Print an aggregate summary of rejected signals |

### `recalculate_backtests_in_directory`

Stream-recalculates every backtest bundle on disk inside worker processes. The full `Backtest` never crosses the process boundary, so parent memory stays flat.

| Parameter | Type | Description |
|-----------|------|-------------|
| `src_dir` | `str \| Path` | Directory containing `.obtf` bundles (and/or legacy backtest directories) |
| `dst_dir` | `str \| Path`, optional | Output directory. If `None`, bundles are rewritten in place inside `src_dir` |
| `risk_free_rate` | `float`, optional | Override risk-free rate. If `None`, uses each backtest's stored rate |
| `metrics` | `List[str]`, optional | Specific metrics to compute. If `None`, computes all default metrics |
| `workers` | `int`, optional | Number of parallel worker processes. Defaults to `min(8, cpu_count)`. Pass `1` for serial |
| `show_progress` | `bool` | Display a tqdm progress bar (default `False`) |
| `include_ohlcv` | `bool` | Re-emit attached OHLCV data with the bundle (default `False`) |
| `max_tasks_per_child` | `int`, optional | Recycle each worker after this many tasks so RSS stays bounded (default `16`) |
| `update_index` | `bool` | Rewrite `index.parquet` in the destination directory (default `True`) |
| `study` | `str`, optional | Recompute only runs in the named study |
| `engine` | `str`, optional | Recompute only `"vector"` or `"event"` runs |
| `windows` | `List[BacktestDateRange]`, optional | Recompute only matching date ranges |

**Returns:** `int` — the number of backtests recalculated.

### `recalculate_backtests` *(deprecated)*

:::warning Deprecated since 8.7.2
Use [`recalculate_backtests_in_directory`](#recalculate_backtests_in_directory) instead. This in-memory variant will be removed in a future major release.
:::

| Parameter | Type | Description |
|-----------|------|-------------|
| `backtests` | `List[Backtest]` | The backtests to recalculate (mutated in place and returned) |
| `risk_free_rate` | `float`, optional | Override risk-free rate. If `None`, uses each backtest's stored rate (falls back to `0.0`) |
| `metrics` | `List[str]`, optional | Specific metrics to compute. If `None`, computes all default metrics |

**Returns:** `List[Backtest]` — the same backtest objects with updated metrics.
