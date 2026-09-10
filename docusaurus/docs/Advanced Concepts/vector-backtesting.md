---
sidebar_position: 2
---

# Vector Backtesting

Use the vector engine to screen strategy parameters quickly, then validate
survivors with the event-driven engine. Both engines support disk-backed
results, progressive pruning, checkpoints, and bounded parallel workers.

## Basic Usage

Both `app.run_backtest()` and `app.run_backtests()` always return a
`BacktestIndex`, including single-strategy and event-driven runs. Full
backtests are saved as `.obtf` bundles rather than accumulated in a list.

```python
from datetime import datetime, timezone
from investing_algorithm_framework import (
    BacktestDateRange, BacktestEngine, BacktestWindow, Study, Universe,
)

study = Study(
    name="parameter_sweep",
    universe=Universe(
        market="BITVAVO", trading_symbol="EUR", symbols=["BTC"],
    ),
    initial_capital=1000,
    engines=[BacktestEngine.VECTOR],
    backtest_windows=[BacktestWindow(
        train_range=BacktestDateRange(
            start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )],
)

results = app.run_backtest(strategies=strategies, study=study)
print(results.df)
print(results.directory)
print(results.df["algorithm_id"].nunique())
```

The index can have pooled and per-universe rows for the same algorithm.
Consequently, `len(results)` is a row count, not necessarily a strategy count.
Full results are loaded explicitly:

```python
# A single selected bundle:
backtest = next(results.iter_backtests())

# Stream larger selections; do not accumulate the objects in a list.
for backtest in results.iter_backtests():
    print(backtest.algorithm_id)

# Deliberately materialize a small selection:
backtests = results.load_backtests(workers=1)
```

`iter_backtests()` loads sequentially, deduplicates bundle paths, and propagates
loading errors. `load_backtests()` also deduplicates paths, but retains the
whole selection in memory.

Loaded runs use the bundle representation of raw signals: sparse ISO timestamp
lists per symbol/side, rather than the vector engine's temporary boolean Series.
Use `pd.to_datetime(run.signals[symbol]["buy"])` for the active signal dates.

:::warning Vector execution is not an order-book simulation
The vector engine evaluates `generate_signal_series()` against price series.
Use event-driven backtesting to validate realistic order execution, limit and
stop orders, partial fills, and blotter behavior. See [Orders](../Getting%20Started/orders).
:::

## Storage Directory

If `backtest_storage_directory` is omitted, the framework creates a unique,
**persistent** directory under `RESOURCE_DIRECTORY/backtests/`. It is not
deleted when the call finishes. The absolute path is available as
`results.directory` and is printed when progress is enabled.

Supply a directory explicitly to reuse results across calls:

```python
results = app.run_backtest(
    strategies=strategies,
    study=study,
    backtest_storage_directory="./backtest_storage",
    use_checkpoints=True,
)
```

The directory contains one `<algorithm_id>.obtf` bundle per algorithm,
`checkpoints.json`, session metadata, and `backtest_session_index.parquet`.
Completed windows and other studies/engines are merged into existing bundles.
Pruning removes algorithms from the returned session index, not their
completed bundles from disk.

### Reopening a Sweep

```python
from investing_algorithm_framework import BacktestIndex

results = BacktestIndex.open(
    "./backtest_storage",
    filename="backtest_session_index.parquet",
)
```

The session index describes this sweep's survivors. It is separate from the
global `index.parquet`; `BacktestIndex.open(directory)` without a filename
still opens that global index.

## Checkpointing

Each completed result is saved and checkpointed by the coordinator. Set
`use_checkpoints=True` to skip matching results on subsequent calls. To resume
an automatically located run, reuse its `results.directory` explicitly.

Checkpoints fingerprint strategy code, parameters, data sources, and date
ranges. Changing those inputs causes stale entries to rerun. Framework event
counters and cached signals are not strategy parameters; executor
configuration is fingerprinted without process-specific object addresses.
Legacy checkpoint entries without hashes still match by algorithm ID.

