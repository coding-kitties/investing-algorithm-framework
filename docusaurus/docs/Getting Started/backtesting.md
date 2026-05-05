---
sidebar_position: 8
---

# Backtesting

Backtesting is the process of running a strategy against historical market
data to estimate how it would have performed. The framework offers two
complementary backtesting modes — pick the one that matches what you
are trying to learn.

## Choosing a backtesting mode

| Aspect | [Event-Driven](event-backtesting) | [Vector](vector-backtesting) |
|--------|-----------------------------------|------------------------------|
| **Speed** | Slower, realistic simulation | 10-100x faster |
| **Stop Loss / Take Profit** | Fully supported | Not supported |
| **Signal Timing** | Executes at next strategy interval | Executes at exact signal timestamp |
| **Position Sizing** | Based on portfolio at execution time | Based on portfolio at signal time |
| **Data Loading** | Sliding window at each step | All data loaded at once |
| **Best For** | Final validation, realistic results | Fast prototyping, parameter sweeps |

A common workflow is to use **vector backtesting** for parameter sweeps
and strategy filtering, and then validate the surviving strategies with
**event-driven backtesting** for realistic execution.

## Event-Driven Backtesting

Event-driven backtesting steps through historical data tick-by-tick,
mimicking the live trading loop. It is the right choice when realism
matters: stop losses, take profits, intra-bar fills, and time-of-day
position sizing all behave the same as in live trading.

```python
from investing_algorithm_framework import create_app, BacktestDateRange
from datetime import datetime, timezone

app = create_app()
app.add_strategy(MyStrategy())
app.add_market(market="bitvavo", trading_symbol="EUR")

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)
```

See [Event-Driven Backtesting](event-backtesting) for the full guide,
including multiple date ranges, accessing metrics and trades, and
best practices.

## Vector Backtesting

Vector backtesting processes the entire price series in a single pass,
which makes it dramatically faster but skips intra-bar simulation
(no stop losses or take profits). It is ideal for parameter sweeps,
running hundreds of strategy variants, and large-scale optimization.

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    backtest_storage_directory="./my_backtests",
    initial_amount=1000
)
```

See [Vector Backtesting](vector-backtesting) for the full guide,
including checkpointing, content-aware reruns (`force_rerun`),
strategy filtering, and parallel processing.

## Saving and Loading Backtests

Both modes can persist their results to disk so you can analyse them
later or share them across machines.

```python
from investing_algorithm_framework import load_backtests_from_directory

backtests = load_backtests_from_directory("./my_backtests")
```

:::info `.iafbt` bundle format
Backtests are persisted in the framework's optimized **`.iafbt` bundle format** — a single binary file per backtest using zstd compression + MessagePack encoding. Compared to the legacy directory layout it is ~21× smaller, ~27× fewer files, and ~3× faster to load. Both `save_backtests_to_directory` and `load_backtests_from_directory` support parallel I/O via `workers=N`. Existing legacy directories keep working transparently; use `iaf migrate-backtests --src ... --dst ...` to convert them.
:::

### Migrating Existing Backtests

Convert a directory of legacy backtest folders to the new bundle
format with `migrate_backtests`. The migration is **streamed**
(load+save fused per worker), so memory usage stays roughly
constant regardless of how many backtests you migrate, and an
interrupted run can simply be re-invoked to resume — destination
bundles that already exist are skipped by default.

```python
from investing_algorithm_framework import migrate_backtests

n = migrate_backtests(
    src_dir="./old_backtests",       # legacy folders and/or .iafbt
    dst_dir="./bundled_backtests",   # destination
    workers=8,                        # parallel; None = min(8, cpu)
    show_progress=True,
    write_index=True,                 # also build index.parquet
    include_ohlcv=False,
    skip_existing=True,               # resume-safe (default)
    delete_source=False,              # set True to remove originals
)
print(f"migrated {n} backtests")
```

Or from the CLI:

```bash
iaf migrate-backtests \
    --src ./old_backtests \
    --dst ./bundled_backtests \
    --workers 8
```

Pass `--delete-source` (or `delete_source=True` in Python) to remove
each legacy directory/bundle after its destination has been written
successfully. Sources are deleted per-backtest, so an interrupted
run leaves only the not-yet-migrated ones behind.

## Reporting

Use [Backtest Reports](/docs/Getting%20Started/backtest-reports) to turn
backtest results — from either mode — into an interactive dashboard or
a self-contained HTML file.

```python
from investing_algorithm_framework import BacktestReport

report = BacktestReport(backtest)
report.show(browser=True)
```

## Next Steps

- [Event-Driven Backtesting](event-backtesting) — realistic simulation
  with full order-execution semantics.
- [Vector Backtesting](vector-backtesting) — fast parameter sweeps and
  optimization, with content-aware checkpoints.
- [Backtest Reports](/docs/Getting%20Started/backtest-reports) — explore
  results in the interactive dashboard.
- [Performance Optimization](/docs/Advanced%20Concepts/OPTIMIZATION_GUIDE)
  — tips for large-scale testing.
