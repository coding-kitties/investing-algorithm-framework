# Architecture documentation

This folder contains the in-depth architecture and design references
for `investing-algorithm-framework` (IAF). Start with
[`general.md`](general.md) for the layered overview, then drill into
the subsystem you care about.

## Index

| Document | What it covers |
|---|---|
| [`general.md`](general.md) | Layered overview, package map, runtime lifecycle (live + backtest), extension points, persistence model, dependency injection, and a "where to look in the code" map. **Start here.** |
| [`strategy.md`](strategy.md) | The v9 strategy API. Why the signal surface is split into `generate_signals` (event mode) and `generate_signal_series` (vector mode), what `Signal` / `SignalSeries` / `SignalSide` mean, and how a signal flows through the phase pipeline. |
| [`event_loop.md`](event_loop.md) | The per-iteration loop: how `EventLoopService` decides which strategies, tasks, and scheduled functions are due, how it fetches data once per iteration, when it reconciles fills via the trade-order evaluator, and how snapshots are taken. |
| [`orders.md`](orders.md) | Order lifecycle in detail — creation, validation, execution, fills, BUY/SELL/SHORT/COVER routing, pending stop-loss / take-profit on unfilled orders, metadata persistence, and the order/trade allocation ledger. |
| [`trades.md`](trades.md) | Trade lifecycle — when trades are materialized (one per fill event), `is_short` semantics, FIFO close behaviour, partial fills, realized vs unrealized P&L, and how SL/TP rules attach to a trade. |
| [`backtest_storage.md`](backtest_storage.md) | The `.iafbt` bundle file format — directory layout, manifest schema, per-engine slot structure, the embedded SQLite index, and versioning rules for the on-disk format. |
| [`pipeline-api.md`](pipeline-api.md) | The declarative pipeline API (universe filter → signal → sizing → execution stages) and the `PipelineEngine` that runs it. Tracks issue #438. |

## Companion references

These live outside this folder but are part of the architecture picture:

- [`../migration-v8-to-v9.md`](../migration-v8-to-v9.md) — concrete
  before/after diffs for every breaking change in v9.0 (scheduling
  API, dual-engine backtest, trade-per-fill, executor/provider
  registration, …).
- [`../design/`](../design/) — earlier design notes that informed the
  current architecture. Kept for historical context; the documents in
  this folder are the source of truth for the current implementation.

## Conventions used in these docs

- **Layering arrows point inward.** `app` → `services` →
  `infrastructure` → `domain`. The reverse is never allowed.
- **Code links** use workspace-relative paths so they resolve both
  on GitHub and inside an editor.
- **"v9.0"** in a section header means "applies to the v9 line and
  later"; older behaviour, if relevant, is called out inline.
- **Issue references** (e.g. `#434`) link to GitHub issues that
  motivated the design or that track outstanding follow-up work.
