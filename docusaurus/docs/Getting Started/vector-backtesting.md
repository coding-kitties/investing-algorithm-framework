---
sidebar_position: 10
---

# Vector Backtesting

Vector backtesting evaluates a strategy's complete price series in batches
instead of replaying the live event loop one timestamp at a time. A strategy
implements `generate_signal_series()` and returns timestamp-aligned entry and
exit signals that the vector engine converts into runs, trades, and metrics.

This removes much of the per-tick framework overhead, making the engine useful
for parameter screening and broad research. It is not an order-book simulator;
validate surviving strategies with the event-driven engine before deployment.

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

results = app.run_backtest(
    strategy=my_strategy,
    study=study,
)
backtest = next(results.iter_backtests())
```

`run_backtest()` returns a disk-backed `BacktestIndex`, not a list of full
bundles. Filter its scalar columns first, then use `iter_backtests()` when you
need orders, trades, signals, or snapshots.

### Multiple Strategies

Compare many strategy configurations independently. Each strategy receives its
own portfolio and produces its own `.obtf` bundle:

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

results = app.run_backtests(
    strategies=strategies,
    study=study,
    run_configuration=BacktestRunConfiguration(
        snapshot_interval=SnapshotInterval.DAILY,
    ),
)
```

## Position sizing

By default, vector runs size each trade against the run's initial balance. This
keeps the simulation fast and vectorizable, but it does not compound position
sizes after earlier gains or losses.

Enable dynamic sizing when `PositionSize.percentage_of_portfolio` should use the
current simulated balance, matching event-driven sizing more closely:

```python
results = app.run_backtests(
    strategies=strategies,
    study=study,
    run_configuration=BacktestRunConfiguration(
        dynamic_position_sizing=True,
    ),
)
```

Dynamic sizing performs more sequential work. Use it for parity checks and
capital-sensitive sizing; leave it disabled for the fastest broad screening.

## Replaying a study with the event engine

Reuse the exact universe, windows, capital, and metadata when validating a
vector result with realistic execution:

```python
vector_backtest = next(results.iter_backtests())
event_study = vector_backtest.get_study_definition(study.name)
event_study.engines = [BacktestEngine.EVENT_DRIVEN]

event_results = app.run_backtest(
    strategy=surviving_strategy,
    study=event_study,
)
```

Saving into the same backtest storage directory merges the new engine's result
slot into the existing algorithm bundle when the algorithm identity matches.

## Differences from Event-Driven Backtesting

| Aspect | Vector | Event-Driven |
|--------|--------|-------------|
| **Speed** | 10-100x faster | Slower, realistic |
| **Stop Loss / Take Profit** | Fixed rules only; no trailing rules | Fully supported |
| **Signal Timing** | Executes at exact signal timestamp | Executes at next interval boundary |
| **Data Loading** | All data loaded at once | Sliding window at each step |
| **Best For** | Fast prototyping, parameter sweeps | Final validation, realistic results |

Signal parity depends on both engines seeing enough history. The vector engine
evaluates the full batch, while the event engine recalculates over a sliding
warmup window. Set the event data provider and strategy data source warmup to at
least two or three times the longest indicator period when comparing signals.

Even with identical signals, execution can differ because vector signals execute
at their timestamps while event orders require subsequent market events and use
the live portfolio state.

## Next Steps

- Use [Scaling Backtests](/docs/Advanced%20Concepts/vector-backtesting) for
    persistent indexes, progressive filtering, checkpoints, parallel workers, and
    memory budgets.
- Replay finalists with [Event-Driven Backtesting](event-backtesting).
- Generate [Backtest Reports](backtest-reports) to compare selected strategies.
