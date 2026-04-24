---
sidebar_position: 9
---

# Vector Backtesting

Vector backtesting is a high-performance backtesting approach that processes market data in batches rather than tick-by-tick. It is 10-100x faster than event-driven backtesting, making it ideal for testing many strategy variants and parameter combinations.

## When to Use Vector Backtesting

- Testing multiple parameter combinations (RSI period, MA length, etc.)
- Running backtests across many time periods
- Large-scale strategy optimization (100+ strategies)
- Fast prototyping and signal research

> For realistic simulation with stop losses and take profits, use [Event-Driven Backtesting](backtesting) instead.

## Quick Start

### Single Strategy

```python
from investing_algorithm_framework import create_app, BacktestDateRange, SnapshotInterval
from datetime import datetime, timezone

app = create_app()

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

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

## Saving and Loading

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

## Checkpointing

Resume interrupted backtests without losing progress:

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    backtest_storage_directory="./my_backtests",
    use_checkpoints=True,
    initial_amount=1000
)
```

## Filtering Strategies

Progressively eliminate underperforming strategies during backtesting:

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

## Parallel Processing

Utilize multiple CPU cores for faster backtesting:

```python
import os

backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=os.cpu_count() - 1,
    initial_amount=1000
)
```

## Differences from Event-Driven Backtesting

| Aspect | Vector | Event-Driven |
|--------|--------|-------------|
| **Speed** | 10-100x faster | Slower, realistic |
| **Stop Loss / Take Profit** | Not supported | Fully supported |
| **Signal Timing** | Executes at exact signal timestamp | Executes at next interval boundary |
| **Data Loading** | All data loaded at once | Sliding window at each step |
| **Best For** | Fast prototyping, parameter sweeps | Final validation, realistic results |

With a sufficiently large `warmup_window` (e.g., 800 bars), both approaches should produce identical signals. Execution timing may differ slightly since vector backtests execute at the exact signal timestamp while event backtests execute at strategy interval boundaries.

## Next Steps

- See the [Advanced Vector Backtesting](/docs/Advanced%20Concepts/vector-backtesting) guide for batching, storage, and advanced filtering
- Explore [Performance Optimization](/docs/Advanced%20Concepts/OPTIMIZATION_GUIDE) for large-scale testing
- Check out [Parallel Processing](/docs/Advanced%20Concepts/PARALLEL_PROCESSING_GUIDE) for multi-core utilization
- Generate [Backtest Reports](backtest-reports) to compare your strategies
