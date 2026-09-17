---
sidebar_position: 9
---

# Event-Driven Backtesting

Event-driven backtesting processes historical market data chronologically
through the same strategy loop used in live trading. At each scheduled time the
framework updates market data and portfolio state, runs due strategies and
tasks, evaluates orders, and records resulting trades and snapshots.

Use it when execution behavior matters: portfolio-aware position sizing, stop
losses, take profits, cooldowns, order timing, and multiple strategies sharing
one portfolio are all evaluated sequentially.

> Looking for a high-level comparison of backtesting modes? See [Backtesting](backtesting). For batch-style high-throughput runs, see [Vector Backtesting](vector-backtesting).

## Quick Start

```python
from datetime import datetime, timezone

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestWindow,
    Study,
    Universe,
    create_app,
)

app = create_app()
app.add_market(market="bitvavo", trading_symbol="EUR")

study = Study(
    name="event_validation",
    universe=Universe(
        market="BITVAVO",
        trading_symbol="EUR",
        symbols=["BTC/EUR"],
    ),
    initial_capital=1_000,
    risk_free_rate=0.027,
    engines=[BacktestEngine.EVENT_DRIVEN],
    backtest_windows=[
        BacktestWindow(
            train_range=BacktestDateRange(
                start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        )
    ],
)

results = app.run_backtest(
    strategy=MyStrategy(),
    study=study,
)

# run_backtest returns a disk-backed BacktestIndex. Load a full bundle
# only when its orders, trades, signals, or snapshots are needed.
backtest = next(results.iter_backtests())
```

The explicit `engines` value ensures the event engine is used. If it is omitted,
the framework selects an engine from the strategy's implemented signal API.

## What the engine simulates

For each timestamp in a study window, the engine:

1. Makes the current and warmup market data available to due strategies.
2. Updates open positions, stop losses, take profits, and portfolio value.
3. Runs scheduled strategy and task hooks.
4. Evaluates newly created orders according to the configured blotter and
   execution assumptions.
5. Persists orders, trades, signals, and portfolio snapshots into the run.

An order emitted on the final bar may remain unfilled because no later market
event exists to execute it. Include enough data after the last expected signal
when testing entry and exit behavior.

## Multiple windows

A study can evaluate the same strategy over several independent periods. Each
window produces a separate run inside the study's event result slot.

```python
study.backtest_windows = [
    BacktestWindow(train_range=date_range, name=name)
    for name, date_range in [
        ("bear_market", bear_market_range),
        ("recovery", recovery_range),
        ("sideways_market", sideways_range),
    ]
]

results = app.run_backtest(strategy=MyStrategy(), study=study)
```

For train/test folds, rolling windows, and `window_part`, see
[Studies](studies).

## One strategy, comparisons, and shared portfolios

Choose the input based on what you are testing:

| Input | Behavior |
| --- | --- |
| `strategy=` | Runs one strategy in its own portfolio. |
| `strategies=` | Compares strategies independently; each gets a portfolio and bundle. |
| `algorithm=` | Runs the algorithm's strategies together in one shared portfolio and bundle. |
| `algorithms=` | Compares independent multi-strategy algorithms. |

Use an `Algorithm` when interactions between strategies are part of the test:

```python
from investing_algorithm_framework import Algorithm

algorithm = Algorithm(
    algorithm_id="combined_portfolio",
    strategies=[MomentumStrategy(), MeanReversionStrategy()],
)

results = app.run_backtest(algorithm=algorithm, study=study)
```

Orders and trades retain their `strategy_id`, allowing results from a shared
portfolio to be attributed to the strategy that created them.

## Analyzing Results

### Backtest Report

Generate a visual report from the loaded backtest:

```python
from investing_algorithm_framework import BacktestReport

report = BacktestReport(backtest)
report.show(browser=True)
```

See [Backtest Reports](/docs/Getting%20Started/backtest-reports) for full documentation on the dashboard features, compare mode, and API reference.

### Accessing Metrics

```python
completed_study = backtest.get_study("event_validation")
metrics = completed_study.get_summary(engine="event")

print(f"Total Return: {metrics.total_return}%")
print(f"Sharpe Ratio: {metrics.sharpe_ratio}")
print(f"Max Drawdown: {metrics.max_drawdown}%")
print(f"Total Trades: {metrics.number_of_trades_closed}")
```

### Accessing Trades

```python
for run in completed_study.get_runs(engine="event"):
    for trade in run.trades:
        print(f"Symbol: {trade.symbol}")
        print(f"Entry: {trade.entry_price}")
        print(f"Exit: {trade.exit_price}")
        print(f"Return: {trade.return_percentage}%")
```

## Event-specific considerations

- Configure fees, slippage, fill behavior, and initial capital before comparing
    event results with vector results.
- Ensure each data source has enough history before the study window for its
    longest indicator warmup.
- Treat strategy schedules as part of the experiment: they determine when the
    strategy can observe data and emit orders.
- Use vector backtesting to screen large parameter sets, then replay surviving
    study definitions with the event engine for execution validation.
- Leave at least one executable market event after the last expected signal.

## Next Steps

- Compare modes on the [Backtesting overview](backtesting).
- Define reproducible universes and windows with [Studies](studies).
- Switch to [Vector Backtesting](vector-backtesting) for fast parameter sweeps and optimization.
- Explore [Backtest Reports](/docs/Getting%20Started/backtest-reports) for the interactive dashboard.
- Scale checkpoints and parallel workers with [Scaling Backtests](/docs/Advanced%20Concepts/vector-backtesting).
