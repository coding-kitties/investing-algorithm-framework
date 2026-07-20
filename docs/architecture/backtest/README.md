# Backtest Architecture

**Status:** Stable. Default since v9.0
**Author:** Marc van Duyn

This directory documents the in-memory data model, on-disk bundle format,
and surrounding workflows for the `investing-algorithm-framework` backtest
system.

---

## Documents in this directory

| File | What it covers |
|------|----------------|
| [data_model.md](data_model.md) | Entity-relationship diagram and field reference for all in-memory types: `Backtest`, `Study`, `EngineSlot`, `Universe`, `BacktestWindow`, `BacktestRun`, `BacktestMetrics`, `BacktestSummaryMetrics`, `MonteCarloTest`, `Trade`, `Position`, `PortfolioSnapshot` |
| [backtest_storage.md](backtest_storage.md) | On-disk `.iafbt` bundle format (v5): outer envelope layout, msgpack body shape, Parquet blob extraction, OHLCV side-store, read/write API contracts, versioning policy |
| [backtesting_workflow.md](backtesting_workflow.md) | Step-by-step workflow: in-sample sweeps, OOS extension, multi-universe studies, event-engine runs, adding Monte-Carlo significance tests |
| [sota_quant_workflow.md](sota_quant_workflow.md) | State-of-the-art quant workflow: how the framework maps onto industry-standard walk-forward practices |

---

## High-level structure

As of v9.0 every backtest result is stored in a three-level hierarchy:

```
Backtest                                # keyed by algorithm_id
├── algorithm_id: str
├── anchor_algorithm_id: str | None     # lineage edge (None on anchor bundles)
├── parameters: dict
├── metadata: dict
├── framework_version: str
├── bundle_format_version: int          # 5 for v9.0 bundles
└── studies: dict[str, Study]
        ├── name: str
        ├── description: str
        ├── windows: list[BacktestWindow]   # train/test/gap/warmup ranges
        ├── universe: Universe              # symbols, market, trading_symbol,
        │                                   #   initial_capital, risk_free_rate
        ├── engine_results:
        │     ├── "vector":               # optional engine slot
        │     │     ├── runs: list[BacktestRun]
        │     │     ├── summary: BacktestSummaryMetrics   # pooled across all runs
        │     │     └── summaries_by_universe: dict[str, BacktestSummaryMetrics]
        │     └── "event":               # same shape
        │           ├── runs: list[BacktestRun]
        │           ├── summary: BacktestSummaryMetrics
        │           └── summaries_by_universe: dict[str, BacktestSummaryMetrics]
        └── monte_carlo_tests: list[BacktestMonteCarloTest]
```

Key v9.0 design decisions:

- **`risk_free_rate` moved to `Universe`** — it is a property of the
  asset universe (risk-free benchmark rate for Sharpe/Sortino), not of
  the algorithm. Default is `0.027` (2.7 %).
- **`EngineSlot` is the run container** — all runs and summaries live
  inside `Study.engine_results["vector"]` / `["event"]`, not directly
  on `Backtest` or `Study`.
- **`BacktestWindow` is a first-class object** on `Study` — carries
  `train_range`, `test_range`, `warmup_days`, `gap_days` (derived),
  and `fold_index`. No longer implied by scanning run dates.
- **Monte-Carlo tests live on `Study`** — not at the top level.
- **Default-study rule** — when a bundle has exactly one study,
  `backtest.get_runs(engine)` / `backtest.get_summary(engine)` resolve
  to that study transparently (legacy single-bundle path). Multiple
  studies require an explicit `study=` argument.

For full field references see [data_model.md](data_model.md).
For the on-disk format see [backtest_storage.md](backtest_storage.md).

---

## What is a `.iafbt` file?

A `.iafbt` file is the unit of storage for one algorithm's backtest
results. It is identified by `algorithm_id` — a fingerprint of the
algorithm code and configuration — so results from different runs of
the same algorithm naturally co-locate in the same file.

The `anchor_algorithm_id` field links derived bundles (e.g. perturbed
variants, cooldown-stress runs) back to their anchor, enabling a single
`GROUP BY anchor_algorithm_id` to recover an entire neighbourhood of
related strategies.

See [backtest_storage.md](backtest_storage.md) for the full on-disk specification.

---

## Common use cases

| Use case | Phase |
|----------|-------|
| In-sample parameter sweep (one study per bundle) | ✅ Phase 3a |
| Event-engine slot added to existing vector study | ✅ Phase 3a |
| Adding a second study to an existing bundle | ⚠️ Phase 3b |
| Out-of-sample study appended to in-sample bundle | ⚠️ Phase 3b |
| Monte-Carlo significance test on a study/engine slot | ✅ Phase 3a |

See [backtesting_workflow.md](backtesting_workflow.md) for step-by-step details on each use case.
