# Strategy Composition — Design Doc

> **Status:** Stable. Default since v9.0.
> **Author:** Marc van Duyn
>
> Related design docs: [`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md), [`open_backtest_format.md`](open_backtest_format.md).
> Related architecture docs: [`strategy.md`](strategy.md), [`pipeline-api.md`](pipeline-api.md), [`../orders_and_trades/orders.md`](../orders_and_trades/orders.md), [`../orders_and_trades/trades.md`](../orders_and_trades/trades.md).

## 1. Goals & non-goals

### Goals

1. Provide a **single class** (`TradingStrategy`) that describes a trading strategy end-to-end and runs **unchanged** across the vector backtest engine, the event-driven backtest engine, and live trading.
2. Express *what data, when to fire, what to trade, how to size, how to manage risk, when to enter/exit* as **declarative slots** rather than imperative code paths, so the engines can enforce them identically.
3. Make every cross-cutting concern (position sizing, stop-loss, take-profit, scale-in/out, cooldowns, trading costs, scheduling, recording) **independently optional**: a minimal strategy is a class with two signal methods; everything else is a class attribute or constructor kwarg.
4. Keep the public API stable enough that old strategies keep working when new capabilities are added (e.g. short selling, pipelines, scheduled functions).

### Non-goals

- A DSL or visual builder. Strategies are Python classes.
- Multi-broker / multi-portfolio routing inside a single strategy (one strategy → one portfolio).
- Hard real-time event ordering across strategies (the engine sequences strategies, not the strategy itself).

## 2. Mental model

A `TradingStrategy` is a **bag of composable slots** plus **signal callbacks**. The framework executes the strategy by:

1. Resolving its **schedule** to decide *when* to call it.
2. Loading data from its **`data_sources`** (and any **`universe`** sources folded in by pipelines).
3. (Optional) Running its **`pipelines`** to materialise a cross-sectional factor frame.
4. Calling the strategy's **signal producer** — `generate_signals(context, data)` for the event / live path, or `generate_signal_series(data)` for the vector backtest engine. Both yield structured `Signal` / `SignalSeries` objects tagged with a `SignalSide` (open / close long or short) and an optional `strength`.
5. Walking the strategy's **phase pipeline** (`CollectSignalsPhase` → `ResolveConflictsPhase` → `SizePositionsPhase` → `ApplyRiskBudgetPhase` → `EmitOrdersPhase` → `AttachRiskRulesPhase` → `RecordCooldownPhase`) which routes those signals through the declarative rule lists (`position_sizes`, `stop_losses`, `take_profits`, `scaling_rules`, `cooldowns`, `trading_costs`) to produce concrete orders and trade state.

The strategy never creates orders directly — it emits signals; the phases + rules + `executor` produce orders. This is what allows the *same* class to run in all three modes without conditional logic.

```text
        ┌──────────────────────────────────────────────────────────┐
        │                   TradingStrategy                        │
        │                                                          │
  data  │  data_sources / universe / pipelines                     │
  ───►  │            │                                             │
        │            ▼                                             │
        │   generate_signals(context, data)     (event / live)     │
        │   generate_signal_series(data)        (vector)           │
        │            │                                             │
        │            ▼                                             │
        │   Phase pipeline: Collect → ResolveConflicts →           │
        │                   SizePositions → ApplyRiskBudget →      │
        │                   EmitOrders → AttachRiskRules →         │
        │                   RecordCooldown                         │
        │            │                                             │
  rules │            ▼                                             │
        │  PositionSize · StopLoss · TakeProfit · Scaling ·        │
        │  Cooldown · TradingCost · ConflictPolicy · Executor      │
        │            │                                             │
        └────────────┼─────────────────────────────────────────────┘
                     ▼
              Orders / Trades / Portfolio snapshots
```

## 3. The slots

Every slot is a class attribute *and* a constructor kwarg. The constructor resolves the value with the precedence **constructor arg > class attribute > sensible default**, and clones any mutable defaults per-instance so two `TradingStrategy` instances never share state.

### 3.1 Identity

| Slot | Type | Required | Purpose |
|---|---|---|---|
| `strategy_id` | `str` | no (defaults to class name) | Unique identifier of *this* strategy instance. Used in logs, bundles, dashboards. |
| `algorithm_id` | `str` | no | Identifier of the **combined** algorithm (a group of cooperating strategies). |
| `metadata` | `dict` | no | Free-form bag of author, version, tags, etc. Persisted in backtest bundles. |

### 3.2 Scheduling

| Slot | Type | Required | Purpose |
|---|---|---|---|
| `schedule` | `Schedule` | **yes** | When the strategy fires. `Schedule.every(interval, time_unit)` for periodic; `Schedule.on(date_rule, time_rule)` for calendar-anchored (month-end at 16:00 etc). |
| `scheduled_functions` | `List[ScheduledFunction]` | no | Extra methods on the same strategy that run on their own schedules (e.g. a `rebalance()` hook on the last trading day of the month). |

The legacy v8 `time_unit` / `interval` pair was removed in v9.0; `Schedule` is the single source of truth.

### 3.3 Data

| Slot | Type | Required | Purpose |
|---|---|---|---|
| `symbols` | `List[str]` | yes-ish (required for the long/short signal helpers; pipelines may infer it) | The symbols this strategy can trade. |
| `trading_symbol` | `str` | no | The quote / cash asset (e.g. `"EUR"`). |
| `data_sources` | `List[DataSource]` | yes (when generating signals from data) | Declarative data subscriptions: type (OHLCV, ticker, …), symbol, timeframe, market, `warmup_window`. The engine guarantees each source has enough history before calling the strategy. |
| `universe` | `List[str]` or `List[DataSource]` | no | Pipeline-only: candidate symbol pool that pipelines filter down. See [`pipeline-api.md`](pipeline-api.md). |
| `pipelines` | `List[type[Pipeline]]` | no | Cross-sectional factor / filter pipelines run before each `run_strategy` call. Opt-in — empty list = zero overhead. |

The `__init__` enforces an invariant: if the schedule is interval-based and faster than the smallest OHLCV timeframe in `data_sources`, the strategy raises `OperationalException` at construction time. (You can't sensibly fire every 5 minutes against 1h candles.)

It also validates that each declared pipeline has `warmup_window ≥ pipeline.required_window()` on every OHLCV source it depends on, so live strategies don't silently emit NaN columns until warmup.

### 3.4 Sizing & execution rules

All six rule lists are independently optional, instance-cloned, and looked up by symbol via `get_position_size(symbol)`, `get_stop_loss_rule(symbol)`, etc.

| Slot | Type | Purpose |
|---|---|---|
| `position_sizes` | `List[PositionSize]` | Sizing per symbol (fixed amount or `percentage_of_portfolio`). Required to actually place an entry order. |
| `stop_losses` | `List[StopLossRule]` | Fixed or trailing stop, optional `sell_percentage` for partial exits. Attached to the trade on entry. |
| `take_profits` | `List[TakeProfitRule]` | Same shape as stop-loss but on the upside. |
| `scaling_rules` | `List[ScalingRule]` | Pyramiding: `max_entries`, `scale_in_percentage=[…]`, per-symbol `cooldown_in_bars`. |
| `cooldowns` | `List[CooldownRule]` | Throttle whipsaw — per-symbol or portfolio-wide, side-aware (`trigger="sell"`, `blocks="buy"`, `bars=12`). Enforced bar-for-bar by **both** engines via a shared `CooldownTracker`. |
| `trading_costs` | `List[TradingCost]` | Per-symbol fee / slippage / fixed cost. Applied at fill time by both engines. Note: the *runtime* `TradingCost` list is not persisted into the on-disk `ExecutionConfig`; the study's `SlippageModel` / `CommissionModel` / `FillModel` are the authoritative on-disk cost record. See [`open_backtest_format.md`](open_backtest_format.md) §Execution config structure. |

### 3.5 Pipeline & routing controls

The v9 `TradingStrategy` also carries three slots that customise the phase pipeline itself. These are set once on the class (or per-instance in `__init__`) and rarely need to change:

| Slot | Type | Default | Purpose |
|---|---|---|---|
| `phases` | `List[StrategyPhase]` | `None` (framework default sequence) | Ordered list of phases the base `run_strategy` walks. Override to insert custom phases, drop the risk-budget step, or reorder. The default sequence is documented in §3.7. |
| `conflict_policy` | `ConflictPolicy` | `ConflictPolicy.default()` (RAISE on same-symbol clash) | How `ResolveConflictsPhase` reconciles multiple signals on the same symbol / side on the same bar. |
| `executor` | `Executor` | `LimitOrderExecutor` | Order routing strategy. `EmitOrdersPhase` calls the executor to turn resolved, sized signals into actual `Order` objects. Swap for `MarketOrderExecutor`, a broker-specific adapter, or a custom implementation. |

### 3.6 Signal surface

In v9.0 the six method surface (`generate_buy_signals`, `generate_sell_signals`, `generate_scale_in_signals`, `generate_scale_out_signals`, `generate_short_signals`, `generate_cover_signals`) was replaced by **two** methods that yield structured `Signal` / `SignalSeries` objects:

| Method | Called by | Yields | Purpose |
|---|---|---|---|
| `generate_signals(context, data)` | event backtest + live | `Iterable[Signal]` | Called once per bar. Each `Signal` carries a `SignalSide` (`OPEN_LONG`, `CLOSE_LONG`, `OPEN_SHORT`, `CLOSE_SHORT`), a `symbol`, an optional `strength` (used for top-N ranking when capital binds), and optional `source` / `metadata` fields. Yielding lazily is recommended for cross-sectional strategies with many symbols. |
| `generate_signal_series(data)` | vector backtest | `Iterable[SignalSeries]` | Called *once* by `VectorBacktestService` with the full window materialised. Each `SignalSeries` is a bar-indexed boolean series for a single `(symbol, side)` pair; the vector engine walks the master timeline and fires the side wherever the series is truthy. |
| `generate_recorded_values(data)` | vector backtest | `Dict[str, pd.Series]` | Optional. Record arbitrary indicator time-series for post-hoc analysis; the vector equivalent of `context.record()` in the event loop. |

Both signal methods default to yielding nothing on the base class. Override the one you need for the engine you'll run on. Strategies that will *only* run event / live can leave `generate_signal_series` untouched; strategies that will *only* run in the vector backtest can leave `generate_signals` untouched. The vector engine raises a clear `OperationalException` when `generate_signal_series` was not overridden.

**Building signals from indicator columns.** The helpers in `investing_algorithm_framework.domain.models.signal_helpers` are the canonical bridge from a pandas/polars frame to a `Signal` / `SignalSeries`:

- `signals_from_column(df, column, side, symbol, ...)` — event mode; yields one `Signal` per truthy row in `column`.
- `signals_from_panel(panel, column, side, strength_column=...)` — event mode, cross-sectional; yields one `Signal` per truthy row of a symbol-panel frame.
- `signal_series_from_column(df, column, side, symbol, source=...)` — vector mode; wraps the whole boolean column as a `SignalSeries`.

**Signal side vocabulary.** `SignalSide` covers all four broker order actions in one enum: `OPEN_LONG` (BUY-to-open), `CLOSE_LONG` (SELL-to-close), `OPEN_SHORT` (SELL-to-open), `CLOSE_SHORT` (BUY-to-cover). Scale-in / scale-out are expressed as additional `OPEN_LONG` / `CLOSE_LONG` signals on an already-open position — governed by any attached `ScalingRule`. There is no separate scale-in / scale-out method.

**Invariant — one direction per symbol at a time.** Per symbol the engine keeps at most one open position direction. While a short is open, `OPEN_LONG` signals are ignored; while a long is open, `OPEN_SHORT` signals are ignored. `ResolveConflictsPhase` gates this uniformly across engines.

### 3.7 Lifecycle: the phase pipeline

`run_strategy(context, data)` is a small orchestrator the engines call each scheduled tick. On the base class it is intentionally tiny: it constructs a `PhaseState`, hands it to each phase in `self.phases` in turn, and returns. All trading behaviour lives in the phases:

| Phase | Responsibility |
|---|---|
| `CollectSignalsPhase` | Calls `generate_signals(context, data)` and materialises the yielded iterable into a concrete signal list on the phase state. |
| `ResolveConflictsPhase` | Applies `conflict_policy` to same-symbol / same-side clashes, enforces the one-direction-per-symbol invariant, and drops signals that violate active cooldowns. |
| `SizePositionsPhase` | Looks up the applicable `PositionSize` for each surviving signal and computes the target amount. |
| `ApplyRiskBudgetPhase` | Applies portfolio-level risk constraints (e.g. max concurrent exposure) and may downsize or drop signals. |
| `EmitOrdersPhase` | Hands each sized signal to the strategy's `executor` to produce concrete `Order` objects on the portfolio. |
| `AttachRiskRulesPhase` | Attaches the applicable `StopLossRule` / `TakeProfitRule` / `ScalingRule` records to newly-opened trades. |
| `RecordCooldownPhase` | Advances the `CooldownTracker` and records any cooldown triggers fired by this bar's fills, so subsequent bars honour them. |

Strategies that want to customise behaviour should:

- Override `generate_signals` to emit different `Signal` instances (the most common case).
- Override `conflict_policy` to change how same-symbol signal clashes are resolved (default: `RAISE`).
- Override `executor` to swap order routing (default: `LimitOrderExecutor`; ship a `MarketOrderExecutor` for market orders).
- Override `phases` to add / remove / reorder phases. Rare, but supported.

Users almost never need to override `run_strategy` itself — the default implementation is sufficient for every strategy in `examples/`.

### 3.8 Parameters

`set_parameters(dict)` stores a JSON-clean copy of constructor hyperparameters; `get_parameters()` returns them. The backtest bundle writer persists these on `Backtest.parameters`, which is what makes parameter sweeps + ranking work without bespoke serialisation per strategy.

## 4. Composition patterns

### 4.1 Minimal strategy (event / live)

```python
from investing_algorithm_framework import (
    TradingStrategy, Schedule, TimeUnit, DataSource, DataType,
    PositionSize, Signal, SignalSide, signals_from_column,
)


class MinimalStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.HOUR)
    symbols = ["BTC/EUR"]
    data_sources = [DataSource("BTC/EUR", "1h", DataType.OHLCV, warmup_window=200)]
    position_sizes = [PositionSize(symbol="BTC/EUR", percentage_of_portfolio=100)]

    def generate_signals(self, context, data):
        df = data["BTC/EUR_1h"]
        df["above_ma"] = df["Close"] > df["Close"].rolling(50).mean()
        df["below_ma"] = df["Close"] < df["Close"].rolling(50).mean()
        yield from signals_from_column(
            df, "above_ma", side=SignalSide.OPEN_LONG, symbol="BTC/EUR",
        )
        yield from signals_from_column(
            df, "below_ma", side=SignalSide.CLOSE_LONG, symbol="BTC/EUR",
        )
