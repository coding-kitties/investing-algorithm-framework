---
sidebar_position: 2
---

# Vector Backtesting

Vector backtesting is a high-performance backtesting approach that processes market data in a vectorized manner, enabling you to test multiple strategies across multiple time periods efficiently. This guide covers all the advanced features including filtering, checkpointing, parallelization, batching, and storage.

## Table of Contents

- [Overview](#overview)
- [Basic Usage](#basic-usage)
- [Advanced Features](#advanced-features)
  - [Checkpointing](#checkpointing)
  - [Parallelization](#parallelization)
  - [Batching](#batching)
  - [Storage Directory](#storage-directory)
  - [Window Filter Function](#window-filter-function)
  - [Final Filter Function](#final-filter-function)
- [Performance Optimization](#performance-optimization)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

Vector backtesting offers significant performance improvements over event-driven backtesting:

- **Speed**: 10-100x faster than event-driven backtesting
- **Scalability**: Test thousands of strategies efficiently
- **Parallelization**: Utilize multiple CPU cores for massive speedups
- **Checkpointing**: Resume interrupted backtests without losing progress
- **Filtering**: Progressively eliminate underperforming strategies
- **Memory Efficient**: Process strategies in batches to manage memory

### When to Use Vector Backtesting

Use vector backtesting when:
- Testing multiple strategy parameter combinations
- Running backtests across multiple time periods
- Needing to complete backtests quickly
- Working with large strategy sets (100+ strategies)

## Basic Usage

### Single Strategy, Single Date Range

```python
from investing_algorithm_framework import create_app, BacktestDateRange, SnapshotInterval
from datetime import datetime, timezone

app = create_app()

# Define your strategy
strategy = MyTradingStrategy(
    rsi_overbought=70,
    rsi_oversold=30
)

# Define date range
date_range = BacktestDateRange(
    start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
    name="Period 1"
)

# Run backtest
backtest = app.run_vector_backtest(
    strategy=strategy,
    backtest_date_range=date_range,
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR"
)

print(f"Total return: {backtest.backtest_summary.total_growth_percentage}%")
```

### Multiple Strategies, Multiple Date Ranges

```python
# Create strategy grid
strategies = []
for rsi_ob in [70, 80]:
    for rsi_os in [20, 30]:
        strategies.append(MyTradingStrategy(
            rsi_overbought=rsi_ob,
            rsi_oversold=rsi_os
        ))

# Define multiple date ranges
date_ranges = [
    BacktestDateRange(
        start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2021, 12, 31, tzinfo=timezone.utc),
        name="Period 1"
    ),
    BacktestDateRange(
        start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
        name="Period 2"
    )
]

# Run backtests
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR"
)

# Each backtest contains runs for all date ranges
for backtest in backtests:
    print(f"Strategy {backtest.algorithm_id}: {len(backtest.backtest_runs)} runs")
```

## Advanced Features

### Checkpointing

Checkpointing saves completed backtests to disk, allowing you to resume interrupted runs and skip already-completed backtests on subsequent runs.

#### Enabling Checkpoints

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR",
    # Enable checkpointing
    use_checkpoints=True,
    backtest_storage_directory="./backtest_storage"
)
```

#### How It Works

1. **First Run**: All backtests execute and save to storage
```
Running backtests for all date ranges: 100%|██████████| 2/2
Saving backtests: 1000/1000 strategies completed
```

2. **Subsequent Run**: Checkpoints are loaded, computation skipped
```
Found 1000 checkpointed backtests, running 0 new backtests
Loading backtests: 100%|██████████| 1000/1000 [instant!]
```

3. **Partial Run** (e.g., interrupted): Resumes from where it left off
```
Found 600 checkpointed backtests, running 400 new backtests
Running backtests: 100%|██████████| 400/1000
```

#### Checkpoint File Structure

```
backtest_storage/
├── checkpoints.json              # Tracks completed backtests
├── strategy_A/
│   ├── algorithm_id.json
│   ├── metadata.json
│   └── runs/
│       ├── 20220101_20231231/    # Date range 1
│       └── 20240101_20251231/    # Date range 2
├── strategy_B/
│   └── ...
```

#### Checkpoint Behavior

| `use_checkpoints` | `backtest_storage_directory` | Creates Checkpoints? | Uses Checkpoints? |
|-------------------|------------------------------|---------------------|------------------|
| `False` | `None` | ❌ No | ❌ No |
| `False` | Provided | ✅ **Yes** | ❌ No |
| `True` | `None` | ❌ No | ❌ No |
| `True` | Provided | ✅ Yes | ✅ **Yes** |

**Note**: When `use_checkpoints=False` but `backtest_storage_directory` is provided, checkpoint files are created for future use but not used during the current run. This builds checkpoint infrastructure progressively.

### Parallelization

Parallelization distributes backtests across multiple CPU cores for massive speedups.

#### Enabling Parallel Processing

```python
import os

backtests = app.run_vector_backtests(
    strategies=strategies,  # 1000 strategies
    backtest_date_ranges=date_ranges,
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR",
    use_checkpoints=True,
    backtest_storage_directory="./backtest_storage",
    # Parallel processing configuration
    n_workers=os.cpu_count() - 1,  # Use all but one CPU core
    show_progress=True
)
```

#### Worker Configuration

- **`n_workers=None`**: Sequential processing (no parallelization)
- **`n_workers=-1`**: Use all available CPU cores
- **`n_workers=N`**: Use exactly N worker processes

**Recommendation**: `os.cpu_count() - 1` to leave one core free for system tasks.

#### Performance Comparison

```
Sequential (n_workers=None):
├─> 1000 strategies × 2 date ranges
├─> ~45 minutes on 8-core machine
└─> Memory: ~2GB

Parallel (n_workers=7):
├─> 1000 strategies × 2 date ranges
├─> ~8 minutes on 8-core machine (5.6x speedup!)
└─> Memory: ~8GB (1-2GB per worker)
```

#### How It Works

```
ProcessPoolExecutor with 8 workers:

Core 1: [Worker 1: Strategies 1-125]
Core 2: [Worker 2: Strategies 126-250]
Core 3: [Worker 3: Strategies 251-375]
Core 4: [Worker 4: Strategies 376-500]
Core 5: [Worker 5: Strategies 501-625]
Core 6: [Worker 6: Strategies 626-750]
Core 7: [Worker 7: Strategies 751-875]
Core 8: [Worker 8: Strategies 876-1000]

ALL RUNNING SIMULTANEOUSLY ✅
```

**Note**: Uses `ProcessPoolExecutor` (true multi-core parallelism), not `ThreadPoolExecutor` (which would be limited by Python's GIL).

### Batching

Batching processes strategies in smaller chunks to manage memory usage and enable progressive checkpoint saves.

#### Configuration

```python
backtests = app.run_vector_backtests(
    strategies=strategies,  # 10,000 strategies
    backtest_date_ranges=date_ranges,
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR",
    use_checkpoints=True,
    backtest_storage_directory="./backtest_storage",
    # Batching configuration
    batch_size=100,              # Process 100 strategies at a time
    checkpoint_batch_size=50,    # Save checkpoint every 50 backtests
    show_progress=True
)
```

#### Parameters

**`batch_size`** (default: 100)
- Number of strategies to process before memory cleanup
- Lower = less memory, more frequent cleanup
- Higher = more memory, fewer cleanup cycles
- **Recommendation**: 50-100 for large-scale backtesting

**`checkpoint_batch_size`** (default: 50)
- Number of backtests before batch save to disk
- Lower = more frequent saves, less data loss on interruption
- Higher = fewer disk I/O operations, faster execution
- **Recommendation**: 25-100 depending on backtest complexity

#### Memory Management

```python
# Small datasets (< 100 strategies)
batch_size=100  # Process all at once

# Medium datasets (100-1000 strategies)
batch_size=50   # Balance memory and speed

# Large datasets (1000+ strategies)
batch_size=25   # Conserve memory, frequent checkpoints
```

#### Batching Output

```
Processing 10,000 strategies in 100 batches of ~100 strategies each
Processing strategy batches: 100%|██████████| 100/100 [45:30<00:00, 27.3s/batch]
```

### Storage Directory

The storage directory persists all backtest results to disk, enabling checkpointing, result analysis, and data preservation.

#### Configuration

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR",
    backtest_storage_directory="./my_backtests"  # Can be relative or absolute path
)
```

#### Directory Structure

```
my_backtests/
├── checkpoints.json                    # Checkpoint tracking file
│
├── strategy_abc123/                    # Algorithm ID directory
│   ├── algorithm_id.json              # Strategy identifier
│   ├── metadata.json                  # Strategy metadata
│   └── runs/                          # Backtest runs
│       ├── 20220101_20231231/         # Date range 1 run
│       │   ├── backtest_metrics.json
│       │   ├── orders.json
│       │   ├── portfolio_snapshots.json
│       │   └── trades.json
│       │
│       └── 20240101_20251231/         # Date range 2 run
│           ├── backtest_metrics.json
│           ├── orders.json
│           ├── portfolio_snapshots.json
│           └── trades.json
│
├── strategy_def456/
│   └── ...
```

#### Loading Backtests from Storage

```python
from investing_algorithm_framework.domain import load_backtests_from_directory

# Load all backtests
all_backtests = load_backtests_from_directory(
    directory_path="./my_backtests",
    show_progress=True
)

# Load with filter
profitable_backtests = load_backtests_from_directory(
    directory_path="./my_backtests",
    filter_function=lambda b: b.backtest_summary.total_growth_percentage > 0
)

# Load specific number
top_backtests = load_backtests_from_directory(
    directory_path="./my_backtests",
    number_of_backtests_to_load=10
)
```

#### Storage Benefits

✅ **Persistence**: Results preserved across runs
✅ **Checkpointing**: Resume interrupted backtests
✅ **Analysis**: Review results offline
✅ **Sharing**: Export/import backtest data
✅ **Debugging**: Investigate individual strategy performance

### Window Filter Function

Window filter function progressively eliminates strategies that don't meet criteria after each date range. This is powerful for walk-forward optimization and adaptive strategy selection.

#### Basic Usage

```python
def filter_profitable_strategies(backtests, date_range):
    """
    Keep only strategies with positive returns for the given date range.
    """
    filtered = []
    for backtest in backtests:
        metrics = backtest.get_backtest_metrics(date_range)
        if metrics.total_growth_percentage > 0:
            filtered.append(backtest)
    return filtered

backtests = app.run_vector_backtests(
    strategies=strategies,  # 1000 strategies
    backtest_date_ranges=[period1, period2, period3],
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR",
    window_filter_function=filter_profitable_strategies  # Apply after each period
)
```

#### How It Works

```
Period 1: 2020-2021
├─> Run 1000 strategies
├─> Apply window filter
├─> Keep 300 strategies (700 filtered out)
└─> Remove filtered strategies from active_strategies

Period 2: 2022-2023
├─> Run 300 strategies only (700 skipped!)
├─> Apply window filter
├─> Keep 150 strategies (150 filtered out)
└─> Remove filtered strategies from active_strategies

Period 3: 2024-2025
├─> Run 150 strategies only (850 skipped!)
├─> Apply window filter
└─> Keep 75 final strategies

Final Result: 75 backtests (passed all periods)
```

#### Filter Examples

**Filter by Trade Count**
```python
def has_min_trades(backtests, date_range):
    """Keep strategies with at least 5 closed trades."""
    return [
        b for b in backtests
        if b.get_backtest_metrics(date_range).number_of_trades_closed >= 5
    ]
```

**Filter by Sharpe Ratio**
```python
def high_sharpe(backtests, date_range):
    """Keep strategies with Sharpe ratio > 1.0."""
    return [
        b for b in backtests
        if b.get_backtest_metrics(date_range).sharpe_ratio > 1.0
    ]
```

**Filter by Drawdown**
```python
def low_drawdown(backtests, date_range):
    """Keep strategies with max drawdown < 20%."""
    return [
        b for b in backtests
        if b.get_backtest_metrics(date_range).max_drawdown < 20.0
    ]
```

**Combined Filter**
```python
def robust_strategies(backtests, date_range):
    """Multiple criteria: profitable, active, low risk."""
    filtered = []
    for backtest in backtests:
        metrics = backtest.get_backtest_metrics(date_range)
        
        # Must be profitable
        if metrics.total_growth_percentage <= 0:
            continue
            
        # Must have sufficient trades
        if metrics.number_of_trades_closed < 10:
            continue
            
        # Must have good risk-adjusted returns
        if metrics.sharpe_ratio < 1.5:
            continue
            
        # Must have reasonable drawdown
        if metrics.max_drawdown > 25.0:
            continue
            
        filtered.append(backtest)
    
    return filtered
```

#### Filtered-Out Backtests

When using `backtest_storage_directory`, filtered-out backtests are **marked with metadata** but **preserved in storage**:

```python
# Backtest marked as filtered out
{
    "algorithm_id": "strategy_X",
    "metadata": {
        "filtered_out": True,
        "filtered_out_at_date_range": "Period 1"
    }
}
```

**Benefits**:
- ✅ No recomputation needed on reruns
- ✅ Checkpoints remain valid
- ✅ Can change filter criteria without losing data
- ✅ Can review why strategies were filtered

**Loading Behavior**:
- Filtered-out backtests are excluded from `run_vector_backtests()` results
- But remain in storage for future runs with different filters
- Load manually with `load_backtests_from_directory()` if needed

### Final Filter Function

Final filter function is applied AFTER all date ranges are processed, enabling ranking and selection based on overall performance.

#### Basic Usage

```python
def select_top_performers(backtests):
    """
    Select top 10 strategies by total return.
    """
    # Sort by total return
    sorted_backtests = sorted(
        backtests,
        key=lambda b: b.backtest_summary.total_growth_percentage,
        reverse=True
    )
    
    # Return top 10
    return sorted_backtests[:10]

backtests = app.run_vector_backtests(
    strategies=strategies,  # 1000 strategies
    backtest_date_ranges=[period1, period2, period3],
    initial_amount=1000,
    market="BITVAVO",
    trading_symbol="EUR",
    final_filter_function=select_top_performers  # Apply at the end
)

# Result: 10 best strategies
```

#### Filter Examples

**Select by Risk-Adjusted Returns**
```python
def best_risk_adjusted(backtests):
    """Select top 20 by Sharpe ratio."""
    return sorted(
        backtests,
        key=lambda b: b.backtest_summary.sharpe_ratio or 0,
        reverse=True
    )[:20]
```

**Select by Consistency**
```python
def most_consistent(backtests):
    """Select strategies profitable in ALL periods."""
    consistent = []
    
    for backtest in backtests:
        # Check if profitable in every run
        all_profitable = all(
            run.backtest_metrics.total_growth_percentage > 0
            for run in backtest.backtest_runs
        )
        
        if all_profitable:
            consistent.append(backtest)
    
    return consistent
```

**Select by Multiple Criteria**
```python
def score_and_select(backtests):
    """Score strategies and select top 50."""
    scored = []
    
    for backtest in backtests:
        summary = backtest.backtest_summary
        
        # Calculate composite score
        score = (
            summary.total_growth_percentage * 0.3 +
            summary.sharpe_ratio * 20 * 0.3 +
            (100 - summary.max_drawdown) * 0.2 +
            summary.win_rate * 0.2
        )
        
        scored.append((score, backtest))
    
    # Sort by score and return top 50
    scored.sort(reverse=True)
    return [backtest for score, backtest in scored[:50]]
```

#### Window Filter vs Final Filter

| Feature | Window Filter | Final Filter |
|---------|--------------|--------------|
| **When Applied** | After each date range | After all date ranges |
| **Purpose** | Progressive elimination | Final selection/ranking |
| **Affects Execution** | Yes (skips filtered strategies) | No (all strategies complete) |
| **Best For** | Walk-forward optimization | Top-N selection |
| **Parameters** | `(backtests, date_range)` | `(backtests)` |

**Use Both Together**:
```python
backtests = app.run_vector_backtests(
    strategies=strategies,  # 10,000 strategies
    backtest_date_ranges=[p1, p2, p3, p4],
    # Window filter: Eliminate poor performers progressively
    window_filter_function=lambda b, dr: [
        bt for bt in b
        if bt.get_backtest_metrics(dr).sharpe_ratio > 0.5
    ],
    # Final filter: Select top 100 by return
    final_filter_function=lambda b: sorted(
        b,
        key=lambda bt: bt.backtest_summary.total_growth_percentage,
        reverse=True
    )[:100]
)
# Result: Top 100 strategies that passed all filters
```

## Performance Optimization

### Optimization Guide

For optimal performance with different dataset sizes:

#### Small Datasets (< 100 strategies)

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    # Sequential processing is fine
    n_workers=None,
    # Process all at once
    batch_size=100,
    checkpoint_batch_size=50,
    # Optional storage
    backtest_storage_directory="./storage"
)
```

**Expected Performance**: 1-5 minutes for 2 date ranges

#### Medium Datasets (100-1,000 strategies)

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    # Enable parallelization
    n_workers=os.cpu_count() - 1,
    # Moderate batching
    batch_size=50,
    checkpoint_batch_size=25,
    # Enable checkpointing
    use_checkpoints=True,
    backtest_storage_directory="./storage"
)
```

**Expected Performance**: 5-15 minutes for 2 date ranges

#### Large Datasets (1,000-10,000 strategies)

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    # Maximum parallelization
    n_workers=-1,  # Use all cores
    # Smaller batches for memory management
    batch_size=25,
    checkpoint_batch_size=25,
    # Essential for large datasets
    use_checkpoints=True,
    backtest_storage_directory="./storage",
    # Use window filter to reduce computation
    window_filter_function=eliminate_poor_performers,
    show_progress=True
)
```

**Expected Performance**: 30-90 minutes for 2 date ranges

#### Extra Large Datasets (10,000+ strategies)

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    # Maximum parallelization
    n_workers=-1,
    # Very small batches
    batch_size=10,
    checkpoint_batch_size=10,
    # Critical for resumability
    use_checkpoints=True,
    backtest_storage_directory="./storage",
    # Aggressive filtering
    window_filter_function=strict_filter,
    final_filter_function=top_n_selector,
    show_progress=True
)
```

**Expected Performance**: 2-6 hours for 2 date ranges

### Memory Optimization

```python
# Monitor memory usage
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024 / 1024  # GB

print(f"Memory before: {get_memory_usage():.2f} GB")

backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    # Memory management settings
    batch_size=10,  # Smaller batches = less memory
    n_workers=4,    # Fewer workers = less memory
)

print(f"Memory after: {get_memory_usage():.2f} GB")
```

### Performance Metrics

```python
import time

start = time.time()

backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=os.cpu_count() - 1,
    show_progress=True
)

duration = time.time() - start
strategies_per_second = len(strategies) * len(date_ranges) / duration

print(f"Completed {len(backtests)} backtests in {duration:.2f} seconds")
print(f"Performance: {strategies_per_second:.2f} backtests/second")
```

## Best Practices

### 1. Always Use Storage Directory

```python
# ✅ GOOD: Results preserved, checkpointing enabled
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    backtest_storage_directory="./storage"
)

# ❌ BAD: Results lost if process crashes, no checkpointing
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges
)
```

### 2. Enable Checkpointing for Long Runs

```python
# ✅ GOOD: Can resume if interrupted
backtests = app.run_vector_backtests(
    strategies=strategies,  # 5000 strategies
    backtest_date_ranges=date_ranges,
    use_checkpoints=True,
    backtest_storage_directory="./storage"
)

# ❌ BAD: 2 hours wasted if process crashes
backtests = app.run_vector_backtests(
    strategies=strategies,  # 5000 strategies
    backtest_date_ranges=date_ranges,
    use_checkpoints=False
)
```

### 3. Use Parallel Processing

```python
import os

# ✅ GOOD: 5-8x speedup on multi-core systems
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=os.cpu_count() - 1
)

# ❌ BAD: Single-threaded, slow
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=None
)
```

### 4. Apply Window Filters Early

```python
# ✅ GOOD: Eliminate poor performers early
backtests = app.run_vector_backtests(
    strategies=strategies,  # 10,000 strategies
    backtest_date_ranges=[p1, p2, p3, p4, p5],
    window_filter_function=eliminate_poor_performers  # Reduces computation
)
# Runs: 10,000 → 3,000 → 1,000 → 400 → 150 = much faster!

# ❌ BAD: Run all strategies for all periods
backtests = app.run_vector_backtests(
    strategies=strategies,  # 10,000 strategies
    backtest_date_ranges=[p1, p2, p3, p4, p5]
)
# Runs: 10,000 × 5 = 50,000 backtests!
```

### 5. Show Progress for Long Runs

```python
# ✅ GOOD: See progress and estimate completion time
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    show_progress=True  # Shows progress bars
)

# ❌ BAD: No feedback, can't estimate completion
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    show_progress=False
)
```

### 6. Adjust Batch Sizes for Your Hardware

```python
# ✅ GOOD: Tuned for system resources
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    batch_size=50,  # Adjust based on RAM
    checkpoint_batch_size=25,  # Adjust based on disk speed
)

# ❌ BAD: Default may not be optimal
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges
)
```

### 7. Handle Errors Gracefully

```python
# ✅ GOOD: Continue despite individual strategy errors
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    continue_on_error=True  # Skip failed strategies
)

# ❌ BAD: One error stops entire run
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    continue_on_error=False
)
```

## Examples

### Example 1: Parameter Grid Optimization

```python
from itertools import product

# Create parameter grid
rsi_overbought_values = [70, 75, 80]
rsi_oversold_values = [20, 25, 30]
ema_periods = [50, 100, 150, 200]

strategies = []
for rsi_ob, rsi_os, ema_period in product(
    rsi_overbought_values,
    rsi_oversold_values,
    ema_periods
):
    strategies.append(MyStrategy(
        rsi_overbought=rsi_ob,
        rsi_oversold=rsi_os,
        ema_period=ema_period
    ))

print(f"Testing {len(strategies)} strategy combinations")
# Result: 3 × 3 × 4 = 36 strategies

# Run optimization
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=[
        BacktestDateRange(
            start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
            name="Train"
        )
    ],
    initial_amount=10000,
    market="BITVAVO",
    trading_symbol="EUR",
    n_workers=-1,
    show_progress=True
)

# Find best parameters
best = max(backtests, key=lambda b: b.backtest_summary.sharpe_ratio)
print(f"Best strategy: {best.algorithm_id}")
print(f"Sharpe ratio: {best.backtest_summary.sharpe_ratio:.2f}")
```

### Example 2: Walk-Forward Optimization

```python
# Define periods
periods = [
    BacktestDateRange(
        start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2020, 12, 31, tzinfo=timezone.utc),
        name="2020"
    ),
    BacktestDateRange(
        start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2021, 12, 31, tzinfo=timezone.utc),
        name="2021"
    ),
    BacktestDateRange(
        start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2022, 12, 31, tzinfo=timezone.utc),
        name="2022"
    ),
    BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
        name="2023"
    )
]

# Filter: Keep only profitable strategies
def keep_profitable(backtests, date_range):
    return [
        b for b in backtests
        if b.get_backtest_metrics(date_range).total_growth_percentage > 0
    ]

# Run walk-forward backtest
backtests = app.run_vector_backtests(
    strategies=strategies,  # 1000 strategies
    backtest_date_ranges=periods,
    initial_amount=10000,
    market="BITVAVO",
    trading_symbol="EUR",
    window_filter_function=keep_profitable,
    use_checkpoints=True,
    backtest_storage_directory="./walk_forward",
    n_workers=-1,
    show_progress=True
)

print(f"Strategies profitable in all periods: {len(backtests)}")

# Analyze consistency
for backtest in backtests:
    yearly_returns = [
        run.backtest_metrics.total_growth_percentage
        for run in backtest.backtest_runs
    ]
    print(f"Strategy {backtest.algorithm_id}: {yearly_returns}")
```

### Example 3: Large-Scale Optimization with Ranking

```python
import os

# Generate large strategy set
strategies = generate_strategies(count=10000)

# Define filter functions
def min_performance(backtests, date_range):
    """Window filter: Minimum performance threshold."""
    return [
        b for b in backtests
        if (b.get_backtest_metrics(date_range).sharpe_ratio > 0.5 and
            b.get_backtest_metrics(date_range).number_of_trades_closed >= 10)
    ]

def top_100(backtests):
    """Final filter: Select top 100 by score."""
    scored = []
    for b in backtests:
        score = (
            b.backtest_summary.sharpe_ratio * 0.5 +
            b.backtest_summary.total_growth_percentage * 0.3 +
            (100 - b.backtest_summary.max_drawdown) * 0.2
        )
        scored.append((score, b))
    
    scored.sort(reverse=True)
    return [b for score, b in scored[:100]]

# Run optimization
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=[
        BacktestDateRange(
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2021, 12, 31, tzinfo=timezone.utc),
            name="Train 1"
        ),
        BacktestDateRange(
            start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
            name="Train 2"
        ),
        BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
            name="Validation"
        )
    ],
    initial_amount=10000,
    market="BITVAVO",
    trading_symbol="EUR",
    # Progressive filtering
    window_filter_function=min_performance,
    final_filter_function=top_100,
    # Performance optimization
    n_workers=os.cpu_count() - 1,
    batch_size=25,
    checkpoint_batch_size=25,
    use_checkpoints=True,
    backtest_storage_directory="./optimization",
    show_progress=True
)

print(f"Top 100 strategies identified from {len(strategies)} candidates")

# Save results
import pandas as pd
results = []
for b in backtests:
    results.append({
        'algorithm_id': b.algorithm_id,
        'total_return': b.backtest_summary.total_growth_percentage,
        'sharpe_ratio': b.backtest_summary.sharpe_ratio,
        'max_drawdown': b.backtest_summary.max_drawdown,
        'win_rate': b.backtest_summary.win_rate
    })

df = pd.DataFrame(results)
df.to_csv('top_100_strategies.csv', index=False)
print("Results saved to top_100_strategies.csv")
```

### Example 4: Resuming Interrupted Backtest

```python
import os

# First run (may be interrupted)
try:
    backtests = app.run_vector_backtests(
        strategies=strategies,  # 5000 strategies
        backtest_date_ranges=date_ranges,
        initial_amount=10000,
        market="BITVAVO",
        trading_symbol="EUR",
        use_checkpoints=True,
        backtest_storage_directory="./checkpoint_demo",
        n_workers=-1,
        show_progress=True
    )
except KeyboardInterrupt:
    print("Interrupted! Partial results saved.")

# Second run - resumes from checkpoint
print("Resuming from checkpoint...")
backtests = app.run_vector_backtests(
    strategies=strategies,  # Same strategies
    backtest_date_ranges=date_ranges,
    initial_amount=10000,
    market="BITVAVO",
    trading_symbol="EUR",
    use_checkpoints=True,
    backtest_storage_directory="./checkpoint_demo",  # Same directory
    n_workers=-1,
    show_progress=True
)

# Output:
# Found 3000 checkpointed backtests, running 2000 new backtests
# Only remaining strategies are computed!
```

## Troubleshooting

### Issue: Out of Memory

**Symptoms**: Process killed, `MemoryError`, system freezes

**Solutions**:
```python
# Reduce batch size
batch_size=10  # Instead of 100

# Reduce number of workers
n_workers=2  # Instead of -1

# Use window filter to eliminate strategies early
window_filter_function=aggressive_filter
```

### Issue: Slow Performance

**Symptoms**: Backtests take too long

**Solutions**:
```python
# Enable parallelization
n_workers=-1

# Use window filter
window_filter_function=eliminate_poor_performers

# Reduce date ranges
# Instead of 10 periods, use 3-5 key periods

# Increase batch size (if memory allows)
batch_size=100
```

### Issue: Checkpoint Not Working

**Symptoms**: Strategies rerun despite checkpoints

**Solutions**:
```python
# Ensure use_checkpoints=True
use_checkpoints=True

# Ensure storage directory is provided
backtest_storage_directory="./storage"

# Check that strategy algorithm_ids are consistent
# (changing strategy parameters changes algorithm_id)

# Don't delete the storage directory between runs
```

### Issue: Filtered Backtests Still Present

**Symptoms**: Filtered-out strategies in results

**Solutions**:
This is expected behavior! Filtered backtests are marked with metadata but preserved in storage.

```python
# They're excluded from results automatically
backtests = app.run_vector_backtests(...)
# backtests will not include filtered-out strategies

# But they remain in storage for future runs
all_backtests = load_backtests_from_directory("./storage")
# This loads ALL backtests including filtered ones

# To exclude filtered backtests:
active_backtests = [
    b for b in all_backtests
    if not (b.metadata and b.metadata.get('filtered_out', False))
]
```

## Summary

Vector backtesting provides powerful tools for large-scale strategy optimization:

- ⚡ **Speed**: 10-100x faster than event-driven backtesting
- 🔄 **Checkpointing**: Resume interrupted runs, avoid recomputation
- 🚀 **Parallelization**: Utilize multiple CPU cores for massive speedups
- 📦 **Batching**: Manage memory efficiently for large strategy sets
- 💾 **Storage**: Persist results for analysis and resumability
- 🎯 **Filtering**: Progressively eliminate poor performers
- 🎲 **Flexibility**: Test thousands of parameter combinations

For maximum performance:
1. Use `n_workers=-1` for parallelization
2. Enable `use_checkpoints=True` with storage directory
3. Apply `window_filter_function` for progressive elimination
4. Adjust `batch_size` based on your RAM
5. Use `show_progress=True` to monitor execution

Happy backtesting! 🎉