Checkpoint loading processes full bundles one at a time. Window summaries are
restricted to windows evaluated so far, even when a saved bundle already
contains later windows. Resume is bounded-memory, not an instantaneous
metadata-only operation.

With `continue_on_error=True`, individual strategy errors are logged and skipped.
Resource errors and persistence failures still propagate. Completed durable
checkpoints remain available after interruption.

## Parallelization

Set `n_workers` for either engine:

```python
results = app.run_backtest(
    strategies=strategies, study=study,
    n_workers=6,
    max_tasks_per_child=16,
    backtest_storage_directory="./backtest_storage",
    use_checkpoints=True,
)
```

- `None` or `0`: sequential execution.
- Positive integer: upper bound on spawned worker processes.
- `-1`: automatic cap of `min(cpu_count - 1, 8)`, with at least one worker.
- One algorithm/strategy and one window form a task.
- The scheduler consumes results before admitting replacement work.
- Pool generations admit at most `max_tasks_per_child` tasks in total. This
  conservative bound works across supported Python versions and can recycle
  an individual worker sooner than that number. `None` disables recycling.
- Numerical-library thread limits are installed before child processes import
  their libraries, avoiding a CPU-sized thread pool inside each worker.

Worker inputs must be spawn-picklable. Put strategy, task, and hook classes in
importable modules, especially when launching from notebooks. In scripts,
put execution behind `if __name__ == "__main__":`.

### Parallel Event Backtests

```python
event_study = study.copy_definition()
event_study.engines = [BacktestEngine.EVENT_DRIVEN]

validation = app.run_backtest(
    strategies=surviving_strategies,
    study=event_study,
    n_workers=4,
    memory_budget_mb=16_384,
    min_available_memory_mb=4_096,
    backtest_storage_directory="./backtest_storage",
    use_checkpoints=True,
)
```

Each event task gets a fresh app/service container and private SQLite database
in a temporary resource directory. Connections are closed before that
directory is removed, including on failures. Workers receive prepared window
data once per process; the coordinator alone merges output bundles and writes
checkpoints and indexes.

Independent algorithms run concurrently **within a window**. All tasks finish
before the window filter runs and the next window starts. Strategies grouped
in one `Algorithm` remain together on one portfolio; one algorithm's event
timeline is not divided among workers.

Worker contexts are isolated, not copies of a live app's mutable service
container. Do not rely on worker mutations becoming visible in the parent.
Event snapshot buffers are flushed in batches of 256, and configured memory
safeguards are polled during event execution.

## Memory-Budgeted Sweeps

Worker count alone does not bound memory. Each process has its own data and
execution state; a few large workers can exhaust a machine.

