---
sidebar_position: 8
---

# Backtesting

Backtesting allows you to test your trading strategies against historical data to evaluate their performance before deploying them in live markets.

## Overview

The framework supports two types of backtesting:

1. **Event-based Backtesting**: Simulates market events tick-by-tick, providing realistic order execution
2. **Vector Backtesting**: High-performance approach that processes data in batches, ideal for testing many strategies

## Quick Start

### Basic Backtest

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
event_backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)

# Run a vector backtest
vector_backtest = app.run_vector_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)
```

## Event-Based Backtesting

Event-based backtesting simulates the market environment by processing each price update sequentially, just like live trading, 
based on the defined strategy interval (e.g., 1-minute, 5-minute bars).

### Running an Event-Based Backtest

```python
backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000,
    risk_free_rate=0.027,  # Optional: for metrics such as Sharpe ratio calculation
)
```

### Multiple Date Ranges

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

## Vector Backtesting

Vector backtesting is significantly faster (10-100x) and is ideal for:
- Testing multiple parameter combinations
- Running backtests across many time periods
- Large-scale strategy optimization

### Running a Vector Backtest

```python
backtest = app.run_vector_backtest(
    backtest_date_range=backtest_range,
    strategy=my_strategy,
    initial_amount=1000,
    market="bitvavo",
    trading_symbol="EUR"
)
```

### Multiple Strategies

Test many strategies simultaneously:

```python
from investing_algorithm_framework import SnapshotInterval

strategies = [
    MyStrategy(rsi_period=10),
    MyStrategy(rsi_period=14),
    MyStrategy(rsi_period=20),
]

backtests = app.run_vector_backtests(
    backtest_date_ranges=[date_range_1, date_range_2],
    strategies=strategies,
    initial_amount=1000,
    snapshot_interval=SnapshotInterval.DAILY,
    market="bitvavo",
    trading_symbol="EUR"
)
```

## Key Differences: Vector vs Event Backtesting

### Signal Timing
- **Vector Backtest**: Signals are executed at the exact timestamp they are generated.
- **Event Backtest**: Signals are executed at the next strategy interval boundary (e.g ., next 5-minute bar).
- This can lead to slight differences in execution prices, especially in volatile markets.

### Stop Loss and Take Profit
- **Vector Backtest**: Does not support stop loss and take profit orders natively due to its batch processing nature.
- **Event Backtest**: Fully supports stop loss and take profit orders as they can be evaluated in real-time.

### Position Sizing
- **Vector Backtest**: Position sizing is calculated based on the portfolio value at the time of signal generation.
- **Event Backtest**: Position sizing is based on the portfolio value at the time of order execution, which may differ from signal generation time.
- This can lead to different position sizes if the portfolio value changes significantly between signal generation and execution.

### Data Provision
The data provision between vector and event backtests is fundamentally different:

| Aspect | Vector Backtest | Event Backtest |
|--------|-----------------|----------------|
| **Data Loading** | All data at once | Window at each step |
| **Signal Computation** | On full history | On window only |
| **Warmup Period** | Included in data | Part of window |
| **Indicator Behavior** | Consistent throughout | Fresh computation each step |

**What this means:**

- **Vector backtest** loads the entire dataset upfront and computes signals on the full history. Indicators like EMA/RSI see all historical data at once.
- **Event backtest** simulates real-time trading by providing only a sliding window of data at each step. Indicators are computed fresh on each window.

With a sufficiently large `warmup_window` (e.g., 800 bars), both approaches should produce identical signals. However, execution timing may still differ slightly since vector backtests execute at the exact signal timestamp while event backtests execute at strategy interval boundaries.

## Analyzing Results

### Backtest Report

Generate a visual report of your backtest:

```python
from investing_algorithm_framework import BacktestReport

report = BacktestReport(backtest)
report.show(browser=True)  # Opens in your default browser
```

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

- Learn about [Vector Backtesting](/docs/Advanced%20Concepts/vector-backtesting) for advanced optimization
- Explore [Performance Optimization](/docs/Advanced%20Concepts/OPTIMIZATION_GUIDE) for large-scale testing
- Check out [Parallel Processing](/docs/Advanced%20Concepts/PARALLEL_PROCESSING_GUIDE) for multi-core utilization

