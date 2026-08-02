# Strategy architecture

This document describes the v9.0 strategy API: the contract a
`TradingStrategy` exposes to the framework, what runs it, and why
the signal surface is split into **two distinct methods** —
`generate_signals` (event mode) and `generate_signal_series`
(vector mode). For the surrounding execution context see
[`event_loop.md`](event_loop.md); for what happens *after* a
signal is produced see [`orders.md`](orders.md) and
[`trades.md`](trades.md).

---

## 1. Mental model

A `TradingStrategy` is a small object that the framework drives in
one of two execution modes:

```
                     ┌────────────────────────────────┐
                     │       TradingStrategy          │
                     │                                │
                     │  generate_signals(ctx, data)   │◄── event   (app.run_backtest, paper, live)
                     │  generate_signal_series(data)  │◄── vector  (app.run_vector_backtest)
                     │                                │
                     │  + class-level slots:          │
                     │    position_sizes,             │
                     │    stop_losses, take_profits,  │
                     │    scaling_rules, cooldowns,   │
                     │    trading_costs               │
                     └────────────────────────────────┘
```

Strategies declare **intent** (where they want to be long / short)
and **rules** (how to size, when to bail out). They do **not**
place orders directly in the common case — the engine resolves
signals through the rule lists and into orders via the
**eight-phase pipeline**
(`Evaluate → Collect → Resolve → Size → Budget → Emit → AttachRisk → RecordCooldown`)
described in §4.

---

## 2. The two signal methods

### 2.1 Signatures

```python
class TradingStrategy:
    def generate_signals(
        self, context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        """Event mode: one bar = one decision."""
        return iter(())

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        """Vector mode: declare intent over the whole window."""
        return iter(())
```

Both default to `iter(())`, so a strategy only overrides the
method(s) corresponding to the modes it supports.

### 2.2 Side-by-side

| Aspect | `generate_signals` (event) | `generate_signal_series` (vector) |
|---|---|---|
| Triggered by | `app.run_backtest`, paper, live | `app.run_vector_backtest` |
| Called per backtest | once **per scheduled tick** | **once total**, before simulation |
| `context` parameter | yes — portfolio, positions, cash, open orders | **no** — that state doesn't exist yet |
| `data["<id>"]` shape | dataframe truncated to `now` | dataframe covering the **entire window** |
| Returns | `Iterable[Signal]` — zero or one decision for the latest bar | `Iterable[SignalSeries]` — one series per side covering all bars |
| Helper | `signals_from_column` (reads `df.iloc[-1]`) | `signal_series_from_column` (keeps the whole column) |
| Performance | Python-per-bar | strategy runs **once**, simulation loop is pure pandas/numpy |
| Lookahead safety | structural — frame is already truncated | structural — bar `i` action is a function of row `i` only |

### 2.3 Why two methods instead of one

The split is deliberate. Three reasons:

1. **No `context` exists in vector mode.** Vector mode runs the
   strategy callback once, *before* any simulation. The portfolio
   doesn't exist yet — positions, cash, open orders all emerge as
   the engine plays back the declared signals. There is nothing
   meaningful to pass in for `context`. The engine enforces the
   "no SCALE_IN without a position", "no OPEN_LONG when already
   long" etc. invariants in `ResolveConflictsPhase` after the
   fact, on a per-bar basis.

2. **Performance is the whole point of vector mode.** Vector mode
   is 10-100× faster than event mode for one reason: the
   user-supplied Python runs **once** and produces precomputed
   boolean columns. The bar-by-bar simulation that follows is
   pure C-level pandas/numpy + the engine's order matching. If
   `generate_signals(context, data)` were called per bar in
   vector mode you would lose this immediately.

3. **Lookahead-bias containment.** In event mode the dataframe
   naturally only contains bars ≤ now. In vector mode the
   strategy is handed the entire window. By forcing intent
   through *columns* — each row representing a self-contained
   decision — the engine guarantees structurally that bar `i`'s
   action is a function of row `i` only. Lookahead leaks become
   the user's narrow responsibility (don't use `shift(-1)` in
   your features) instead of an engine-wide footgun.

### 2.4 What both methods share

