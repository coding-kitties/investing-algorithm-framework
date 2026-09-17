---
sidebar_position: 10
---

# Universes

A `Universe` identifies the assets and market context evaluated by a
[Study](studies). Keeping this definition with the study makes it clear which
market produced a result and allows the same strategy to be tested against
different asset sets without mixing their evidence.

Each study targets exactly one universe. A universe can describe one symbol, a
fixed basket, or the market context used by a strategy that selects symbols
dynamically.

## Define a universe

```python
from investing_algorithm_framework import Universe

crypto_majors = Universe(
    key="crypto_majors_eur",
    symbols=["BTC/EUR", "ETH/EUR"],
    trading_symbol="EUR",
    market="BITVAVO",
    metadata={"selection": "largest EUR pairs"},
)
```

| Field | Purpose |
| --- | --- |
| `key` | Stable identifier used in persisted results and indexes. |
| `symbols` | Assets included in the evaluation. |
| `trading_symbol` | Quote or settlement currency, such as `EUR`. |
| `market` | Exchange, broker, or venue identifier. |
| `metadata` | Optional provenance or selection details. |

When `key` is omitted, the framework derives one from the universe definition.
Use an explicit key when the selection has a durable business meaning or when
you want a stable label in reports.

## Use a universe in a study

```python
from investing_algorithm_framework import Study, StudySampleType

study = Study(
    name="momentum_majors",
    universe=crypto_majors,
    backtest_windows=windows,
    sample_type=StudySampleType.IN_SAMPLE,
)
```

The universe is persisted with the study in the
[Open Backtest Format](open-backtest-format), so reports and external readers
can identify the assets and market behind every result.

## Universe out-of-sample testing

Use separate studies to test whether a strategy generalizes to unseen assets:

```python
development_study = Study(
    name="momentum_development",
    universe=Universe(
        key="development_assets",
        symbols=["BTC/EUR", "ETH/EUR"],
        trading_symbol="EUR",
        market="BITVAVO",
    ),
    backtest_windows=windows,
    sample_type=StudySampleType.IN_SAMPLE,
)

held_out_study = Study(
    name="momentum_held_out",
    universe=Universe(
        key="held_out_assets",
        symbols=["SOL/EUR", "ADA/EUR"],
        trading_symbol="EUR",
        market="BITVAVO",
    ),
    backtest_windows=windows,
    sample_type=StudySampleType.OUT_SAMPLE_UNIVERSE,
)
```

Keeping these as separate studies prevents in-sample and held-out evidence from
being pooled accidentally.

## Related guides

- [Studies](studies) combines a universe, windows, engines, and assumptions.
- [Backtest Windows](backtest-windows) defines the time periods to evaluate.
- [Cross-Sectional Pipelines](../Advanced%20Concepts/pipelines) dynamically
  ranks and filters symbols within a strategy.
