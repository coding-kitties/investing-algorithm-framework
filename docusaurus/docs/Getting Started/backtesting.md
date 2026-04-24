---
sidebar_position: 8
---

# Event-Driven Backtesting

Event-driven backtesting simulates the market environment by processing each price update sequentially, just like live trading. It provides realistic order execution with full support for stop losses, take profits, and position sizing.

## Quick Start

```python
from investing_algorithm_framework import create_app, BacktestDateRange
from datetime import datetime, timezone

app = create_app()
app.add_strategy(MyStrategy())
app.add_market(market="bitvavo", trading_symbol="EUR")

# Define the backtest period
backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

# Run an event backtest
backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)
```

## Running an Event-Based Backtest

```python
backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000,
    risk_free_rate=0.027,  # Optional: for metrics such as Sharpe ratio calculation
)
```

## Multiple Date Ranges

Test your strategy across different market conditions:

```python
date_ranges = [
    BacktestDateRange(
        start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2022, 12, 31, tzinfo=timezone.utc),
        name="Bear Market 2022"
    ),
    BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
        name="Recovery 2023"
    ),
]

backtests = app.run_backtests(
    backtest_date_ranges=date_ranges,
    ... # other params
)
```

## Event-Driven vs Vector Backtesting

The framework supports two backtesting modes. This page covers event-driven backtesting. For vector backtesting, see [Vector Backtesting](vector-backtesting).

| Aspect | Event-Driven | Vector |
|--------|-------------|--------|
| **Speed** | Slower, realistic simulation | 10-100x faster |
| **Stop Loss / Take Profit** | Fully supported | Not supported |
| **Signal Timing** | Executes at next strategy interval | Executes at exact signal timestamp |
| **Position Sizing** | Based on portfolio at execution time | Based on portfolio at signal time |
| **Data Loading** | Sliding window at each step | All data loaded at once |
| **Best For** | Final validation, realistic results | Fast prototyping, parameter sweeps |

## Analyzing Results

### Backtest Report

Generate a visual report of your backtest:

```python
from investing_algorithm_framework import BacktestReport

# Single strategy
report = BacktestReport(backtest)
report.show(browser=True)  # Opens in your default browser

# Multi-strategy comparison
report = BacktestReport(backtests=[backtest_a, backtest_b])
report.show()

# Load from saved backtests on disk
report = BacktestReport.open(directory_path="./my_backtests")
report.show()

# Save as a self-contained HTML file
report.save("comparison_report.html")
```

See [Backtest Reports](/docs/Getting%20Started/backtest-reports) for full documentation on the dashboard features, compare mode, and API reference.

### Accessing Metrics

```python
# Get performance metrics
metrics = backtest.get_backtest_metrics()
print(f"Total Return: {metrics.total_return}%")
print(f"Sharpe Ratio: {metrics.sharpe_ratio}")
print(f"Max Drawdown: {metrics.max_drawdown}%")
print(f"Total Trades: {metrics.number_of_trades_closed}")
```

### Accessing Trades

```python
for run in backtest.get_all_backtest_runs():
    trades = run.trades
    for trade in trades:
        print(f"Symbol: {trade.symbol}")
        print(f"Entry: {trade.entry_price}")
        print(f"Exit: {trade.exit_price}")
        print(f"Return: {trade.return_percentage}%")
```

## Saving and Loading Backtests

### Save to Directory

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    backtest_storage_directory="./my_backtests",
    initial_amount=1000
)
```

### Load from Directory

```python
from investing_algorithm_framework import load_backtests_from_directory

backtests = load_backtests_from_directory("./my_backtests")
```

## Advanced Features

### Checkpointing

Resume interrupted backtests:

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    backtest_storage_directory="./my_backtests",
    use_checkpoints=True,  # Resume from last checkpoint
    initial_amount=1000
)
```

### Filtering Strategies

Filter out underperforming strategies during backtesting:

```python
def window_filter(backtest_run):
    """Filter after each date range"""
    return backtest_run.backtest_metrics.total_return > 0

def final_filter(backtest):
    """Filter at the end"""
    return backtest.backtest_summary.sharpe_ratio > 1.0

backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    window_filter_function=window_filter,
    final_filter_function=final_filter,
    initial_amount=1000
)
```

### Parallel Processing

Utilize multiple CPU cores for faster backtesting:

```python
import os

backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=os.cpu_count() - 1,  # Use all cores except one
    initial_amount=1000
)
```

## Best Practices

1. **Use representative date ranges**: Include bull markets, bear markets, and sideways periods
2. **Avoid overfitting**: Don't optimize too heavily on historical data
3. **Account for costs**: Consider trading fees and slippage in your strategy
4. **Use checkpointing**: For long-running backtests, enable checkpoints to avoid losing progress
5. **Start with event-based**: Use event-based backtesting for realistic simulation, then scale with vector backtesting

## Next Steps

- Learn about [Vector Backtesting](vector-backtesting) for fast parameter sweeps and optimization
- Explore [Backtest Reports](/docs/Getting%20Started/backtest-reports) for the interactive dashboard
- Check out [Performance Optimization](/docs/Advanced%20Concepts/OPTIMIZATION_GUIDE) for large-scale testing
