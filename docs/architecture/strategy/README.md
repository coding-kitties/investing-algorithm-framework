# Strategy subsystem

Everything about how a strategy is defined, wired up, and executed by the framework — across live, event backtest, and vector backtest modes.

## Docs in this folder

| Document | What it covers |
|---|---|
| [`strategy.md`](strategy.md) | The v9 strategy API surface. The two signal-producing methods (`generate_signals` for event / live, `generate_signal_series` for vector), the `Signal` / `SignalSeries` / `SignalSide` vocabulary, and how a signal flows through the phase pipeline into orders. Read this first if you're writing a new strategy. |
| [`strategy_composition.md`](strategy_composition.md) | Design rationale for the composition model. Explains why `TradingStrategy` is a bag of slots, what each slot means, how phase pipeline / `conflict_policy` / `executor` compose, and the invariants the runtime enforces. Read this if you want to understand *why* the API is shaped the way it is, or if you need to extend it. |
| [`pipeline-api.md`](pipeline-api.md) | The declarative pipeline API: `Factor` / `Filter` building blocks, `Pipeline` subclasses, universe filtering, cross-sectional signal generation, and the `PipelineEngine` runtime. Used for factor-model style strategies with many symbols. |

## Related

- [`../orders_and_trades/`](../orders_and_trades/) — what happens to a signal once it becomes an `Order`.
- [`../event_loop.md`](../event_loop.md) — when the strategy is called, by whom, and how often.
- [`../backtest/`](../backtest/) — how strategies are exercised in the vector and event backtest engines.
