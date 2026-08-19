---
sidebar_position: 10
---

# Vector Backtesting

Vector backtesting is a high-performance backtesting approach that processes market data in batches rather than tick-by-tick. It is 10-100x faster than event-driven backtesting, making it ideal for testing many strategy variants and parameter combinations.

## When to Use Vector Backtesting

- Testing multiple parameter combinations (RSI period, MA length, etc.)
- Running backtests across many time periods
- Large-scale strategy optimization (100+ strategies)
- Fast prototyping and signal research

> For realistic simulation with stop losses and take profits, use [Event-Driven Backtesting](event-backtesting) instead. For a high-level comparison of backtesting modes, see the [Backtesting overview](backtesting).

## Quick Start

### Single Strategy

```python
from investing_algorithm_framework import (
    create_app, BacktestDateRange, SnapshotInterval, Study, Universe,
    BacktestWindow, BacktestEngine,
)
from datetime import datetime, timezone

app = create_app()

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=backtest_range)],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtest(
    strategy=my_strategy,
    study=study,
)
backtest = backtests[0]
```

### Multiple Strategies

Test many strategies simultaneously:

```python
strategies = [
    MyStrategy(rsi_period=10),
    MyStrategy(rsi_period=14),
    MyStrategy(rsi_period=20),
]

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[
        BacktestWindow(train_range=date_range_1),
        BacktestWindow(train_range=date_range_2),
    ],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    snapshot_interval=SnapshotInterval.DAILY,
    study=study,
)
```

## Saving and Loading

### Save to Directory

```python
study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    backtest_storage_directory="./my_backtests",
    study=study,
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
study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    backtest_storage_directory="./my_backtests",
    use_checkpoints=True,
    study=study,
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

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    window_filter_function=window_filter,
    final_filter_function=final_filter,
    study=study,
)
```

## Parallel Processing

Utilize multiple CPU cores for faster backtesting:

```python
import os

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    n_workers=os.cpu_count() - 1,
    study=study,
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
