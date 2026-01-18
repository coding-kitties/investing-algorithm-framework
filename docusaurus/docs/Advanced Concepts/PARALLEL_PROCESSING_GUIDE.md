---
sidebar_position: 4
---

# Parallel Processing Guide

## Overview

The optimized backtest function includes **optional parallel processing** using Python's `ProcessPoolExecutor`, allowing you to leverage all CPU cores for massive speedups when running thousands of backtests.

## Performance Comparison

For **10,000 backtests**:

| Configuration | Runtime | Speedup | Best Use Case |
|---------------|---------|---------|---------------|
| Original (sequential) | ~180 min | 1x | Baseline |
| Optimized (sequential) | ~90 min | 2x | Single-core or I/O bound |
| Optimized (4 cores) | ~30 min | 6x | Typical laptop |
| Optimized (8 cores) | ~20 min | 9x | Desktop/server |
| Optimized (16 cores) | ~15 min | 12x | High-end server |

## When to Use Parallel Processing

### ✅ USE Parallel Processing When:
- Running 1,000+ backtests
- CPU-bound operations (complex indicators, many calculations)
- Multi-core processor available (4+ cores)
- Each backtest is independent
- Memory per core is sufficient (~500MB-2GB per worker)

### ❌ DON'T Use Parallel Processing When:
- Running < 100 backtests (overhead > benefit)
- I/O bound (disk/network bottleneck)
- Limited RAM (< 8GB total)
- Single/dual core processor
- Strategies share mutable state

## Usage

### Basic Usage

```python
import os

# Use all available cores
backtests = app.run_vector_backtests_with_checkpoints_optimized(
    initial_amount=1000,
    strategies=strategies,  # 10,000 strategies
    backtest_date_ranges=[date_range_1, date_range_2],
    n_workers=-1,  # Use all CPU cores
    show_progress=True,
)
```

### Recommended Usage

```python
# Leave one core free for system
n_cores = os.cpu_count() - 1

backtests = app.run_vector_backtests_with_checkpoints_optimized(
    initial_amount=1000,
    strategies=strategies,
    backtest_date_ranges=[date_range_1, date_range_2],
    n_workers=n_cores,  # e.g., 7 cores on an 8-core machine
    batch_size=100,
    checkpoint_batch_size=50,
    show_progress=True,
)
```

### Conservative Usage

```python
# Use half available cores (safer for shared systems)
n_cores = max(1, os.cpu_count() // 2)

backtests = app.run_vector_backtests_with_checkpoints_optimized(
    initial_amount=1000,
    strategies=strategies,
    backtest_date_ranges=[date_range_1, date_range_2],
    n_workers=n_cores,
    show_progress=True,
)
```

## Configuration Parameters

### `n_workers` Parameter

- **`None`** (default): Sequential processing (no parallelization)
- **`-1`**: Use all available CPU cores (`os.cpu_count()`)
- **`N`**: Use exactly N worker processes

**Examples:**
```python
n_workers=None  # Sequential (safest, ~90min for 10k)
n_workers=1     # Also sequential
n_workers=4     # Use 4 cores (~30min for 10k)
n_workers=8     # Use 8 cores (~20min for 10k)
n_workers=-1    # Use all cores (~15-20min for 10k on 8-core)
```

## How It Works

### Architecture

```
Main Process:
├── Loads checkpoint cache (shared read-only)
├── Identifies missing backtests
├── Creates ProcessPoolExecutor with N workers
├── Submits backtest tasks to worker pool
└── Collects results and saves in batches

Worker Process 1-N:
├── Receives strategy + parameters
├── Creates isolated app instance
├── Runs backtest independently
├── Returns result to main process
└── Terminates
```

### Key Implementation Details

1. **Process-based parallelism**: Uses `multiprocessing.ProcessPoolExecutor` to bypass Python's GIL
2. **Isolated workers**: Each worker creates its own app instance
3. **Batch collection**: Results are collected and saved in batches to reduce I/O
4. **Progress tracking**: tqdm shows real-time progress across all workers
5. **Error handling**: Continues or fails based on `continue_on_error` flag