```python
results = app.run_backtest(
    strategies=strategies,
    study=study,
    n_workers=6,
    memory_budget_mb=16_384,
    min_available_memory_mb=4_096,
    max_tasks_per_child=16,
    backtest_storage_directory="./backtest_storage",
    use_checkpoints=True,
    show_progress=True,
)
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `memory_budget_mb` | `None` | Soft coordinator-plus-descendants RSS budget in MiB. |
| `min_available_memory_mb` | `None` | Available-memory reserve in MiB. |
| `max_tasks_per_child` | `16` | Pool generation task limit; `None` disables recycling. |
| `window_metrics_filter_function` | `None` | Receives `(BacktestIndex, date_range)` and returns a subset index. |
| `final_metrics_filter_function` | `None` | Receives the final index and returns a subset index. |

Configured budgets and recycling limits must be positive integers. Existing
notebook variables count toward the RSS budget. RSS accounting is conservative:
shared pages may be counted more than once. Available system memory and Linux
cgroup headroom can further restrict admissions.

With memory controls enabled, the scheduler starts conservatively, measures
worker usage, and admits additional work only when estimated headroom permits.
On pressure it stops admissions, drains current work, reclaims the pool, and
either continues with fewer workers or raises a resource error.

:::warning Soft safeguards are not hard limits
A running strategy, native library, data initialization, serialization, or
bundle merge can allocate beyond a threshold before monitoring reacts.
The largest individual task/bundle must still fit in memory. Strategy lists,
index rows, and checkpoint metadata also grow with sweep size.

Prepared data is not shared-memory data. Neither worker count, garbage
collection, nor swap guarantees protection against out-of-memory failures.
Use OS containment when a hard limit is required.
:::

### Windows and WSL 2

An illustrative WSL 2 cap for a 32 GB Windows host is:

```ini
[wsl2]
memory=20GB
swap=4GB
```

Configure this in `%UserProfile%\.wslconfig` or WSL Settings. Save all WSL work
before running `wsl --shutdown` in PowerShell: it stops all WSL distributions.
The cap applies to the whole WSL 2 VM, not only this backtest. Adjust it for
other workloads; swap can substantially slow execution.
See [Microsoft's WSL configuration reference](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).

For workload-level hard containment, use a dedicated Linux/WSL cgroup or a
Windows Job Object. The Python API does not install these limits, and exceeding
them may kill the workload rather than raise a Python exception.

## Window Filter Function

Use scalar metrics instead of loading full backtests for pruning. Rows are
scoped to the requested study and engine. `summary.*` columns describe
evaluated windows; `window_*` columns describe the current window.
Callbacks should explicitly handle missing metric values.

```python
import pandas as pd


def prune_window(index, date_range):
    def keep(row):
        # Use one pooled row per algorithm, not per-universe duplicates.
        if pd.notna(row["universe_key"]):
            return False
        trades = row["window_number_of_trades_closed"]
        if pd.isna(trades) or trades < 1:
            return False
        windows = row["summary.number_of_windows"]
        if pd.isna(windows) or windows < 3:
            return True
        active = row["summary.number_of_windows_with_trades"]
        gain = row["summary.total_net_gain"]
        return active / windows >= 0.5 and gain > 0

    return index.filter(keep)


results = app.run_backtest(
    strategies=strategies, study=study,
    window_metrics_filter_function=prune_window,
    n_workers=4,
    backtest_storage_directory="./backtest_storage",
    use_checkpoints=True,
)
```

Filters must return a subset `BacktestIndex` in the same directory with its
identity columns intact. Foreign/duplicate identities are rejected. Returned
paths and metrics come from authoritative rows, not callback modifications.

## Final Filter Function

Rank pooled scalar rows without materializing full bundles:

```python
def top_twenty(index):
    if index.df.empty:
        return index
    pooled = index.df[index.df["universe_key"].isna()]
    ranked = pooled.nlargest(20, "summary.total_net_gain")
    return BacktestIndex(index.directory, ranked)


results = app.run_backtest(
    strategies=strategies, study=study,
    window_metrics_filter_function=prune_window,
    final_metrics_filter_function=top_twenty,
)
```

## Batching and API Migration

`batch_size` and `checkpoint_batch_size` remain accepted for compatibility, but
public index execution saves/checkpoints each result individually. They do not
control parallel queue depth. Use worker, memory, and recycling controls instead.

- Remove `result_mode="list"`: it is rejected. `result_mode="index"` remains
  accepted but is redundant.
- Replace `results[0]` with `next(results.iter_backtests())`.
- Replace full-object iteration with `results.iter_backtests()`, or explicitly
  load a small selection with `results.load_backtests(workers=1)`.
- Replace `window_filter_function` / `final_filter_function` with their
  `*_metrics_filter_function` equivalents. Full-object callbacks are rejected.
- Keep a persistent directory to resume a run; omitting it starts a new run.
- Count unique `algorithm_id` values rather than index rows.

Start with a short, representative study before launching a large sweep.
Reduce window/data size if one task cannot fit the budget, leave memory for
the OS and other applications, and inspect selected full bundles sequentially.
