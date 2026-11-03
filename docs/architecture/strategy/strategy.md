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

### Shared sizing and risk rules

`ScalingRule`, `PositionSize`, `StopLossRule` and `TakeProfitRule` accept
`symbols=[...]` to apply the same settings independently to several target
symbols. Existing `symbol="BTC"` declarations and positional arguments remain
supported.

```python
from investing_algorithm_framework import (
    PositionSize, ScalingRule, StopLossRule, TakeProfitRule,
)

targets = ["BTC", "ETH"]
position_sizes = [
    PositionSize(symbols=targets, percentage_of_portfolio=40),
]
scaling_rules = [
    ScalingRule(
        symbols=targets, max_entries=3, initial_entry_percentage=20,
        scale_in_percentage=[40, 40], cooldown_in_bars=2,
    ),
]
stop_losses = [
    StopLossRule(symbols=targets, percentage_threshold=7,
                 sell_percentage=100, trailing=True),
]
take_profits = [
    TakeProfitRule(symbols=targets, percentage_threshold=15,
                   sell_percentage=100),
]
```

Pass these lists into the strategy constructor. Each 40% position allocation
is **per symbol**, not a shared 40% allocation across the list. Scaling stages,
cooldowns and trade risk state remain independent for each symbol.

Use either `symbol` or `symbols`, not both. An explicit `symbols` list/tuple
must be non-empty and contain unique target names, not trading pairs. Names
are normalized to uppercase and stored as a tuple; duplicates after
normalization are rejected. The caller's list is not retained.
Omitting both selectors on `PositionSize` or `ScalingRule` preserves the
existing default for otherwise unconfigured symbols; an explicitly targeted
rule takes precedence over that default. Risk-rule `side`, `trailing` and
`mirror_on_exchange` settings retain their existing meaning. Existing vector
limitations still apply: trailing risk rules require event execution and
scaling uses Python rather than native vector accounting.

### Optional native indicator declarations