The two helpers (`signals_from_column` and
`signal_series_from_column`) are deliberately symmetric so a
strategy can write **one** feature-engineering pass and feed the
same boolean column into either helper depending on the mode.
Event mode just slices `df.iloc[-1]`; vector mode keeps the whole
column. That's the only difference at the seam.

See `examples/machine_learning_enabled_strategy/strategy.py` for a
strategy that implements both methods over a shared `_predict()`
helper.

### 2.5 When to override which

| Use case | Override |
|---|---|
| Only running vector backtests | `generate_signal_series` only |
| Only running live / paper / event backtests | `generate_signals` only |
| Same strategy must work in every mode | both — share the feature/prediction code |
| Portfolio-state-dependent decisions (e.g. "size relative to remaining cash *during* the decision") | `generate_signals` — vector mode cannot see live cash, only post-hoc allocation via `SignalSeries.strength_series` |

### 2.6 Validation

`app.run_vector_backtest(...)` calls
`validate_strategy_for_vector_backtest(strategy)` before doing any
work. The validator uses a class-identity check:

```python
own_method  = type(strategy).generate_signal_series
base_method = TradingStrategy.generate_signal_series
if own_method is base_method:
    raise OperationalException(
        "Strategy does not override generate_signal_series — "
        "vector backtest cannot run."
    )
```

Event mode has no equivalent check; an unoverridden
`generate_signals` simply emits no signals, which is sometimes the
right thing (e.g. a strategy that only reacts to scheduled
functions).

---

## 3. The `Signal` and `SignalSeries` types

### 3.1 `Signal` (event mode)

```python
@dataclass
class Signal:
    symbol: str
    side: SignalSide
    source: str = ""
    strength: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

One `Signal` represents one decision at one timestamp. The engine
attaches `INDEX_DATETIME` (the iteration's wall-clock time)
implicitly.

### 3.2 `SignalSeries` (vector mode)

```python
@dataclass
class SignalSeries:
    symbol: str
    side: SignalSide
    series: pd.Series                  # boolean, aligned with the OHLCV frame
    source: str = ""
    strength_series: Optional[pd.Series] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

`series` is the per-bar boolean column. `strength_series`, when
present, is used by `SizePositionsPhase` for ranking-aware sizing
in cross-sectional strategies.

### 3.3 `SignalSide`

```
OPEN_LONG     CLOSE_LONG
SCALE_IN      SCALE_OUT
OPEN_SHORT    CLOSE_SHORT
```

These map to `Order.order_side` + `order_reason` via the
`_ORDER_REASON` table in `services/strategy_phases/size_positions.py`.
Strategies emit `SignalSide`; the engine never asks them to think
in terms of BUY/SELL.

---

## 4. Phase pipeline (what happens to a signal)

Every signal the strategy emits — in **either** mode — is shepherded
through the same ordered sequence of `StrategyPhase` objects before
it becomes an `Order`. The pipeline is the single source of truth
for the rules the engine applies between *intent* and *fill*: which
signals to drop, how much to size, how to fit into the available
cash budget, what risk rules to attach, and how to arm cooldowns
afterwards. Event mode runs the pipeline once per tick; vector mode
runs an equivalent collapsed version once per bar inside the
simulation loop.

### 4.1 Pipeline shape

```
generate_signal[_series]
        │
        ▼
┌─────────────────────────────────┐
│ 0. EvaluatePipelinesPhase       │  materialise factor frames from
│                                 │  strategy.pipelines (universe-refresh
│                                 │  cache, live-mode resilience)
├─────────────────────────────────┤
│ 1. CollectSignalsPhase          │  tick cooldown counters, advance
│                                 │  bar index, gather strategy +
│                                 │  Pipeline.to_signals() emissions
├─────────────────────────────────┤
│ 2. ResolveConflictsPhase        │  drop disabled sides → open-order
│                                 │  gate → state gate → cooldown gate
│                                 │  → per-symbol ConflictPolicy
│                                 │  arbitration (mutex + tie-break)
├─────────────────────────────────┤
│ 3. SizePositionsPhase           │  PositionSize / ScalingRule arithmetic
│                                 │  → base-currency amount; sort opens
│                                 │  by Signal.strength desc for top-N
├─────────────────────────────────┤
│ 4. ApplyRiskBudgetPhase         │  proportionally scale cash-consuming
│                                 │  intents (OPEN_LONG / SCALE_IN) to
│                                 │  fit context.get_unallocated();
│                                 │  drops intents below 0.01 quote
├─────────────────────────────────┤
│ 5. EmitOrdersPhase              │  dispatch each SizedIntent through
│                                 │  strategy.executor (default:
│                                 │  LimitOrderExecutor)
├─────────────────────────────────┤
│ 6. AttachRiskRulesPhase         │  push StopLossRule / TakeProfitRule
│                                 │  onto every freshly-emitted opening
│                                 │  order (OPEN_LONG, SCALE_IN,
│                                 │  OPEN_SHORT); rules are materialised
│                                 │  onto each fill-time trade
├─────────────────────────────────┤
│ 7. RecordCooldownPhase          │  arm cooldown windows from emitted
│                                 │  fills, scan for system-exit fills
│                                 │  (TP / SL closes) and arm those
│                                 │  cooldowns too, update scale-out
│                                 │  counters
└─────────────────────────────────┘
        │
        ▼
   Order in book / fill
```