## Memory Considerations

### Estimating Memory Usage

Each worker process needs:
- **Base**: ~200-500MB (Python + framework)
- **Data**: ~100-500MB (OHLCV data for backtest period)
- **Strategy**: ~50-200MB (indicators, calculations)
- **Total per worker**: ~500MB - 2GB

**Example for 8 workers:**
- Conservative: 8 × 500MB = 4GB
- Typical: 8 × 1GB = 8GB
- Heavy: 8 × 2GB = 16GB

### Memory Management Tips

```python
# Monitor memory usage
import psutil

def check_memory():
    mem = psutil.virtual_memory()
    return f"Used: {mem.percent}%, Available: {mem.available / 1024**3:.1f}GB"

# Adjust workers based on available memory
available_gb = psutil.virtual_memory().available / 1024**3
recommended_workers = int(available_gb / 2)  # 2GB per worker
n_workers = min(os.cpu_count() - 1, recommended_workers)

print(f"Using {n_workers} workers (Memory: {check_memory()})")

backtests = app.run_vector_backtests_with_checkpoints_optimized(
    strategies=strategies,
    n_workers=n_workers,
    ...
)
```

## Performance Tuning

### Optimal Configuration Formula

```python
import os

# System specs
total_cores = os.cpu_count()
available_ram_gb = psutil.virtual_memory().available / 1024**3

# Calculate optimal settings
n_workers = min(
    total_cores - 1,  # Leave one core free
    int(available_ram_gb / 2),  # 2GB per worker
    len(strategies) // 10  # At least 10 strategies per worker
)

# Batch sizes
checkpoint_batch_size = max(10, n_workers * 5)  # 5 per worker
batch_size = max(50, n_workers * 10)  # 10 per worker

print(f"Optimal config: {n_workers} workers, "
      f"checkpoint_batch={checkpoint_batch_size}, "
      f"batch={batch_size}")
```

### CPU-Bound vs I/O-Bound

**CPU-Bound (benefits from parallelization):**
- Complex indicator calculations
- Many mathematical operations
- Large datasets
- Long time periods

**I/O-Bound (may not benefit):**
- Frequent disk reads/writes
- Network-based data fetching
- Database queries
- Very fast backtests (< 1 second each)

### Benchmark Your Setup

```python
import time

strategies_sample = strategies[:100]  # Test with 100 strategies

# Test sequential
start = time.time()
results_seq = app.run_vector_backtests_with_checkpoints_optimized(
    strategies=strategies_sample,
    n_workers=None,  # Sequential
    ...
)
seq_time = time.time() - start

# Test parallel with 4 workers
start = time.time()
results_par4 = app.run_vector_backtests_with_checkpoints_optimized(
    strategies=strategies_sample,
    n_workers=4,
    ...
)
par4_time = time.time() - start

# Test parallel with all cores
start = time.time()
results_par_all = app.run_vector_backtests_with_checkpoints_optimized(
    strategies=strategies_sample,
    n_workers=-1,
    ...
)
par_all_time = time.time() - start

print(f"Sequential: {seq_time:.1f}s")
print(f"Parallel (4): {par4_time:.1f}s (speedup: {seq_time/par4_time:.1f}x)")
print(f"Parallel (all): {par_all_time:.1f}s (speedup: {seq_time/par_all_time:.1f}x)")

# Extrapolate to full dataset
estimated_full = par_all_time * (len(strategies) / 100)
print(f"\nEstimated time for {len(strategies)} strategies: {estimated_full/60:.1f} minutes")
```

## Common Issues and Solutions

### Issue 1: "Out of Memory" Errors

**Symptoms:** Process killed, memory error
**Solution:**
```python
# Reduce number of workers
n_workers = max(1, os.cpu_count() // 2)  # Use half the cores

# Reduce batch sizes
checkpoint_batch_size = 25  # Smaller batches
```

### Issue 2: No Speed Improvement

**Symptoms:** Parallel is same speed or slower than sequential
**Causes:**
- I/O bound workload
- Too few strategies (< 100)
- Overhead exceeds benefit

