# Architecture documentation

This folder contains the in-depth architecture and design references for `investing-algorithm-framework` (IAF). Start with [`general.md`](general.md) for the layered overview, then drill into the subsystem you care about.

## Layout

The architecture docs are organised by subsystem:

```text
architecture/
├── general.md               ← layered overview (start here)
├── event_loop.md
├── strategy/                ← how strategies are defined & executed
├── orders_and_trades/       ← order and trade lifecycle
└── backtest/                ← backtest engines, storage format, workflows
```

## Cross-cutting docs

| Document | What it covers |
|---|---|
| [`general.md`](general.md) | Layered overview, package map, runtime lifecycle (live + backtest), extension points, persistence model, dependency injection, and a "where to look in the code" map. **Start here.** |
| [`event_loop.md`](event_loop.md) | The per-iteration loop: how `EventLoopService` decides which strategies, tasks, and scheduled functions are due, how it fetches data once per iteration, when it reconciles fills via the trade-order evaluator, and how snapshots are taken. |

## Strategy subsystem — [`strategy/`](strategy/)

| Document | What it covers |
|---|---|
| [`strategy/strategy.md`](strategy/strategy.md) | The v9 strategy API. Why the signal surface is split into `generate_signals` (event mode) and `generate_signal_series` (vector mode), what `Signal` / `SignalSeries` / `SignalSide` mean, and how a signal flows through the phase pipeline. |
| [`strategy/strategy_composition.md`](strategy/strategy_composition.md) | Design rationale for the composition model — the slot-based `TradingStrategy` class, phase pipeline, declarative rule lists, and the `conflict_policy` / `executor` extension points. |
| [`strategy/pipeline-api.md`](strategy/pipeline-api.md) | The declarative pipeline API (universe filter → signal → sizing → execution stages) and the `PipelineEngine` that runs it. |

## Orders & trades — [`orders_and_trades/`](orders_and_trades/)

| Document | What it covers |
|---|---|
| [`orders_and_trades/orders.md`](orders_and_trades/orders.md) | Order lifecycle in detail — creation, validation, execution, fills, BUY/SELL/SHORT/COVER routing, pending stop-loss / take-profit on unfilled orders, metadata persistence, and the order/trade allocation ledger. |
| [`orders_and_trades/trades.md`](orders_and_trades/trades.md) | Trade lifecycle — when trades are materialised (one per fill event), `is_short` semantics, FIFO close behaviour, partial fills, realized vs unrealized P&L, and how SL/TP rules attach to a trade. |

## Backtest subsystem — [`backtest/`](backtest/)

| Document | What it covers |
|---|---|
| [`backtest/README.md`](backtest/README.md) | Overview of the backtest subsystem: engines, storage tiers, workflow. |
| [`backtest/data_model.md`](backtest/data_model.md) | Entity-relationship diagram and field reference for the in-memory backtest object graph. |
| [`backtest/open_backtest_format.md`](backtest/open_backtest_format.md) | On-disk `.obtf` bundle format (OBTF reference implementation): full field-by-field spec of every serialised type, cost / slippage attribution, and Monte-Carlo test layout. |
| [`backtest/backtest_storage.md`](backtest/backtest_storage.md) | The directory layout of a `.obtf` bundle, msgpack body shape, Parquet blob extraction, embedded SQLite index, and versioning rules. |
| [`backtest/tiered-backtest-storage.md`](backtest/tiered-backtest-storage.md) | Three-tier storage architecture: bundle files, SQLite index, in-memory materialisation. |
| [`backtest/ohlcv-dedup-protocol.md`](backtest/ohlcv-dedup-protocol.md) | Cross-bundle OHLCV deduplication protocol used by the tiered store. |
| [`backtest/v9.0-dual-engine-design.md`](backtest/v9.0-dual-engine-design.md) | Design rationale for the vector / event dual-engine split. |
| [`backtest/backtesting_workflow.md`](backtest/backtesting_workflow.md) | Step-by-step workflow: in-sample sweeps, OOS extension, multi-universe studies, event-engine runs, adding Monte-Carlo significance tests. |
| [`backtest/sota_quant_workflow.md`](backtest/sota_quant_workflow.md) | State-of-the-art quant workflow: how the framework maps onto industry-standard walk-forward practices. |

## Conventions used in these docs

- **Layering arrows point inward.** `app` → `services` → `infrastructure` → `domain`. The reverse is never allowed.
- **Code links** use workspace-relative paths so they resolve both on GitHub and inside an editor.
- **"v9.0"** in a section header means "applies to the v9 line and later"; older behaviour, if relevant, is called out inline.
