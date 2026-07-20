# Strategy Composition — Design Doc

> **⚠️ Partially superseded.** This document still describes the v8 six-method signal API (`generate_buy_signals` / `generate_sell_signals` / `generate_scale_in_signals` / `generate_scale_out_signals` / `generate_short_signals` / `generate_cover_signals`). In v9.0 those six methods were **removed** and replaced by **two** methods: `generate_signals(context, data)` (event mode) and `generate_signal_series(data)` (vector mode). For the current contract, see [`../architecture/strategy.md`](../architecture/strategy.md) and §10 of [`../migration-v8-to-v9.md`](../migration-v8-to-v9.md). The rest of this document — class slots, declarative rule lists, phase pipeline — is still accurate.
>
> Status: **Historical design rationale** — kept for context on why the composition model is shaped the way it is.
> Related design docs: [`pipeline-api.md`](pipeline-api.md), [`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md), [`order-architecture.md`](order-architecture.md).

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
4. Calling its **signal generators** (`generate_buy_signals`, `generate_sell_signals`, optionally `generate_scale_in_signals`, `generate_scale_out_signals`, `generate_short_signals`, `generate_cover_signals`, `generate_recorded_values`).
5. Routing the resulting signals through the **declarative rule lists** (`position_sizes`, `stop_losses`, `take_profits`, `scaling_rules`, `cooldowns`, `trading_costs`) to produce concrete orders and trade state.

The strategy never creates orders directly in the long-only critical path — it produces signals; the engine + rules produce orders. This is what allows the *same* class to run in three modes without conditional logic.

```
        ┌────────────────────────────────────────────────────────┐
        │                   TradingStrategy                      │
        │                                                        │
  data  │  data_sources / universe / pipelines                   │
  ───►  │            │                                           │
        │            ▼                                           │
        │   generate_*_signals(data)  ────►  Dict[symbol, Series]│
        │                                          │             │
        │                                          ▼             │
  rules │  PositionSize · StopLoss · TakeProfit · Scaling ·      │
        │  Cooldown · TradingCost                                │
        │            │                                           │
        └────────────┼───────────────────────────────────────────┘
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

It also validates that each declared pipeline has `warmup_window ≥ pipeline.required_window()` on every OHLCV source it depends on (#503), so live strategies don't silently emit NaN columns until warmup.

### 3.4 Sizing & execution rules

All five rule lists are independently optional, instance-cloned, and looked up by symbol via `get_position_size(symbol)`, `get_stop_loss_rule(symbol)`, etc.

| Slot | Type | Purpose |
|---|---|---|
| `position_sizes` | `List[PositionSize]` | Sizing per symbol (fixed amount or `percentage_of_portfolio`). Required to actually place an entry order. |
| `stop_losses` | `List[StopLossRule]` | Fixed or trailing stop, optional `sell_percentage` for partial exits. Attached to the trade on entry. |
| `take_profits` | `List[TakeProfitRule]` | Same shape as stop-loss but on the upside. |
| `scaling_rules` | `List[ScalingRule]` | Pyramiding: `max_entries`, `scale_in_percentage=[…]`, per-symbol `cooldown_in_bars`. |
| `cooldowns` | `List[CooldownRule]` | Throttle whipsaw — per-symbol or portfolio-wide, side-aware (`trigger="sell"`, `blocks="buy"`, `bars=12`). Enforced bar-for-bar by **both** engines via a shared `CooldownTracker`. |
| `trading_costs` | `List[TradingCost]` | Per-symbol fee / slippage / fixed cost. The vector engine applies them on fill; the event engine plugs them into the order executor. |

### 3.5 Signal surface

The strategy expresses *intent* as Boolean Series per symbol. Each signal method returns `Dict[symbol → pd.Series[bool]]` or `None`.

| Method | Required? | Direction | Order side | Effect | Engine support |
|---|---|---|---|---|---|
| `generate_buy_signals` | **yes** | long | BUY | open long position when flat | vector + event + live |
| `generate_sell_signals` | **yes** | long | SELL | close open long position | vector + event + live |
| `generate_scale_in_signals` | no (falls back to buy) | long | BUY | add to open long position (governed by `ScalingRule`) | vector + event |
| `generate_scale_out_signals` | no (no scale-out if absent) | long | SELL | partial close of open long position | vector + event |
| `generate_short_signals` | no (off if `None`) | short | SELL-to-open | open short position when flat | **vector only** (#433) |
| `generate_cover_signals` | no (off if `None`) | short | BUY-to-cover | close open short position | **vector only** (#433) |
| `generate_recorded_values` | no | — | — | record arbitrary indicator time-series; vector equivalent of `context.record()` | vector |

**Invariant — one direction per symbol at a time.** Per symbol the engine keeps at most one open position direction. While a short is open, long BUY / scale-in signals are ignored; while a long is open, SHORT signals are ignored. The vector engine gates this explicitly; the event engine simply doesn't yet route the short methods.

**Why `short` + `cover` and not `long_buy` / `short_buy`.** The four method names map 1:1 onto the four broker order actions (BUY / SELL / SHORT / COVER) used by IB, Alpaca, Zipline, QuantConnect etc. Inventing symmetric names like "short_buy" would conflict with the fact that shorting *is* a sell, not a buy.

### 3.6 Lifecycle hook

`run_strategy(context, data)` is the orchestrator the engines call each scheduled tick. It is implemented on the base class and:

1. Stores `context`, reads `INDEX_DATETIME`.
2. Calls `generate_buy_signals`, `generate_sell_signals`, `generate_scale_in_signals`, `generate_scale_out_signals`.
3. Ticks down cooldown counters.
4. For each symbol: if flat → consider buy; if long → consider sell, scale-in, scale-out; in all cases consult cooldowns, position sizes, stops, take-profits.
5. The vector engine has its own bar loop in `VectorBacktestService` that *also* honours `generate_short_signals` / `generate_cover_signals` and the symmetric short-side accounting.

Users override `generate_*_signals` (and very rarely `run_strategy` itself) — the default `run_strategy` is sufficient for almost every strategy in `examples/`.

### 3.7 Parameters

`set_parameters(dict)` stores a JSON-clean copy of constructor hyperparameters; `get_parameters()` returns them. The backtest bundle writer persists these as `parameters.json`, which is what makes parameter sweeps + dashboard ranking work without bespoke serialisation per strategy.

## 4. Composition patterns

### 4.1 Minimal strategy

```python
class MinimalStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.HOUR)
    symbols = ["BTC/EUR"]
    data_sources = [DataSource("BTC/EUR", "1h", DataType.OHLCV, warmup_window=200)]
    position_sizes = [PositionSize(symbol="BTC/EUR", percentage_of_portfolio=100)]

    def generate_buy_signals(self, data):
        df = data["BTC/EUR_1h"]
        return {"BTC/EUR": df["Close"] > df["Close"].rolling(50).mean()}

    def generate_sell_signals(self, data):
        df = data["BTC/EUR_1h"]
        return {"BTC/EUR": df["Close"] < df["Close"].rolling(50).mean()}
```

### 4.2 Long-only with risk rules

Add `stop_losses`, `take_profits`, `cooldowns`, `trading_costs`. No signal-method changes required — the engines pick up the rules via the lookup helpers.

### 4.3 Pyramiding (scale-in / scale-out)

1. Add a `ScalingRule(symbol=…, max_entries=3, scale_in_percentage=[50, 25])`.
2. Optionally override `generate_scale_in_signals` (defaults to `generate_buy_signals`).
3. Optionally override `generate_scale_out_signals` for partial exits.

### 4.4 Cross-sectional / factor strategy

1. Define a `Pipeline` subclass with `Factor` / `Filter` class attributes (see [`pipeline-api.md`](pipeline-api.md)).
2. Set `pipelines = [MyPipeline]` and provide a `universe`.
3. In `run_strategy` (or signal methods) read `data["MyPipeline"]` as a tidy `pl.DataFrame`.

### 4.5 Long + short (vector backtests)

1. Override `generate_short_signals` and `generate_cover_signals` — both must return non-`None` dicts.
2. The vector engine routes SELL-to-open / BUY-to-cover, credits/debits cash symmetrically with longs, and persists `Trade.is_short = True` (now a first-class DB column, not a metadata flag).
3. Long signals continue to behave as before; no other slot is affected.

A typical mirror-image pattern:

```python
def generate_short_signals(self, data):
    if not self.enable_shorting:
        return None
    return {sym: bearish_flip(data[sym]) & confirmation(data[sym])
            for sym in self.symbols}

def generate_cover_signals(self, data):
    if not self.enable_shorting:
        return None
    return {sym: bullish_flip(data[sym]) & confirmation(data[sym])
            for sym in self.symbols}
```

See [`examples/tutorial/strategies/supertrend_ema_confirmation/strategy.py`](../../examples/tutorial/strategies/supertrend_ema_confirmation/strategy.py) for a worked example with symmetric SuperTrend + EMA + RSI/Bollinger guardrails.

### 4.6 Scheduled side-functions

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
| `generate_buy_signals` / `generate_sell_signals` | ✅ | ✅ | ✅ |
| `generate_scale_in_signals` / `generate_scale_out_signals` | ✅ | ✅ | ✅ |
| `generate_short_signals` / `generate_cover_signals` | ✅ | ✅ (#434) | ⛔ (#433 phase 3) |
| `generate_recorded_values` | ✅ | — (use `context.record()`) | — |
| `pipelines = [...]` | ✅ (#502) | ✅ (#501) | ✅ (#503) |
| `scheduled_functions` | ✅ | ✅ | ✅ |
| `cooldowns` / `stop_losses` / `take_profits` | ✅ | ✅ | ✅ |

A capability marked ⛔ means *the signal method is allowed but the engine ignores it*; the strategy still loads and runs in long-only mode.

## 6. Per-instance state (mutable bookkeeping)

The base `__init__` initialises a small set of per-instance dicts so two instances of the same strategy class never share state:

- `_parameters` — JSON-clean hyperparameters (set via `set_parameters`).
- `_cooldown_remaining`, `_scale_out_counts` — scaling cooldown / count tracker.
- `_cooldown_tracker` (`CooldownTracker`) and `_cooldown_bar_index` — `CooldownRule` enforcement state.
- `stop_loss_rules_lookup`, `take_profit_rules_lookup`, `scaling_rules_lookup`, `position_sizes_lookup` — lazily-built per-symbol indices for O(1) lookup in the hot path.

All of this is bookkeeping the user should *never* read or write directly — it's exposed through the `get_*` helpers and the rule engine.

## 7. Stability & evolution

### What is stable

- The four required slots: `schedule`, `symbols` (when using signals), `data_sources`, signal methods.
- The signature `generate_*_signals(self, data) -> Dict[str, pd.Series] | None`.
- The order-action vocabulary: BUY / SELL / SHORT / COVER.

### What may evolve

- New optional rule-list slots (e.g. an explicit `risk_budgets` slot is on the roadmap).
- New optional signal generators always introduced as `Optional[…]` returning `None` to preserve long-only behaviour by default. Short selling (#433) is the canonical example.
- The event engine and live trading will gain short support in phases 2 and 3 of #433; the signal API is forward-compatible.

### Deprecations

- v8 `time_unit` / `interval` → removed in v9.0 in favour of `Schedule`.
- `Trade.is_short` was previously a `metadata_json` flag → promoted to a first-class DB column with a forward-only migration (#433).

## 8. References

- [`investing_algorithm_framework/app/strategy.py`](../../investing_algorithm_framework/app/strategy.py) — implementation of `TradingStrategy`.
- [`pipeline-api.md`](pipeline-api.md) — cross-sectional pipelines.
- [`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md) — vector vs event split and bundle format.
- [`order-architecture.md`](order-architecture.md) — how signals turn into orders and trades.
- [`examples/strategies_showcase/`](../../examples/strategies_showcase/README.md) — runnable strategy templates illustrating every composition pattern in this doc.
