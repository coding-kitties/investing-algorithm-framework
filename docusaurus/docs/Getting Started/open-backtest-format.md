---
sidebar_position: 14
---

# Open Backtest Format

The Open Backtest Format (OBTf) is the portable, versioned bundle format used
for persisted backtests. Each `<algorithm_id>.obtf` file keeps the definition,
results, and lineage of an algorithm together instead of spreading one result
across unrelated files.

OBTf is open and extensible: tools can read and write the format independently
of this framework, and compatible additions can be stored without discarding
the standard model.

## What a bundle contains

```text
Backtest bundle (one algorithm)
├── algorithm identity, parameters, tags, and metadata
└── studies
    └── named study
        ├── universe
        ├── backtest windows
        ├── execution assumptions
        ├── vector runs, summary, and Monte Carlo tests
        └── event runs, summary, and Monte Carlo tests
```

Runs can include metrics, orders, trades, positions, portfolio snapshots, and
custom strategy data. Vector and event evidence use independent engine slots,
so both can coexist in the same study without being confused or overwritten.

## Write bundles

Set a storage directory when running a backtest:

```python
from investing_algorithm_framework import BacktestRunConfiguration

results = app.run_backtest(
    strategy=strategy,
    study=study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./my-backtests",
    ),
)
```

The directory becomes the source of truth for later indexing, reporting, and
analysis. Checkpoints allow interrupted runs to resume without treating a
result from another study or engine as complete.

## Read bundles

Use the public backtest helpers to load one bundle or discover a directory:

```python
from investing_algorithm_framework import get_backtest, get_backtests

backtest = get_backtest("./my-backtests/my_algorithm.obtf")
collection = get_backtests("./my-backtests")

study = backtest.get_study("walk_forward_validation")
vector_runs = study.get_runs(engine="vector")
event_runs = study.get_runs(engine="event")
```

You can also retrieve a result-free copy of a study definition with
`backtest.get_study_definition(name)` and use it for a reproducible rerun.

## OBTf versus the storage layer

OBTf defines what one portable backtest bundle contains. The
[Backtest Storage Layer](backtest-storage) organizes collections of bundles and
adds SQLite indexes, ranking, filtering, tiered layouts, and shared market-data
storage. Small projects can use OBTf files directly; large research collections
can add the storage layer without changing the bundle model.

## Related guides

- [Studies](studies) defines the experiment stored in a bundle.
- [Universes](universes) identifies the evaluated assets and market.
- [Backtest Windows](backtest-windows) defines the evaluation periods.
- [Backtest Reports](backtest-reports) visualizes persisted results.