The canonical ordering lives in
[`services/strategy_phases/default.py`](../../investing_algorithm_framework/services/strategy_phases/default.py)
as `DEFAULT_PHASES`. `TradingStrategy.__init__` calls
`build_default_phases()` when the user hasn't supplied a custom
`phases = [...]` override.

### 4.2 Per-phase contract

Every phase is a subclass of `StrategyPhase` with the signature:

```python
class StrategyPhase:
    name: str

    def run(self, state: PhaseState) -> None:
        ...
```

`PhaseState` is the mutable per-iteration scratchpad threaded
through the pipeline. The relevant fields (see
[`phase_state.py`](../../investing_algorithm_framework/services/strategy_phases/phase_state.py)):

| Field | Populated by | Consumed by |
|---|---|---|
| `strategy`, `context`, `data` | pipeline driver | every phase |
| `bar_index` | `CollectSignalsPhase` | `RecordCooldownPhase` |
| `pipeline_outputs` | `EvaluatePipelinesPhase` | `CollectSignalsPhase`, user pipelines |
| `raw_signals: list[Signal]` | `CollectSignalsPhase` | `ResolveConflictsPhase` |
| `approved_signals: list[Signal]` | `ResolveConflictsPhase` | `SizePositionsPhase` |
| `sized_intents: list[SizedIntent]` | `SizePositionsPhase`, `ApplyRiskBudgetPhase` | `EmitOrdersPhase` |
| `emitted_orders: list[EmittedOrder]` | `EmitOrdersPhase` | `AttachRiskRulesPhase`, `RecordCooldownPhase` |

A phase is free to mutate any field it owns; downstream phases
read the result. Phases are stateless by default — any
per-iteration memory should live on `PhaseState`; any
per-strategy memory (cooldown trackers, scale-out counters,
pipeline universe caches) lives on the parent `TradingStrategy`.

### 4.3 Phase-by-phase semantics

**Phase 0 — `EvaluatePipelinesPhase`**
Walks `strategy.pipelines`, calls each pipeline's compute step,
and writes the resulting frames into `state.pipeline_outputs`
keyed by the pipeline class name. Honours
`Pipeline.refresh_universe_every` cadence via a per-strategy
cache. In live / paper mode a single pipeline exception is logged
and the iteration continues with an empty output; in backtest
mode it raises. This phase exists so the eventloop no longer
contains strategy-shaped logic.

**Phase 1 — `CollectSignalsPhase`**
Performs the per-iteration bookkeeping that used to live at the
top of the legacy `run_strategy`:

- Decrements `strategy._cooldown_remaining[symbol]` by 1; drops
  zero entries.
- Increments `strategy._cooldown_bar_index` and writes it to
  `state.bar_index`.

Then collects signals from two sources, merging into
`state.raw_signals`:

1. `strategy.generate_signals(context, data)` — the user-facing
   hook.