```

### 4.2 Minimal strategy (vector backtest)

Same class, add `generate_signal_series` for the batched engine:

```python
from investing_algorithm_framework import (
    SignalSide, signal_series_from_column,
)


class MinimalStrategy(TradingStrategy):
    # ... same slots as above ...

    def generate_signal_series(self, data):
        df = data["BTC/EUR_1h"]
        df["above_ma"] = df["Close"] > df["Close"].rolling(50).mean()
        df["below_ma"] = df["Close"] < df["Close"].rolling(50).mean()
        yield signal_series_from_column(
            df, "above_ma", side=SignalSide.OPEN_LONG, symbol="BTC/EUR",
        )
        yield signal_series_from_column(
            df, "below_ma", side=SignalSide.CLOSE_LONG, symbol="BTC/EUR",
        )
```

The class runs unchanged in vector, event, and live mode — the engine chooses which method to call.

### 4.3 Long-only with risk rules

Add `stop_losses`, `take_profits`, `cooldowns`, `trading_costs`. No signal-method changes required — `AttachRiskRulesPhase` and `ResolveConflictsPhase` pick up the rules automatically.

### 4.4 Pyramiding (scale-in / scale-out)

1. Add a `ScalingRule(symbol=…, max_entries=3, scale_in_percentage=[50, 25])`.
2. Continue yielding `OPEN_LONG` signals as normal — `ResolveConflictsPhase` recognises the additional `OPEN_LONG` on an already-open position as a scale-in when a `ScalingRule` is attached.
3. Yield `CLOSE_LONG` with a `strength` field to control the partial-close fraction, or attach a `StopLossRule` with `sell_percentage=25` for rule-driven scale-out.

### 4.5 Cross-sectional / factor strategy

1. Define a `Pipeline` subclass with `Factor` / `Filter` class attributes (see [`pipeline-api.md`](pipeline-api.md)).
2. Set `pipelines = [MyPipeline]` and provide a `universe`.
3. In `generate_signals` read `data["MyPipeline"]` as a tidy `pl.DataFrame` and yield signals via `signals_from_panel(...)` with a `strength_column` for top-N ranking downstream.

### 4.6 Long + short

Yield `OPEN_SHORT` / `CLOSE_SHORT` alongside `OPEN_LONG` / `CLOSE_LONG` from the same `generate_signals` (or `generate_signal_series`) method. The one-direction-per-symbol invariant is enforced by `ResolveConflictsPhase`; the executor and blotter handle the actual short-side accounting. `Trade.is_short` is a first-class field on the persisted trade so post-hoc analysis can partition by direction.

```python
def generate_signals(self, context, data):
    for sym in self.symbols:
        df = data[f"{sym}_1h"]
        if bullish_flip(df) and confirmation(df):
            yield Signal(symbol=sym, side=SignalSide.OPEN_LONG)
        if bearish_flip(df) and confirmation(df):
            yield Signal(symbol=sym, side=SignalSide.OPEN_SHORT)