For a fully declarative strategy, inherit `ConfluenceScoringStrategy` and
declare indicator configs plus cards with explicit `side`, optional `symbols`,
and `scale_in_stage` for additions. Both signal hooks are provided. See
[declarative confluence strategies](confluence_cards.md#declarative-indicator-driven-strategies)
for the reference strategy, 20/40/40 sizing, cooldown semantics and execution
engine limitations. `TradingStrategy` remains the general-purpose base for
imperative strategies and retains its existing concrete-card compatibility API.

Strategies may declare `indicator_configs` and `confluence_cards` instead of
repeating indicator calculations inside `generate_signals`. Existing imperative
strategies remain unchanged: the extra `EvaluateIndicatorsPhase` is a no-op
without declarations. The default order is now pipeline evaluation → indicator
evaluation → signal collection → the existing execution phases. Custom phase
lists should insert `EvaluateIndicatorsPhase` before `CollectSignalsPhase`.

Event backtests create a fresh indicator engine for every algorithm/window.
Built-in indicators and callables explicitly declaring `execution="precompute"`
are prepared before the event loop; default per-decision callables still
receive only completed history at each decision. Live execution uses the same
phase with incrementally accumulated source history (this does not turn an
arbitrary batch function into an incremental formula).

Use the framework's `IndicatorConfig` directly. Built-in declarations support
`to_dict()` / `from_dict()` for configuration persistence; arbitrary Python
callables must be reconstructed from their code, not deserialized. A
`data_source` mapping may select identifiers by uppercase base symbol or pair.
Such a declaration requires an explicit `symbol` when passed directly to
`IndicatorEngine`; multi-symbol strategies can expand templates into concrete
per-source declarations first.
Indicator and scoring declarations retain their immutable mappings when sent
to spawned backtest workers. Callable implementations used with multiprocessing
must be importable, picklable functions; exporting built-in configurations as
JSON is separate from transferring trusted Python objects to a worker.

Use `data_sources` to apply one indicator declaration independently to
multiple sources in a `ConfluenceScoringStrategy`:

```python
indicator_configs = [
    IndicatorConfig(
        id="z_score_long",
        data_sources=["btc_2h", "eth_2h"],
        calculate=zscore,
        parameters={"source_column": "Close", "period": 14,
                    "result_column": "zscore"},
        output_columns=["zscore"],
        minimum_history=14,
        history="continuous",
        execution="precompute",
    ),
]
```

Declare/import `zscore` as the caller-provided function and register both source
identifiers in the strategy's `data_sources`. A list or tuple of `DataSource`
objects is also accepted; it references their identifiers rather than
registering new strategy sources. Each symbol gets its own history and
calculation; the callable still receives **one DataFrame**, not a collection.
Cards must include the corresponding symbols to evaluate/trade them.

Use either `data_source` or `data_sources`, not both. The explicit list must
be non-empty and contain unique, non-empty identifiers. Unknown identifiers
raise an error. Each symbol/timeframe binding must select exactly one OHLCV
source; ambiguous selections raise rather than choosing the first source.
For a standalone `IndicatorEngine`, use an explicit `symbol` (the full pair)
and, if needed, `timeframe` to disambiguate a plural selection. Multi-symbol
fan-out is provided by `ConfluenceScoringStrategy`.
Legacy `data_source=` strings, objects, mappings and positional arguments
remain supported. Built-in declarations round-trip plural identifiers through
`to_dict()` / `from_dict()`; callable declarations remain Python-only.

```python
from investing_algorithm_framework import (
    TradingStrategy, DataSource, IndicatorConfig, IndicatorRule,
    ConfluenceScoreConfig,
)

class MyStrategy(TradingStrategy):
    # Also declare the strategy's normal schedule and sizing/risk settings.
    data_sources = [DataSource(
        identifier="btc_2h", symbol="BTC/EUR", data_type="ohlcv",
        time_frame="2h", warmup_window=100,
    )]
    indicator_configs = (
        IndicatorConfig("oversold", "wilders_rsi", period=14,
                        timeframe="2h", data_source="btc_2h"),
    )
    confluence_cards = {
        "entry": ConfluenceScoreConfig(
            rules={"low_rsi": IndicatorRule(
                "oversold", threshold=30, comparison="le",
                lookback_period=3, group_weights={"entry": 2},
            )},
            group_aggregation={"entry": "sum"},
            group_thresholds={"entry": 2},
        ),
    }

    def generate_signals(self, context, data):
        evaluation = data["indicators"]
        rsi = evaluation.values["oversold"]["value"]
        qualified = evaluation.cards["entry"]["passed"]
        # Use these observations in the strategy's normal Signal generation.
        return ()
```

The phase calls `strategy.create_indicator_engine()` to construct instance-local
state. The general-purpose base returns `IndicatorEngine(configs, cards,
data_sources)`; the confluence subclass binds isolated engines per symbol.
An execution engine may instead install a fresh engine as
`strategy._indicator_engine`. `prepare({source_identifier: full_raw_frame})`
resets previous run history and caches. Built-in calculations and callable
calculations explicitly opting into precomputation are computed once; cards
depending only on these calculations are scored at native candle-completion
boundaries and selected by backward alignment. Cards involving per-decision
callables are scored afresh. `evaluate(data, as_of)` also works without
preparation, retaining completed supplied bars across rolling provider windows.
Built-ins are recomputed only when completed observations arrive. There is no
global cache; built-in aliases share computations by source, kind, timeframe
and numerical parameters, not by rule/id. Arbitrary callable declarations do
not share calculations or state implicitly.

**Caller-provided indicator functions**

Use `calculate` instead of `indicator` to control the numerical implementation.
Any compatible function can be used, including a function from an optional
third-party library; the framework does not require or substitute that library.

```python
def cumulative_range(frame, multiplier=1):
    # This example accepts pandas. A Polars source requires a compatible
    # callable (or an implementation handling both DataFrame types).
    frame["range_total"] = (frame["High"] - frame["Low"]).cumsum() * multiplier
    return frame

indicator_configs = [
    IndicatorConfig(
        id="range", data_source="btc_2h",
        calculate=cumulative_range, parameters={"multiplier": 2},
        output_columns=["range_total"], minimum_history=14,
        history="continuous",
        execution="per_decision",  # Default; called on every decision.
    ),
]
confluence_cards = [
    ConfluenceScoreConfig(
        id="entry",  # Required, unique and non-empty for list declarations.
        rules={"range_large": IndicatorRule(
            indicator_id="range", output_column="range_total",
            threshold=50, comparison="ge", lookback_period=3,
            group_weights={"entry": 1},
        )},
        group_thresholds={"entry": 1},
    ),
]
```

Callable timeframes are inferred from the exactly resolved OHLCV source unless
explicitly constrained. The function receives a defensive DataFrame copy in
the source's pandas/Polars backend, including **all original columns** (and the
Polars `Datetime` column). Its input is the accumulated completed native history
from the run origin, not just the current provider window. `parameters` are
passed as keyword arguments. It must return a pandas or Polars **DataFrame**,
not a Series, with the same timestamps, order and row count. Every declared
`output_columns` name must exist and be numeric; names are used verbatim, never
aliased to `value`. Rules must explicitly select an `output_column` declared by
the callable. Legacy built-in `output=...` rules remain supported.