2. `Pipeline.to_signals(...)` for every pipeline that overrides
   the default empty implementation (issue #503).

**Phase 2 — `ResolveConflictsPhase`**
The hardest-working phase. Drops signals through five filters in
order:

1. **Disabled-side drop** — sides listed in
   `ConflictPolicy.disabled_sides` are removed up front (no I/O).
2. **Open-order gate** — when
   `ConflictPolicy.block_when_open_order` is `True` (the default),
   any symbol with a pending order has all its signals dropped.
3. **State gate** — sides whose preconditions aren't met are
   dropped: `OPEN_LONG` while long, `SCALE_IN` without a position,
   `CLOSE_SHORT` with no open short trade, etc. Each drop emits a
   `signal_event` with a reason (`already_in_position`,
   `open_short_position`, `no_position_to_close`, ...) so users
   can see *why* a signal was rejected.
4. **Cooldown gate** — checks both `_cooldown_remaining` (legacy
   per-symbol counter) and the `CooldownTracker` (rule-driven
   trigger/blocks pairs). Rejects emit `reason="cooldown"`.
5. **Per-symbol arbitration** — `ConflictPolicy.resolve` enforces
   direction mutex (long vs short on the same symbol) and
   priority / strength tie-breaking when multiple signals survive
   for the same symbol-side.

Survivors are written, ordered by priority then strength desc,
to `state.approved_signals`.

**Phase 3 — `SizePositionsPhase`**
Converts each approved `Signal` into a `SizedIntent`:

- `OPEN_LONG` / `OPEN_SHORT` — `PositionSize.get_size()` (quote
  currency) ÷ latest price = base amount.
- `SCALE_IN` — base size × per-entry scaling percentage, clamped
  to `max_position_percentage` headroom.
- `CLOSE_LONG` — full position amount.
- `CLOSE_SHORT` — sum of `available_amount` over open short
  trades.
- `SCALE_OUT` — current position amount × scale-out percentage.

When more opening intents exist than the risk budget can fund,
opens are sorted by `Signal.strength` descending so
`ApplyRiskBudgetPhase` can preserve the highest-conviction names.
This phase only sorts; the actual cash-fit happens in Phase 4.
Each `SizedIntent` carries an `order_reason` tag derived from a
fixed `SignalSide → reason` map so downstream code can identify
*why* the order was placed.

**Phase 4 — `ApplyRiskBudgetPhase`**
Proportionally scales cash-consuming intents (`OPEN_LONG`,
`SCALE_IN`) when their combined notional exceeds
`context.get_unallocated()`. Closes (`CLOSE_LONG`, `CLOSE_SHORT`,
`SCALE_OUT`) and short opens are **never** scaled here — closes
must always be free to fire, short opens credit cash rather than
debit it. Intents scaled below the 0.01 quote-currency minimum
execution threshold are dropped with a warning. Because Phase 3
pre-sorted opens by `Signal.strength`, stronger signals retain
fuller size when the scaling factor bites.

**Phase 5 — `EmitOrdersPhase`**
Dispatch-free: each `SizedIntent` is passed through
`strategy.executor.execute(intent, context, metadata)`. The
default `LimitOrderExecutor` reproduces legacy behaviour (limit
orders pegged at the signal-bar price). Users swap LIMIT /
MARKET / bracket / OCO / iceberg behaviour by setting a different
executor on the strategy — the pipeline itself doesn't change.
Successful emissions are appended to `state.emitted_orders` as
`EmittedOrder` records (intent + order + executor metadata).

**Phase 6 — `AttachRiskRulesPhase`**
For every emitted opening order
(`OPEN_LONG`, `SCALE_IN`, `OPEN_SHORT`) the phase pushes any
configured `StopLossRule` / `TakeProfitRule` onto the order via
`Context.add_stop_loss` / `Context.add_take_profit`. The
framework's trade-creation path then materialises the rule onto
every trade produced at fill time, with `is_short=True` carried
through for short opens. Each `SCALE_IN` fill creates its own
trade with its own rule, mirroring legacy behaviour.

**Phase 7 — `RecordCooldownPhase`**
Final bookkeeping after orders are out the door:

- Arms cooldown windows on the `CooldownTracker` from every
  emitted fill (both user signals and system exits).
- Scans for **system-exit fills** (TP / SL closes flagged with
  `metadata.order_reason in {"take_profit", "stop_loss"}` and
  `created_at > strategy._last_system_exit_scan_at`). These
  weren't approved through `ResolveConflictsPhase` but still
  need to arm cooldowns so the next entry waits the configured
  bars. Advances the watermark to prevent double-counting.
- Increments `strategy._scale_out_counts` on `SCALE_OUT`
  emissions; clears the counter on `CLOSE_LONG` (full exit).
- Decrements per-symbol `_cooldown_remaining` for any explicit
  legacy cooldown that was armed this iteration.

### 4.4 Customising the pipeline

`TradingStrategy.phases` is a list of phase **instances**. You
can:

- **Replace one phase** — subclass it and substitute:
  ```python
  class MyStrategy(TradingStrategy):
      phases = [
          EvaluatePipelinesPhase(),
          CollectSignalsPhase(),
          MyCustomResolveConflicts(),   # ← replaces default
          SizePositionsPhase(),
          ApplyRiskBudgetPhase(),
          EmitOrdersPhase(),
          AttachRiskRulesPhase(),
          RecordCooldownPhase(),
      ]
  ```
- **Insert a phase** — e.g. a custom logging or telemetry phase
  between Emit and AttachRisk.
- **Remove a phase** — e.g. drop `ApplyRiskBudgetPhase` if your
  strategy hand-sizes everything and you want opens to fail loudly
  on insufficient cash rather than scale silently.

See [`pipeline-api.md`](pipeline-api.md) for the full
contract and worked examples.

### 4.5 Vector mode equivalence

Vector mode doesn't run `StrategyPhase` objects literally — it runs
a single pass over precomputed boolean columns inside
`VectorBacktestService._simulate`. But the *order of checks* per
bar mirrors the phase pipeline so behaviour stays consistent:

| Pipeline phase | Vector-loop equivalent |
|---|---|
| Phase 0 — Evaluate pipelines | not applicable (pipelines are factor frames; computed pre-loop in `generate_signal_series`) |
| Phase 1 — Collect signals | the `buy_signal` / `sell_signal` / `short_signal` / `cover_signal` columns produced by `generate_signal_series` |
| Phase 2 — Resolve conflicts | per-bar `is_buy and not has_position`, `is_short_sig and not has_position`, `not in_cooldown` gates (see `vector_backtest_service.py` lines ~1080–1280); rejected signals append to `signal_events` with the same reasons as the event engine |
| Phase 3 — Size positions | inline `position_size.get_size()` call per accepted open |
| Phase 4 — Apply risk budget | inline cash check against `portfolio.unallocated` |
| Phase 5 — Emit orders | direct `_open_long_position` / `_open_short_position` / `_close_*` calls |
| Phase 6 — Attach risk rules | TP / SL columns precomputed from `take_profit_percentage` / `stop_loss_percentage`; `_evaluate_tp_sl` triggers them inline per bar |
| Phase 7 — Record cooldown | `CooldownTracker.arm()` called after each fill, including TP / SL system exits |

This is why a strategy can be developed against vector mode for
fast iteration, then handed unchanged to the event engine for
paper / live trading — the only thing that changes is the cadence
at which the rules are enforced, not the rules themselves.

---

## 5. Where to look in the code

| Concern | File |
|---|---|
| `TradingStrategy` base class | `investing_algorithm_framework/app/strategy.py` |
| `Signal`, `SignalSeries`, `SignalSide` | `investing_algorithm_framework/domain/models/signal*.py` |
| `signals_from_column`, `signal_series_from_column` | `investing_algorithm_framework/domain/models/signal_helpers.py` |
| Phase pipeline base + state | `investing_algorithm_framework/services/strategy_phases/base.py`, `phase_state.py` |
| Default phase ordering | `investing_algorithm_framework/services/strategy_phases/default.py` |
| Individual phases | `services/strategy_phases/{evaluate_pipelines,collect_signals,resolve_conflicts,size_positions,apply_risk_budget,emit_orders,attach_risk_rules,record_cooldown}.py` |
| `ConflictPolicy`, `CooldownTracker` | `investing_algorithm_framework/domain/models/{conflict_policy,risk_rules/cooldown_rule}.py` |
| `Executor` interface + `LimitOrderExecutor` | `investing_algorithm_framework/services/executors/` |
| Vector validator | `investing_algorithm_framework/infrastructure/services/backtesting/backtest_service.py` |
| Vector simulation loop | `investing_algorithm_framework/infrastructure/services/backtesting/vector_backtest_service.py` |
| Event loop entry point | `investing_algorithm_framework/app/eventloop.py` |
| Pipeline customisation guide | `docs/architecture/strategy/pipeline-api.md` |