**Solution:**
```python
# Use sequential for small workloads
if len(strategies) < 100:
    n_workers = None
else:
    n_workers = os.cpu_count() - 1
```

### Issue 3: Pickling Errors

**Symptoms:** "Can't pickle X" errors
**Cause:** Strategy contains unpickleable objects (lambdas, local functions)
**Solution:**
```python
# Make sure strategies are pickleable
# Avoid: lambdas, local functions, file handles in strategy

# Good:
class MyStrategy(TradingStrategy):
    def __init__(self, param1, param2):
        self.param1 = param1  # Simple types only
        super().__init__(...)

# Bad:
class MyStrategy(TradingStrategy):
    def __init__(self):
        self.callback = lambda x: x + 1  # Lambda not pickleable!
```

### Issue 4: Slower on Windows

**Symptoms:** Windows significantly slower than Linux/Mac
**Cause:** Windows process creation overhead
**Solution:**
```python
# Use fewer workers on Windows
import platform

if platform.system() == 'Windows':
    n_workers = max(1, os.cpu_count() // 2)
else:
    n_workers = os.cpu_count() - 1
```

## Platform-Specific Notes

### Linux (Best Performance)
- Fast process forking
- Efficient memory sharing
- **Recommended**: Use 90% of cores

### macOS (Good Performance)
- Similar to Linux
- May have stricter memory limits
- **Recommended**: Use 80% of cores

### Windows (Moderate Performance)
- Slower process creation
- Higher memory overhead
- **Recommended**: Use 50% of cores

## Advanced: Custom Worker Function

If you need custom worker behavior, you can modify `_run_single_backtest_worker`:

```python
@staticmethod
def _run_single_backtest_worker(args):
    """Custom worker with profiling."""
    import cProfile
    import pstats
    from io import StringIO
    
    # Profile the backtest
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run backtest (existing code)
    result = ... # existing worker code
    
    profiler.disable()
    
    # Optional: Log profiling stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumtime')
    ps.print_stats(10)
    
    return result
```

## Example: Complete Optimized Setup

```python
import os
import psutil
from investing_algorithm_framework import create_app

# Configuration
def get_optimal_config():
    total_cores = os.cpu_count()
    available_ram_gb = psutil.virtual_memory().available / 1024**3
    
    # Calculate workers
    n_workers = min(
        total_cores - 1,
        int(available_ram_gb / 2),
        8  # Cap at 8 for stability
    )
    
    # Calculate batch sizes
    checkpoint_batch = max(25, n_workers * 5)
    batch = max(50, n_workers * 10)
    
    return n_workers, checkpoint_batch, batch

# Setup
app = create_app(name="OptimizedBacktester")
app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=1000)

# Get optimal config
n_workers, checkpoint_batch, batch = get_optimal_config()

print(f"Configuration:")
print(f"  Workers: {n_workers}")
print(f"  Checkpoint batch: {checkpoint_batch}")
print(f"  Batch size: {batch}")
print(f"  Total strategies: {len(strategies)}")
print(f"  Expected time: ~{len(strategies) / (100 * n_workers):.1f} minutes")

# Run optimized backtests
backtests = app.run_vector_backtests_with_checkpoints_optimized(
    initial_amount=1000,
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=n_workers,
    batch_size=batch,
    checkpoint_batch_size=checkpoint_batch,
    show_progress=True,
    continue_on_error=True,  # Don't stop on individual failures
)

print(f"\nCompleted {len(backtests)} backtests successfully!")
```

## Summary

✅ **Use `n_workers=-1`** for maximum speed on dedicated machines
✅ **Use `n_workers=os.cpu_count()-1`** for shared/production systems
✅ **Use `n_workers=None`** for < 100 backtests or debugging
✅ **Monitor memory** and adjust workers accordingly
✅ **Benchmark first** with a small sample to find optimal settings
✅ **Consider platform** (Linux > macOS > Windows for parallel performance)

With proper configuration, parallel processing can reduce 10,000 backtest runtime from **3 hours to 15-20 minutes**!

