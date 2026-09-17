---
sidebar_position: 8
---

# Backtesting

Backtesting is the process of running an algorithm against historical market
data to estimate how it would have performed. It helps test strategy logic,
measure risk and returns, compare variants, and expose execution problems before
paper or live trading. A backtest is evidence under specific historical data
and assumptions, not a guarantee of future performance.

The framework represents a reproducible backtest with four core concepts:

| Concept | Question it answers |
| --- | --- |
| [Study](studies) | What experiment and assumptions are being evaluated? |
| [Universe](universes) | Which assets and market are included? |
| [Backtest window](backtest-windows) | Which training or test periods run? |
| [Open Backtest Format](open-backtest-format) | How are definitions, results, and lineage persisted? |

The framework offers two complementary backtesting modes. Choose the one that
matches what you are trying to learn.

## Choosing a backtesting mode

| Aspect | [Event-Driven](event-backtesting) | [Vector](vector-backtesting) |
|--------|-----------------------------------|------------------------------|
| **Multi strategy support** | Yes | No, you can only test one strategy class per backtest |
| **Speed** | Slower, realistic simulation | 10-100x faster |
| **Stop Loss / Take Profit** | Fully supported | Fixed rules supported; trailing rules not supported |
| **Signal Timing** | Executes at next strategy interval | Executes at exact signal timestamp |
| **Position Sizing** | Based on portfolio at execution time | Based on portfolio at signal time |
| **Data Loading** | Sliding window at each step | All data loaded at once |
| **Best For** | Final validation, realistic results | Fast prototyping, parameter sweeps |

A common workflow is to use **vector backtesting** for parameter sweeps
and strategy filtering, and then validate the surviving strategies with
**event-driven backtesting** for realistic execution.

> Keep in mind that vector backtesting has some limitations: trailing stop-loss
> and take-profit rules require event-driven validation, and vector mode assumes
> that signals execute at the exact timestamp they are generated, which may not be
> realistic in live trading. Event-driven backtesting, on the other hand, simulates the actual trading
> loop and is more accurate for final validation of strategies.
> Also, data the signal generation is probably not the same as the signal generation on event backtesting or
> live trading. The developer should be aware of the differences in signal generation and choose the appropriate
> backtesting mode based on their needs.

## Event-Driven Backtesting

Event-driven backtesting steps through historical data tick-by-tick,
mimicking the live trading loop. It is the right choice when realism
matters: stop losses, take profits, intra-bar fills, and time-of-day
position sizing all behave the same as in live trading.

```python
from investing_algorithm_framework import BacktestRunConfiguration
from investing_algorithm_framework import (
    create_app, BacktestDateRange, BacktestWindow, Study, Universe,
    Algorithm, Task, Schedule, TimeUnit, TradingStrategy,
)
from datetime import datetime, timezone

app = create_app()
app.add_market(market="bitvavo", trading_symbol="EUR", initial_balance=1000)


class MyStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)

    def run_strategy(self, context, data):
        # inspect `data` and call context.create_order(...) /
        # context.create_limit_order(...) to trade
        pass


# Tasks can be used in event backtesting to run periodic jobs,
# such as logging, reporting, or other maintenance tasks.
class MyTask(Task):
    schedule = Schedule.every(1, TimeUnit.DAY)

    def run(self, context):
        # do something with the context (portfolio, positions, ...)
        pass


# Multiple strategies registered on one Algorithm run TOGETHER,
# sharing a single portfolio, in one combined Backtest.
algorithm = Algorithm(
    algorithm_id="my_algorithm",
    strategies=[MyStrategy()],
    tasks=[MyTask()],
)

# A Study describes *what* is being tested: the universe it trades
# and the date range(s) ("windows") to run it over.
study = Study(
    name="my_study",
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[
        BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            )
        )
    ],
)

results = app.run_backtest(
    algorithm=algorithm,
    study=study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./my_backtests",
        use_checkpoints=True,
    ),
)
backtest = next(results.iter_backtests())

metrics = backtest.get_backtest_metrics(
    study.backtest_windows[0], study_name=study.name
)
print(f"Total Return: {metrics.total_return}%")
```

See [Event-Driven Backtesting](event-backtesting) for the full guide,
including multiple date ranges, accessing metrics and trades, and
best practices.

## Vector Backtesting

Vector backtesting processes the entire price series in a single pass,
which makes it dramatically faster but skips realistic intra-bar order
simulation. Fixed stop-loss and take-profit rules are supported, while trailing
rules, limit-order behavior, partial fills, and live portfolio timing require
event-driven validation. It is ideal for parameter sweeps, running hundreds of
strategy variants, and large-scale optimization.

