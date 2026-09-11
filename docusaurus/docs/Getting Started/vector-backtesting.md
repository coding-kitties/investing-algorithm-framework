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
    BacktestWindow, BacktestEngine, BacktestRunConfiguration,
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
from investing_algorithm_framework import BacktestRunConfiguration
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
    study=study,
    run_configuration=BacktestRunConfiguration(
        snapshot_interval=SnapshotInterval.DAILY,
    ),
)
```

## Saving and Loading

### Save to Directory

```python
from investing_algorithm_framework import BacktestRunConfiguration
study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    study=study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./my_backtests",
    ),
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
    study=study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./my_backtests",
        n_workers=8,
        memory_budget_mb=16_384,
        min_available_memory_mb=4_096,
    ),
)
```

`BacktestRunConfiguration` enables checkpoints, progress output and
continue-on-error by default. Window summaries are always current. Use
`BacktestRunConfiguration.from_env()` to read the same settings from
`IAF_BACKTEST_*` environment variables.

| Environment variable | Field |
| --- | --- |
| `IAF_BACKTEST_CONTINUE_ON_ERROR` | `continue_on_error` |
| `IAF_BACKTEST_USE_CHECKPOINTS` | `use_checkpoints` |
| `IAF_BACKTEST_STORAGE_DIRECTORY` | `backtest_storage_directory` |
| `IAF_BACKTEST_SHOW_PROGRESS` | `show_progress` |
| `IAF_BACKTEST_N_WORKERS` | `n_workers` |
| `IAF_BACKTEST_MEMORY_BUDGET_MB` | `memory_budget_mb` |
| `IAF_BACKTEST_MIN_AVAILABLE_MEMORY_MB` | `min_available_memory_mb` |
| `IAF_BACKTEST_SNAPSHOT_INTERVAL` | `snapshot_interval` (`DAILY` or `STRATEGY_ITERATION`) |
| `IAF_BACKTEST_SKIP_DATA_SOURCES_INITIALIZATION` | `skip_data_sources_initialization` |
| `IAF_BACKTEST_DYNAMIC_POSITION_SIZING` | `dynamic_position_sizing` |
| `IAF_BACKTEST_FILL_MISSING_DATA` | `fill_missing_data` |
| `IAF_BACKTEST_MAX_TASKS_PER_CHILD` | `max_tasks_per_child` (`None` disables recycling) |

## Filtering Strategies

Progressively eliminate underperforming strategies during backtesting:

```python
def window_filter(index, date_range):
    """Keep algorithms with positive cumulative returns so far."""
    return index.filter(lambda row: row["summary.total_return"] > 0)

def final_filter(index):
    """Select completed results."""
    return index.filter(lambda row: row["summary.sharpe_ratio"] > 1.0)

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    window_metrics_filter_function=window_filter,
    final_metrics_filter_function=final_filter,
    study=study,
)
```

## Parallel Processing

Utilize multiple CPU cores for faster backtesting:

```python
from investing_algorithm_framework import BacktestRunConfiguration
import os

study = Study(
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=dr) for dr in date_ranges],
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtests(
    strategies=strategies,
    study=study,
    run_configuration=BacktestRunConfiguration(
        n_workers=os.cpu_count() - 1,
    ),
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