`minimum_history` must be positive. Before that many completed rows exist, the
callable is not invoked and its observations are NaN/not ready. Outputs for
earlier initialization rows are also unavailable. Missing-data handling and all
other numerical initialization are the callable's responsibility; the framework
does not replace its formula. Exceptions and invalid returned schemas raise
errors identifying the indicator and source, with the original error chained.
`history="continuous"` is currently the only supported history policy.

**Execution is caller-controlled.** The default `execution="per_decision"`
invokes each callable on every decision once minimum history exists, even when
there is no newly completed candle. This remains true after `prepare`: the
function receives only the prefix completed at that decision, never the
prepared future rows. Stateful functions should use this mode. Explicitly set
`execution="precompute"` only when you, the caller, know the function is causal
and suitable for one full-history computation. The framework makes no automatic
causality or safe-precomputation claim. With preparation, such a function runs
once per fresh `prepare`; without preparation it runs when history grows.
For causal functions with the same history origin, prepared and accumulated
event evaluation have matching outputs. Access results as
`evaluation.values["range"]["range_total"]` and
`evaluation.cards["entry"]["passed"]`.

**Native contract and readiness**

* A candle timestamp is its **open**. It becomes available at open + timeframe;
  monthly/yearly candles use calendar offsets rather than fixed-day estimates.
  `as_of` must be timezone-aware; naive provider candle timestamps mean UTC.
  Supplied incomplete/future candles never affect the current observation.
* Select exactly one OHLCV source at the declared timeframe using `data_source`
  (identifier or `DataSource`), optionally constrained by `symbol`. Without an
  explicit identifier, source resolution must still be unambiguous. There is
  no implicit symbol expansion, first-symbol selection, or resampling.
* `IndicatorEvaluation.values[id]` is the latest native output mapping.
  Scalar indicators expose `value`, MACD exposes `macd`, `signal`, `histogram`,
  and stochastic exposes `k`, `d`. Multi-output rules require `output=...`.
  Comparisons are explicit `le/ge/lt/gt/eq/ne`, never inferred from rule names.
* Rule matching applies comparison **on native bars**, then rolling-any over
  the last `lookback_period` native observations, including the current bar.
  Partial lookback windows are allowed. Current output must be finite, even
  when an older bar matched; NaN/inf never matches, including `ne`.
  The default `lookback_scope="market"` includes pre-entry observations.
  Close-long/close-short rules may use `lookback_scope="position"` to exclude
  observations completed at or before the leg's first entry fill, without
  resetting continuous indicator history. See [position-scoped exits](./confluence_cards.md).