```python
from investing_algorithm_framework import BacktestRunConfiguration
from investing_algorithm_framework import (
    create_app, BacktestDateRange, BacktestWindow, Study, Universe,
    Schedule, TimeUnit, TradingStrategy,
)
from datetime import datetime, timezone

app = create_app()


class MyStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.DAY)

    def generate_signal_series(self, data):
        # Vectorized signals: yield one SignalSeries per (symbol, side)
        yield ...


study = Study(
    name="my_vector_study",
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[
        BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            )
        )
    ],
)

# run_backtest auto-detects the vector engine since MyStrategy
# overrides generate_signal_series (not generate_signals). Vector
# backtesting only supports a single strategy per backtest.
results = app.run_backtest(
    strategy=MyStrategy(),
    study=study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./my_backtests",
        use_checkpoints=True,
    ),
)
backtest = next(results.iter_backtests())

metrics = backtest.get_backtest_metrics(study.backtest_windows[0])
print(f"Total Return: {metrics.total_return}%")
```

> Note: If you do any long-running computations in your strategy,
> such as usage of machine learning models, its best to precompute
> the data before the signals are generated, and pass the
> precomputed data to the strategy. This will make the backtest
> run faster and avoid any issues with long-running computations.

See [Vector Backtesting](vector-backtesting) for the full guide,
including checkpointing, explicit reruns (`force_rerun=True`),
strategy filtering, and parallel processing.

## Data preparation

Configure data preparation through `BacktestRunConfiguration`.
`fill_missing_data=True` is the default and fills missing OHLCV rows before a
run, so you do not have to hand-roll gap filling.

```python
run_configuration = BacktestRunConfiguration(fill_missing_data=True)
results = app.run_backtest(
    strategy=MyStrategy(),
    study=study,
    run_configuration=run_configuration,
)
```

If you want to precompute features (e.g. for a machine learning model)
before a vector backtest, do it once outside the strategy and pass the
precomputed data in, rather than recomputing it inside
`generate_signal_series` on every call — this keeps the backtest fast
and avoids repeated expensive computation.

## Parameter sweeps and filtering

To test many strategy variants (e.g. a parameter sweep), instantiate
each variant and pass them all as `strategies=[...]`; each strategy
yields its own independent `Backtest` so you can compare results:

```python
strategies = [
    MyStrategy(rsi_period=10),
    MyStrategy(rsi_period=14),
    MyStrategy(rsi_period=20),
]

# A Study can hold multiple windows — one sweep, many date ranges.
study = Study(
    name="rsi_sweep",
    universe=Universe(market="bitvavo", trading_symbol="EUR"),
    initial_capital=1000,
    backtest_windows=[BacktestWindow(train_range=r) for r in date_ranges],
)

results = app.run_backtests(strategies=strategies, study=study)
```

Use `window_metrics_filter_function` to progressively prune underperforming
strategies between windows. The callback receives the current `BacktestIndex`
and date range, then returns a subset index:

```python
import pandas as pd


def keep_profitable(index, date_range):
    return index.filter(
        lambda row: (
            pd.notna(row["summary.total_net_gain"])
            and row["summary.total_net_gain"] > 0
        )
    )


results = app.run_backtests(
    strategies=strategies,
    study=study,
    window_metrics_filter_function=keep_profitable,
)
```

Both entry points also accept `final_metrics_filter_function` for one final
selection after all windows complete. See [Scaling Backtests](/docs/Advanced%20Concepts/vector-backtesting)
for metric columns, ranking, checkpoints, and bounded parallel execution.

## Open Backtest Format

Backtests are persisted as portable, versioned `.obtf` bundles. One bundle can
hold named studies, universes, windows, execution assumptions, and independent
vector and event results for an algorithm. See
[Open Backtest Format](open-backtest-format) for the bundle structure, reading,
writing, and its relationship to the storage layer.

## Next Steps

- [Studies](studies) — define the universe, windows, engine, and evaluation
    assumptions for a reproducible experiment.
- [Universes](universes) — identify the assets and market being evaluated.
- [Backtest Windows](backtest-windows) — model simple periods, holdouts,
  rolling tests, anchored tests, and walk-forward folds.
- [Open Backtest Format](open-backtest-format) — persist definitions, results,
  and lineage in portable `.obtf` bundles.
- [Event-Driven Backtesting](event-backtesting) — realistic simulation
  with full order-execution semantics.
- [Vector Backtesting](vector-backtesting) — fast parameter sweeps and
  optimization, with window/algorithm checkpoints.
- [Backtest Reports](/docs/Getting%20Started/backtest-reports) — explore
  results in the interactive dashboard.
- [Scaling Backtests](/docs/Advanced%20Concepts/vector-backtesting) — use
    persistent indexes, checkpoints, filtering, and bounded workers at scale.