```

See [`examples/tutorial/strategies/supertrend_ema_confirmation/strategy.py`](../../examples/tutorial/strategies/supertrend_ema_confirmation/strategy.py) for a worked example with symmetric SuperTrend + EMA + RSI/Bollinger guardrails.

### 4.7 Scheduled side-functions

```python
class RebalancingStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.DAY)
    scheduled_functions = [
        ScheduledFunction(name="rebalance",
                          schedule=Schedule.on(MonthEnd(), Time(16, 0))),
    ]

    def rebalance(self, context, data):
        ...
```

The `rebalance` method fires on its own schedule, independent of the main `run_strategy` cadence. Used heavily by cross-sectional strategies that want monthly rebalances on top of a daily signal loop.

## 5. Engine contract

The three engines all consume the *same* `TradingStrategy` instance but exercise different subsets of the surface.

| Capability | Vector | Event | Live |
|---|:-:|:-:|:-:|
| `generate_signals` | — (unused) | ✅ | ✅ |
| `generate_signal_series` | ✅ | — (unused) | — (unused) |
| `generate_recorded_values` | ✅ | — (use `context.record()`) | — |
| `OPEN_SHORT` / `CLOSE_SHORT` sides | ✅ | ✅ | ⛔ (depends on broker adapter) |
| `pipelines = [...]` | ✅ | ✅ | ✅ |
| `scheduled_functions` | ✅ | ✅ | ✅ |
| `phases` / `conflict_policy` / `executor` | ✅ | ✅ | ✅ |
| `cooldowns` / `stop_losses` / `take_profits` / `scaling_rules` | ✅ | ✅ | ✅ |

A capability marked ⛔ means *the signal is emitted but not routed*; the strategy still loads and runs on the sides the engine does route.

## 6. Per-instance state (mutable bookkeeping)

The base `__init__` initialises a small set of per-instance dicts so two instances of the same strategy class never share state:

- `_parameters` — JSON-clean hyperparameters (set via `set_parameters`).
- `_cooldown_remaining`, `_scale_out_counts` — scaling cooldown / count tracker.
- `_cooldown_tracker` (`CooldownTracker`) and `_cooldown_bar_index` — `CooldownRule` enforcement state.
- `stop_loss_rules_lookup`, `take_profit_rules_lookup`, `scaling_rules_lookup`, `position_sizes_lookup` — lazily-built per-symbol indices for O(1) lookup in the hot path.

All of this is bookkeeping the user should *never* read or write directly — it's exposed through the `get_*` helpers and the phase pipeline.

## 7. Stability & evolution

### What is stable

- The required slots: `schedule`, `data_sources`, and at least one of `generate_signals` / `generate_signal_series`.
- The signal contract: `generate_signals(context, data) -> Iterable[Signal]` and `generate_signal_series(data) -> Iterable[SignalSeries]`, both defaulting to yielding nothing on the base class.
- The `SignalSide` vocabulary: `OPEN_LONG`, `CLOSE_LONG`, `OPEN_SHORT`, `CLOSE_SHORT`.
- The phase-pipeline extension points: `phases`, `conflict_policy`, `executor`.

### What may evolve

- New optional rule-list slots (e.g. an explicit `risk_budgets` slot is on the roadmap).
- Additional phase implementations shipping with the framework — the phase list is user-overridable, so new defaults are additive.
- Broader broker support for `OPEN_SHORT` / `CLOSE_SHORT` in live mode as adapters gain short capability.

### Removed in v9.0

- The v8 six-method signal API (`generate_buy_signals`, `generate_sell_signals`, `generate_scale_in_signals`, `generate_scale_out_signals`, `generate_short_signals`, `generate_cover_signals`) was replaced by `generate_signals` / `generate_signal_series`.
- The v8 `time_unit` / `interval` pair was replaced by `Schedule`.
- The runtime `TradingCost` list is still supported for per-symbol overrides, but is no longer persisted into the on-disk bundle's `ExecutionConfig`; the study's `SlippageModel` / `CommissionModel` / `FillModel` are the authoritative on-disk cost record. See [`open_backtest_format.md`](open_backtest_format.md) §Execution config structure.

## 8. References

- [`investing_algorithm_framework/app/strategy.py`](../../investing_algorithm_framework/app/strategy.py) — implementation of `TradingStrategy`.
- [`strategy.md`](strategy.md) — architectural view of the strategy runtime.
- [`pipeline-api.md`](pipeline-api.md) — cross-sectional pipelines.
- [`../orders_and_trades/orders.md`](../orders_and_trades/orders.md), [`../orders_and_trades/trades.md`](../orders_and_trades/trades.md) — how signals turn into orders and trades.
- [`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md) — vector vs event split.
- [`open_backtest_format.md`](open_backtest_format.md) — on-disk backtest bundle format.
- [`../../examples/strategies_showcase/`](../../examples/strategies_showcase/README.md) — runnable strategy templates illustrating every composition pattern in this doc.
