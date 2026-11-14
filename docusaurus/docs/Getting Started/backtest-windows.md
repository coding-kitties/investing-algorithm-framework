---
sidebar_position: 11
---

# Backtest Windows

A `BacktestWindow` defines the historical periods evaluated by a
[Study](studies). A window always has a training range and can also have a test
range, which supports simple date ranges, holdouts, rolling tests, anchored
tests, and walk-forward folds with the same model.

## Define a window

```python
from datetime import datetime, timezone

from investing_algorithm_framework import BacktestDateRange, BacktestWindow

window = BacktestWindow(
    name="2024_q1_fold",
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
)
```

| Field | Purpose |
| --- | --- |
| `name` | Human-readable identity for the window. |
| `train_range` | Required range used for training or a standalone run. |
| `test_range` | Optional held-out range used for validation. |
| `warmup_days` | Initial days reserved for indicator initialization. |
| `fold_index` | Stable fold identity for rolling or walk-forward studies. |

Dates should be timezone-aware. The framework persists both ranges and the
window metadata, so each run can be traced back to its intended evaluation
period.

## Choose which range runs

Set `Study.window_part` to control how its windows are executed:

- `WindowPart.TRAIN` runs each training range.
- `WindowPart.TEST` runs each test range and falls back to the training range
  when no test range exists. This is the default.
- `WindowPart.BOTH` runs the training and test ranges separately.

```python
from investing_algorithm_framework import Study, WindowPart

study = Study(
    name="walk_forward_validation",
    universe=universe,
    backtest_windows=[window],
    window_part=WindowPart.TEST,
)
```

## Common window designs

| Design | Window pattern |
| --- | --- |
| Single period | One `train_range`, no `test_range`. |
| Holdout | One fixed training range followed by one test range. |
| Rolling | Move both range boundaries forward for each fold. |
| Anchored | Keep the training start fixed and extend its end for each fold. |
| Walk-forward | Create ordered train/test pairs and assign `fold_index`. |
| Time out-of-sample | Put later unseen dates in test ranges or a separate study. |

Use multiple named windows when performance must be evaluated across regimes.
Summaries can then aggregate the runs while preserving per-window metrics.

## Warmup periods

`warmup_days` reserves the beginning of the training range for loading enough
history to initialize indicators. It does not create a separate result window.
Choose a warmup long enough for the strategy's largest lookback and keep it
consistent when comparing variants.

## Related guides

- [Studies](studies) explains how windows form a complete experiment.
- [Universes](universes) defines the assets evaluated in those windows.
- [Vector Backtesting](vector-backtesting) covers multi-window sweeps.
- [Event-Driven Backtesting](event-backtesting) covers realistic validation.
