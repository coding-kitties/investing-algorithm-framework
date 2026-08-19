---
sidebar_position: 8
---

# Backtesting

Backtesting is the process of running an algorithm against historical market
data to estimate how it would have performed. The framework offers two
complementary backtesting modes, pick the one that matches what you
are trying to learn.

## Choosing a backtesting mode

| Aspect | [Event-Driven](event-backtesting) | [Vector](vector-backtesting) |
|--------|-----------------------------------|------------------------------|
| **Multi strategy support** | Yes | No, you can only test one strategy class per backtest |
| **Speed** | Slower, realistic simulation | 10-100x faster |
| **Stop Loss / Take Profit** | Fully supported | Not supported |
| **Signal Timing** | Executes at next strategy interval | Executes at exact signal timestamp |
| **Position Sizing** | Based on portfolio at execution time | Based on portfolio at signal time |
| **Data Loading** | Sliding window at each step | All data loaded at once |
| **Best For** | Final validation, realistic results | Fast prototyping, parameter sweeps |

A common workflow is to use **vector backtesting** for parameter sweeps
and strategy filtering, and then validate the surviving strategies with
**event-driven backtesting** for realistic execution.

> Keep in mind that vector backtesting has some limitations: it does not support stop losses or take profits,
> and it assumes that all signals are executed at the exact timestamp they are generated, which may not be
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

backtests = app.run_backtest(
    algorithm=algorithm,
    study=study,
    backtest_storage_directory="./my_backtests",
    use_checkpoints=True,
)
backtest = backtests[0]

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
which makes it dramatically faster but skips intra-bar simulation
(no stop losses, take profits, signal cooldowns, order sizing etc). It is ideal for parameter sweeps, running hundreds of strategy variants, and large-scale optimization.

```python
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
backtests = app.run_backtest(
    strategy=MyStrategy(),
    study=study,
    backtest_storage_directory="./my_backtests",
    use_checkpoints=True,
)
backtest = backtests[0]

metrics = backtest.get_backtest_metrics(study.backtest_windows[0])
print(f"Total Return: {metrics.total_return}%")
```

> Note: If you do any long-running computations in your strategy,
> such as usage of machine learning models, its best to precompute
> the data before the signals are generated, and pass the
> precomputed data to the strategy. This will make the backtest
> run faster and avoid any issues with long-running computations.

See [Vector Backtesting](vector-backtesting) for the full guide,
including checkpointing, content-aware reruns (`force_rerun`),
strategy filtering, and parallel processing.

## Data preparation

Both `run_backtest` and `run_backtests` accept a `fill_missing_data`
flag (default `True`) that automatically fills missing OHLCV rows
before the backtest runs, so you don't have to hand-roll gap-filling
yourself.

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

backtests = app.run_backtests(strategies=strategies, study=study)
```

Use `window_filter_function`/`final_filter_function` to progressively
prune underperforming strategies between date ranges instead of
waiting until every window has finished:

```python
def window_filter(backtest_run):
    """Runs after each date range; keep only profitable strategies."""
    return backtest_run.backtest_metrics.total_return > 0

def final_filter(backtest):
    """Runs once, after all date ranges have completed."""
    return backtest.backtest_summary.sharpe_ratio > 1.0

backtests = app.run_backtests(
    strategies=strategies,
    study=study,
    window_filter_function=window_filter,
    final_filter_function=final_filter,
)
```

Both `run_backtest` and `run_backtests` support these same
`window_filter_function`/`final_filter_function` parameters,
regardless of which engine is used.

## Open Backtest Format

Backtests are persisted in the framework's optimized **`.obtf` bundle format**, which is a single file containing all the data and metadata for a backtest. The format is designed to be efficient for both reading and writing, and is compatible with both event-driven and vector backtesting modes.

The goal of this format is to be **open and extensible**: you can read and write the format without the framework, and you can add your own custom data to the bundle without breaking compatibility with future versions of the framework.

Also this format allows developers to see the entire lineage of a backtest, including the strategies, studies, parameters, and data used to generate the results. This makes it easy to reproduce results and understand how a backtest was generated and to see the performance of your strategy accross scenarios.

## Next Steps

- [Event-Driven Backtesting](event-backtesting) — realistic simulation
  with full order-execution semantics.
- [Vector Backtesting](vector-backtesting) — fast parameter sweeps and
  optimization, with content-aware checkpoints.
- [Backtest Reports](/docs/Getting%20Started/backtest-reports) — explore
  results in the interactive dashboard.
- [Performance Optimization](/docs/Advanced%20Concepts/OPTIMIZATION_GUIDE)
  — tips for large-scale testing.
