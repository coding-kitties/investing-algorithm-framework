---
sidebar_position: 9
---

# Studies

A `Study` is the complete definition of one backtesting experiment. It records
what is being evaluated, the market universe, the time windows, the engine, and
the assumptions needed to interpret the results.

Studies are natively represented in the Open Backtest Format (`.obtf`). When a
backtest is saved, its study definitions, runs, summaries, execution settings,
and Monte Carlo results can travel together in one reproducible bundle.

## What a study contains

| Field | Purpose |
| --- | --- |
| `name` | Stable, unique name within the parent backtest. |
| `description` | Human-readable explanation of the experiment. |
| `universe` | The symbols, quote currency, and market being evaluated. |
| `backtest_windows` | Training and optional test periods to execute. |
| `engines` | The event-driven or vector engine to use. |
| `initial_capital` | Starting capital for the evaluation. |
| `risk_free_rate` | Annualized rate used by risk-adjusted metrics. |
| `sample_type` | The study's role, such as in-sample or walk-forward. |
| `window_part` | Whether to run the train, test, or both parts of each window. |
| `metadata` | Custom provenance, parameter fingerprints, or experiment tags. |

Each study targets **exactly one universe**. To test the same strategy on a
different set of assets, create another study. Multiple studies can be stored
in the same backtest bundle, making comparisons explicit without mixing their
evidence.

## Define a study

```python
from datetime import datetime, timezone

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestWindow,
    Study,
    StudySampleType,
    Universe,
    WindowPart,
)

study = Study(
    name="btc_eth_walk_forward",
    description="Quarterly validation of the momentum strategy",
    universe=Universe(
        key="crypto_majors",
        symbols=["BTC/EUR", "ETH/EUR"],
        trading_symbol="EUR",
        market="BITVAVO",
    ),
    backtest_windows=[
        BacktestWindow(
            name="2024_q1",
            train_range=BacktestDateRange(
                start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            test_range=BacktestDateRange(
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 4, 1, tzinfo=timezone.utc),
            ),
            warmup_days=30,
            fold_index=0,
        ),
    ],
    engines=[BacktestEngine.VECTOR],
    initial_capital=10_000,
    risk_free_rate=0.027,
    sample_type=StudySampleType.WALK_FORWARD,
    window_part=WindowPart.TEST,
    metadata={"strategy_family": "momentum"},
)

backtests = app.run_backtest(strategy=strategy, study=study)
```

The `engines` list selects the requested runner. The framework stores completed
runs in per-engine result slots, so vector and event-driven evidence remain
separate inside the same study definition.

## Universes

The `Universe` is part of the study, not an external filter applied after the
run. It identifies the exact assets and market context used to produce the
evidence. See [Universes](universes) for field definitions, stable keys, and
universe out-of-sample patterns.

Use one study per universe when performing universe out-of-sample validation:

```python
major_assets = Study(
    name="momentum_majors",
    universe=Universe(
        key="majors",
        symbols=["BTC/EUR", "ETH/EUR"],
        trading_symbol="EUR",
        market="BITVAVO",
    ),
    sample_type=StudySampleType.IN_SAMPLE,
    backtest_windows=windows,
)

held_out_assets = Study(
    name="momentum_held_out_assets",
    universe=Universe(
        key="held_out_assets",
        symbols=["SOL/EUR", "ADA/EUR"],
        trading_symbol="EUR",
        market="BITVAVO",
    ),
    sample_type=StudySampleType.OUT_SAMPLE_UNIVERSE,
    backtest_windows=windows,
)
```

## Windows and folds

A `BacktestWindow` contains a required `train_range` and an optional
`test_range`. This supports simple holdouts, rolling or anchored windows,
walk-forward folds, and time-based out-of-sample studies. See
[Backtest Windows](backtest-windows) for detailed patterns and warmup behavior.

`window_part` controls which ranges are executed:

- `WindowPart.TRAIN` runs only training ranges.
- `WindowPart.TEST` runs test ranges, falling back to the training range when a
  window has no test range. This is the default.
- `WindowPart.BOTH` runs both ranges as separate runs.

Use `warmup_days` for indicator initialization and `fold_index` to preserve a
fold's identity in rolling and walk-forward studies.

## Sample types

`StudySampleType` labels the role a study plays in the research process. Built-in
types include in-sample, time and universe out-of-sample, walk-forward, stress,
Monte Carlo, and exploratory studies. Custom string values are also supported,
so downstream tools should treat unknown values as valid experiment labels.

## Inspect results

After execution, retrieve the study from its parent `Backtest` and inspect the
engine-specific runs or summaries:

```python
backtest = next(backtests.iter_backtests())
completed_study = backtest.get_study("btc_eth_walk_forward")

runs = completed_study.get_runs(engine="vector")
summary = completed_study.get_summary(engine="vector")
window_metrics = completed_study.get_metrics(
    engine="vector",
    backtest_window=completed_study.backtest_windows[0],
)
```

Use `copy_definition()` to rerun the same universe, windows, and assumptions
without carrying over existing runs or summaries:

```python
replay_study = completed_study.copy_definition()
replay_study.engines = [BacktestEngine.EVENT_DRIVEN]

event_backtests = app.run_backtest(strategy=strategy, study=replay_study)
```

This makes vector-to-event validation reproducible and keeps both experiments
grounded in the same study definition.

## Related guides

- [Backtesting](backtesting) explains the complete backtesting workflow.
- [Universes](universes) explains asset and market definitions.
- [Backtest Windows](backtest-windows) explains evaluation periods and folds.
- [Event-Driven Backtesting](event-backtesting) covers realistic execution.
- [Vector Backtesting](vector-backtesting) covers fast research and sweeps.
- [Open Backtest Format](open-backtest-format) explains `.obtf` bundles.
- [Backtest Storage](backtest-storage) explains indexing and tiered storage.