* `evaluation.ready[id]` means all that indicator's latest outputs are finite.
  `rule_readiness[card][rule]` checks its selected current output.
  `cards[card]["lookback_ready"][rule]` additionally requires a complete finite
  lookback. `cards[card]["ready"]` combines selected current readiness; it is
  diagnostic, not an extra scoring rule. `passed` is the existing card's
  qualification, with its normal group weights, sum/max aggregation, negative
  evidence, requirements/vetoes, and overrides.
* Missing **rows** are not invented or forward-filled into price data: periods
  and lookbacks count observed native rows.   For built-ins, missing numerical inputs produce
  unavailable outputs. Finite rolling windows recover after the missing value
  leaves their window; recursive indicators reset and warm up a fresh segment.
  Omitting a source on a tick retains its last known completed observation.
* Overlapping changed computation inputs, inserted old observations and
  backward `as_of` evaluations fail explicitly. Prepared engines also reject
  supplied completed bars outside their prepared history; start a fresh run or
  call `prepare` again. Input frames are never mutated.

**Indicator definitions and initialization**

| Kind | Definition / initialization |
|---|---|
| `z_score` | `(close - rolling_mean) / rolling_std`, population standard deviation (`ddof=0`); zero dispersion is unavailable |
| `willr` | `-100 * (rolling_high - close) / (rolling_high - rolling_low)` |
| `rsi` | Simple rolling average gains/losses over `period` close changes |
| `wilders_rsi` | First `period` changes seed an SMA, then Wilder recursion with alpha `1/period` |
| `ema` | First finite close seeds recursion, alpha `2/(period+1)`; hidden until `period` contiguous observations |
| `macd` | Short EMA minus long EMA; signal EMA starts at first finite MACD; histogram is MACD minus signal |
| `stochastic` | Raw `%K = 100*(close-low)/(high-low)`; `k` is its `k_slowing` SMA, `d` is the `d_period` SMA of `k` |

All outputs are multiplied by config `scale`. Zero gain and loss gives RSI 50;
positive gains with zero loss gives 100. Zero high-low ranges are unavailable.
Recursive values use the run's original accumulated history, not a reseeded
provider window, ensuring event-prefix/prepared parity.

`config.required_window(output=None)` and `engine.required_windows` expose
finite initialization requirements. RSI needs `period+1` closes, stochastic
needs `period+k_slowing+d_period-2` rows for both outputs, and MACD needs
`long_period+signal_period-1`. A rule's full lookback needs its selected
initialization plus `lookback_period-1`. Explicit source `warmup_window` below
the required maximum is rejected; reaching the count does not guarantee finite
outputs when inputs are missing. Increasing recursive warmup changes the
history origin and therefore can change its numerical values.

These native, potentially multi-output calculations are deliberately separate
from cross-sectional `Factor.compute_panel`/`Pipeline`. Scoring is not separate:
declarations compile native rule-match booleans to the existing
`ConfluenceScoreCard`. Optional requirements/vetoes use independent conditions
on named rule booleans; overrides can use existing `Rule`/`Threshold` expressions.

A `TradingStrategy` is a small object that the framework drives in
one of two execution modes:

```
                     ┌────────────────────────────────┐
                     │       TradingStrategy          │
                     │                                │
                     │  generate_signals(ctx, data)   │◄── event   (app.run_backtest, paper, live)
                     │  generate_signal_series(data)  │◄── vector  (app.run_backtest with engines=[BacktestEngine.VECTOR])
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
**nine-phase pipeline**
(`Pipelines → Indicators → Collect → Resolve → Size → Budget → Emit → AttachRisk → RecordCooldown`)
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
| Triggered by | `app.run_backtest`, paper, live | `app.run_backtest` with `study.engines=[BacktestEngine.VECTOR]` |
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

`app.run_backtest(...)` calls
`validate_strategy_for_vector_backtest(strategy)` when the vector
engine is selected, before doing any work. The validator uses a
class-identity check:

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

#### Staged scale-in cards

`SignalSeries.supports_staged_scale_in: ClassVar[bool] = True` declares
framework support for the execution contract below. It is a class-level
capability marker, not a constructor argument, dataclass field, or serialized
signal field. Before yielding staged masks, strategies supporting older
framework installations should fail explicitly:

```python
if not getattr(SignalSeries, "supports_staged_scale_in", False):
    raise RuntimeError(
        "Staged scale-in vector backtests require updated framework support"
    )
```

For a long position, emit multiple `SignalSeries(side=SignalSide.SCALE_IN)`
for the same symbol with `metadata={"scale_in_stage": 0,
"require_lower_price": True}` (then stages `1`, `2`, ...). Each series must
contain the **raw card-qualified mask**: indicators, history availability and
thresholds only, not a simulated position state. Entry and exit series can
also be raw masks. A `ScalingRule` still controls sizing, maximum entries
(including the initial entry) and cooldowns.

The vector executor selects only the next unfilled stage, starting at `0`
after the initial entry. Missing stages mean no further additions. Only a
successful fill advances the stage; cooldowns, capital denials and failed
opens do not consume it. At most one addition occurs per bar, never on the
initial-entry bar, and exits take priority. Partial exits do not rearm stages;
becoming fully flat resets them. With `require_lower_price=True`, the current
close must be strictly below the latest accepted entry's actual fill price,
even if that entry has since been partially or fully trimmed.

Stage numbers must be nonnegative integers (not booleans), unique per symbol.
Mixing staged and unstaged `SCALE_IN` series for one symbol is invalid.
Unstaged series retain their existing last-series-wins behavior. Staged
execution uses Python: `execution_backend="auto"` logs a Python fallback;
strict `"rust"` raises `NativeExecutionUnsupported` rather than ignoring
stage metadata. Card batch evaluation and execution backend are independent.

In event mode, `Signal(side=SignalSide.SCALE_IN,
metadata={"scale_in_stage": stage})` also selects the corresponding
`ScalingRule` percentage and enforces cumulative `max_entries` in sizing.
The strategy supplies this fill-derived stage and resets it only when fully
flat; the number of still-open lots is not a substitute after partial exits.
Unstaged event signals continue to size from the current open-trade count.

To recover additions that filled and closed between event evaluations, query
`context.get_trades(target_symbol=symbol, trading_symbol=quote,
portfolio=portfolio.id, opened_since=position_started_at)` without a status
filter. `opened_since` is inclusive and is applied before history is loaded,
including in Python/Rust event archives. Symbol and quote filters
are forwarded to the repository; portfolio scope uses its `portfolio_id`
filter. `market=` resolves that market's portfolio, or verifies an explicit
portfolio belongs to the market. Filter the returned history for
`not trade.is_short`, `trade.filled_amount > 0`, and
`trade.opened_at >= position_started_at`, retaining IDs until fully flat.
Use consistent timezone handling for timestamps. Direct service queries use
`trade_service.get_all({"opened_at_gte": position_started_at, ...})`.
New SQL schemas and event archives index `opened_at`; existing persistent SQL
databases need the equivalent `ix_trades_opened_at` index for indexed lookups.
For an existing SQL database, apply this idempotent schema upgrade:

```sql
CREATE INDEX IF NOT EXISTS ix_trades_opened_at ON trades (opened_at);
```

Native event accounting requires the rebuilt `event-archive-v3` extension;
older archives fail the capability check rather than scanning all history.
Default SQL accounting and explicit Python `event_state_backend="memory"`
do not load the native extension and remain usable without rebuilding it.
Event accounting has no `"auto"` backend; explicit `"rust"` is strict.
`Trade` has no direct market/portfolio field: scope is determined through its
orders' positions.

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
│ 0b. EvaluateIndicatorsPhase      │  optional native indicator/card
│                                 │  evaluation → data["indicators"]
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

**Phase 0b — `EvaluateIndicatorsPhase`**
Evaluates native declarations, using an installed `_indicator_engine` or a
lazy instance-local engine, and injects `IndicatorEvaluation` as
`state.data["indicators"]`. Without declarations this phase has no effect.
See the native contract in §1.

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
          EvaluateIndicatorsPhase(),
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
