# Backtest Bundle Format — Adoption of Open Backtest Format (OBTF)

**Status:** Stable. Default since v9.0
**Author:** Marc van Duyn

This document describes the on-disk binary format produced by
`save_bundle()` and consumed by `open_bundle()` /
`Backtest.open()`. It is a reference implementation of the Open Backtest Format (OBTF) specification. You can find the full specification at [https://github.com/Quant-Commons/Open-Backtest-Format](https://github.com/Quant-Commons/Open-Backtest-Format).

---

## Overview

The backtest bundle format is a single-file, engine-agnostic, studies-first container for the full evidence of a quantitative trading strategy's backtest results: metrics, trades, orders, portfolio snapshots, universes, cost assumptions, and Monte-Carlo significance tests. It is designed to be portable across environments, engines (vector / event-driven / hybrid), regimes, and toolchains.

This document describes how QuantOS currently implements the OBTF specification. The specification itself is maintained in a separate repository ([Quant-Commons/Open-Backtest-Format](https://github.com/Quant-Commons/Open-Backtest-Format)) and may evolve independently of this implementation. Other implementers wishing to produce or consume OBTF bundles can use this document as a concrete reference alongside the spec.

## High-level structure

```
Backtest                                # keyed by algorithm_id
├── algorithm_id: str                   # unique fingerprint of the algo code + config
├── anchor_algorithm_id: str | None     # lineage edge: id of the anchor strategy this
│                                       #   bundle was derived from (None on anchors,
│                                       #   set on perturbed / sibling bundles).
├── parameters: dict                    # the canonical param fingerprint
├── metadata: dict                      # algo-level, static
├── obtf_version: int                   # e.g. 1, official OBTF format
└── studies: dict[str, Study]           # keyed by study_name
        ├── name: str                   # the strategy/signal idea (e.g. "ema_cross")
        ├── description: str
        ├── created_at: datetime
        ├── initial_capital: float | None  # starting capital for this study (e.g. 1000.0)
        ├── risk_free_rate: float          # annualised risk-free rate for Sharpe/Sortino
        │                                  #   (default 0.027 = 2.7%)
        ├── windows: list[BacktestWindow | BacktestDateRange]
        │                               # the temporal axis of the study. Use
        │                               #   BacktestWindow for walk-forward / k-fold
        │                               #   (train + optional test); use a bare
        │                               #   BacktestDateRange for a single in-sample
        │                               #   period. See §Backtest Window Structure.
        ├── universes: list[Universe]   # registry of universes this study has runs for
        │                               #   (the regime axis — per-run universe lives on Run)
        ├── sample_type: str | None     # categorical role of this study in the evaluation
        │                               #   workflow. See §Sample type for the full list of
        │                               #   built-in values ("in_sample", "walk_forward", …).
        │                               #   Free-form: user-defined tags are allowed;
        │                               #   readers MUST treat unknowns as opaque.
        ├── execution_config: ExecutionConfig | None
        │                               # snapshot of the cost / fill assumptions this
        │                               #   study's runs were produced under; None on
        │                               #   legacy bundles. See §Execution config structure.
        ├── vector:                     # optional engine slot
        │     ├── runs: list[Run]                       # each Run carries its own Universe
        │     ├── summary: Summary                      # pooled across all runs (overall study perf)
        │     └── monte_carlo_tests: list[MonteCarloTest]
        │                               # significance tests against null distributions
        │                               #   produced by shuffling the engine's runs.
        │                               #   See §Monte-Carlo test structure.
        └── event:                      # same shape as vector
              ├── runs: list[Run]
              ├── summary: Summary
              └── monte_carlo_tests: list[MonteCarloTest]
```

A `Study` represents a single test configuration.
Each study has multiple engine slots (e.g. `vector`, `event`) and each engine slot has multiple runs. A study
always has one universe. A study also always has one execution config (cost / fill assumptions) that applies to all runs in that study.

### Universe Structure

A universe is a representation of the market context in which a run was executed. It contains the symbols, base currency, and market information. Universes can be shared across runs and studies, allowing for efficient comparisons and aggregations.

```
Universe
├── key: str               # short stable identifier (e.g. "eu_top10_crypto")
├── symbols: list[str]    # e.g. ["BTC/EUR", "ETH/EUR", ...]
├── trading_symbol: str    # base currency, e.g. "EUR"
├── market: str | None      # e.g. "BITVAVO", "BINANCE"; None for multi-market
└── metadata: dict          # free-form
```

> **Note:** `initial_capital` and `risk_free_rate` are intentionally NOT on
> Universe. They are evaluation parameters that belong on the Study — the
> same asset basket can be tested with different capital levels or rate
> assumptions across studies.

### Backtest Window Structure

A `BacktestWindow` represents a single train/test slice of a study — one training period, optionally paired with an out-of-sample test period, plus the metadata needed to reason about it (warmup, purge, fold membership, generator step).

A study typically carries a *list* of these on `Study.windows`: one per fold in k-fold, one per step in walk-forward, or a single window for a plain in-sample fit. Backtests that don't need a train/test split can use a bare `BacktestDateRange` instead — `Study.windows` accepts either shape and consumers distinguish them by field presence (`train_range` vs `start_date`).

**Fields at a glance:**

- **`train_range`** (required) — the in-sample period. **Includes** any warmup at its start.
- **`test_range`** (optional) — the out-of-sample period. `None` when the window is in-sample-only (e.g. a parameter fit that will be evaluated by a separate downstream study).
- **`warmup_days`** — a warmup buffer stripped from the *start* of `train_range` before strategy evaluation. Use it when an indicator (say, a 26-day EMA) needs data before its first meaningful reading. Also see the derived `effective_train_range` below.
- **`gap_days`** — the purge period between `train_range.end_date` and `test_range.start_date`. Prevents look-ahead leakage when indicators or signals span the train/test boundary. Stored (not derived) so the runner's declared intent is preserved on disk, even in the `gap_days == 0` case where the intent is ambiguous from dates alone.
- **`step_days`** — the inter-window step used by the generator that produced this window (e.g. `step_days = 90` for a quarterly rolling walk-forward). `None` for k-fold and one-off windows. Every window in a rolling or anchored sequence carries the same value.
- **`fold_index`** — zero-based fold index for k-fold splits. `None` for rolling / anchored / one-off windows.
- **`name`** — human label, optional. Free-form.

**Common workflows produce these window shapes:**

| Workflow                | `train_range`         | `test_range`          | `step_days` | `fold_index` | Generator                              |
| ----------------------- | --------------------- | --------------------- | :---------: | :----------: | -------------------------------------- |
| Rolling walk-forward    | fixed size, slides    | slides after train    |     set     |    `None`    | `generate_rolling_backtest_windows`    |
| Anchored walk-forward   | fixed start, grows    | slides after train    |     set     |    `None`    | `generate_anchored_backtest_windows`   |
| Time-series k-fold      | expanding from anchor | disjoint fold         |   `None`    | set (0..n-1) | `generate_k_fold_backtest_windows`     |
| One-off in-sample fit   | set                   | `None`                |   `None`    |    `None`    | manual construction                    |
| One-off with holdout    | set                   | set                   |   `None`    |    `None`    | manual construction                    |

**Relationship to `Run`.** A single `BacktestWindow` produces exactly **one** `Run` per engine slot. The run's *active range* is the window's `test_range` when it has one (walk-forward / holdout evaluation) and its `train_range` otherwise (in-sample-only fit). The derived fields `Run.backtest_start_date`, `Run.backtest_end_date`, `Run.backtest_date_range_name`, and `Run.window_role` all read from the active range. The full parent window — including the training portion that produced this run, plus any warmup / gap / step / fold metadata — stays accessible on `Run.backtest_window`; readers that need to inspect the training period of a walk-forward run should read `Run.backtest_window.train_range` directly.

```md
BacktestDateRange
├── start_date: datetime                    # start of the range, inclusive
├── end_date: datetime                      # end of the range, inclusive
└── name: str                               # human label (e.g. "in_sample", "oos_2023")
```

```md
BacktestWindow
├── name: Optional[str]                     # human label (e.g. "walkforward_fold_3")
├── train_range: BacktestDateRange          # the training / in-sample period
│                                           #   (INCLUDES any warmup at its start)
├── test_range: Optional[BacktestDateRange] # the out-of-sample period.
│                                           #   None when in-sample-only.
├── warmup_days: int                        # days at the start of train_range reserved
│                                           #   for warming up indicators. NOT counted
│                                           #   as effective training. Default: 0.
├── gap_days: Optional[int]                 # purge period (in days) between
│                                           #   train_range.end_date and
│                                           #   test_range.start_date. Stored to
│                                           #   preserve producer intent; MUST match
│                                           #   the gap implied by the dates when a
│                                           #   test_range is set. None when test_range
│                                           #   is None.
├── step_days: Optional[int]                # inter-window step used by the generator
│                                           #   that produced this window. None for
│                                           #   k-fold and one-off windows (which are
│                                           #   not step-generated). Same value on
│                                           #   every window in a rolling / anchored
│                                           #   sequence.
└── fold_index: Optional[int]               # zero-based fold index for k-fold splits.
                                            # None for rolling / one-off windows.
```

**Validation.** A `BacktestWindow` MUST satisfy:

- `warmup_days >= 0`
- `warmup_days < (train_range.end_date - train_range.start_date).days`
- `gap_days >= 0` when provided
- `step_days > 0` when provided
- If `test_range` is set: `test_range.start_date >= train_range.end_date`
- If both `gap_days` and `test_range` are provided: `gap_days == (test_range.start_date - train_range.end_date).days` (declared intent MUST match the dates)

**Derived properties** (computed on demand, never stored on disk):

- `effective_train_range` — `train_range` with the first `warmup_days` days stripped from the start. The period actually usable for strategy evaluation once indicators have warmed up.

**Overlap semantics.** Consecutive windows in `Study.windows` MAY exhibit three distinct kinds of temporal overlap, all by design:

- **Adjacent train overlap** — the training ranges of `window[i]` and `window[i+1]` intersect. Standard for rolling walk-forward (`train_days − step_days` days of overlap; e.g. 275 days with the defaults `train_days=365`, `step_days=90`). For anchored walk-forward and time-series k-fold the earlier training range is fully *contained* in the later one (their training ranges are nested by construction, growing from a shared anchor).
- **Adjacent test overlap** — the test ranges of `window[i]` and `window[i+1]` intersect. Occurs in rolling and anchored walk-forward only when `step_days < test_days` ("small-step" configurations). K-fold never produces overlapping test ranges (disjoint by construction).
- **Cumulative test-in-train containment** — the test range of `window[i]` falls inside the training range of `window[j]` for some `j > i`. Happens in rolling whenever `train_days > step_days` (the framework's rolling defaults produce 90 days of this per adjacent pair), and *always* in anchored walk-forward and k-fold (their training ranges anchor to the study start and cumulatively include every prior test range).

Consumers aggregating metrics across `Study.windows` MUST account for all three overlaps and deduplicate whenever their statistic requires disjoint samples. Naive pooled averages over `Study.windows[*].test_range` metrics will double-count. Non-overlapping evaluation is a runner concern, not a format guarantee.

The specific numbers above describe what the framework's built-in generators produce. The OBTF format itself does not require any particular overlap pattern — see `open-backtest-format/spec/5-universe-windows.md` for the neutral, format-level statement.

### Execution config structure

An `ExecutionConfig` is a snapshot of the cost, fill assumptions under which a study's runs were produced. It is stored on `Study.execution_config` and applies to all runs in that study. It is the `BacktestExecutionConfig` dataclass — small, dict-shaped, always inline in the msgpack body; no Parquet blobs, no lazy references.

**Why on the study, not the backtest?** Two studies inside the same `algorithm_id` bundle can validly use different execution assumptions — e.g. an in-sample sweep run zero-cost next to an out-of-sample study run under realistic fees. Anchoring `execution_config` to `Study` (rather than to `Backtest`) keeps each study self-describing and lets one bundle hold optimistic / pessimistic overlays of the same algorithm side by side.

```bash
ExecutionConfig (= BacktestExecutionConfig)
├── slippage_model: SlippageModel | None
│                                         # applied to every fill.
├── commission_model: CommissionModel | None
│                                         # applied to every trade.
├── fill_model: FillModel | None          # controls whether/how orders fill
│                                         #   (fully, partial by volume, etc.).
└── metadata: dict | None                 # free-form (blotter module path for user
                                           #   subclasses, runtime flags like
                                           #   dynamic_position_sizing,
                                           #   fill_missing_data, etc.).
```

#### Pluggable model pattern

`SlippageModel`, `CommissionModel`, and `FillModel` are pluggable base classes. On disk each instance is serialised as:

```json
{"type": "<class_name>", "params": {...}}
```

The framework maintains a class-name **registry** populated automatically via `__init_subclass__` on each of the three base classes. On load, `from_dict` looks up the `type` string and instantiates the concrete class with `**params`.

Built-in `type` values shipped with the framework:

| Base class        | Built-in types |
| ----------------- | -------------- |
| `SlippageModel`   | `NoSlippage`, `PercentageSlippage`, `FixedSlippage`, `FixedBasisPointsSlippage`, `VolumeImpactSlippage`, `VolumeShareSlippage` |
| `CommissionModel` | `NoCommission`, `PercentageCommission`, `FixedCommission` |
| `FillModel`       | `FullFill`, `VolumeBasedFill` |

Behaviour:

- **All built-in subclasses round-trip losslessly** — their `__init__` signatures match their public instance attributes.
- **User-defined subclasses round-trip** as long as the class is imported before the bundle is opened. Import your subclass in the same process (or module) that calls `open_bundle()`.
- **Unknown types degrade gracefully.** If the registry lookup fails, the reader logs a warning and returns `None` in place of the model instance. The rest of the bundle is unaffected.

The registry is process-local; it is *not* persisted. Bundles carry only the type name + params, keeping the on-disk format free of Python-class references.

#### Built-in model parameters

Each built-in `type` has a fixed set of constructor parameters. These parameter names ARE part of the on-disk shape — the `params` dict inside `{"type": ..., "params": {...}}` MUST use these exact keys.

**`SlippageModel` types:**

| `type`                       | `params` keys                                          | Defaults           | Semantics                                                                        |
| ---------------------------- | ------------------------------------------------------ | ------------------ | -------------------------------------------------------------------------------- |
| `NoSlippage`                 | *(none)*                                               | —                  | Fills at the exact order price.                                                  |
| `PercentageSlippage`         | `percentage: float`                                    | `0.001`            | Decimal (0.001 = 0.1%). Buys fill higher, sells fill lower by `price × percentage`. |
| `FixedSlippage`              | `amount: float`                                        | `0.01`             | Absolute slippage in price units. Buys fill at `price + amount`, sells at `price - amount`. |
| `FixedBasisPointsSlippage`   | `basis_points: float`                                  | `5`                | 1 bp = 0.01%. Slippage = `price × basis_points / 10000`.                          |
| `VolumeImpactSlippage`       | `base_percentage: float`, `impact_power: float`        | `0.001`, `0.5`     | `impact = base_percentage × (amount/volume) ^ impact_power`. Falls back to `base_percentage` when volume is unavailable. |
| `VolumeShareSlippage`        | `volume_limit: float`, `price_impact: float`           | `0.025`, `0.1`     | `impact = price_impact × (amount/volume)²`. Also caps the fillable amount at `volume_limit × volume`. |

**`CommissionModel` types:**

| `type`                    | `params` keys           | Defaults | Semantics                                            |
| ------------------------- | ----------------------- | -------- | ---------------------------------------------------- |
| `NoCommission`            | *(none)*                | —        | Zero fee.                                            |
| `PercentageCommission`    | `percentage: float`     | `0.001`  | Fee = `price × amount × percentage`.                 |
| `FixedCommission`         | `amount: float`         | `1.0`    | Flat fee per trade, in the trading-symbol currency.  |

**`FillModel` types:**

| `type`             | `params` keys                        | Defaults | Semantics                                                                         |
| ------------------ | ------------------------------------ | -------- | --------------------------------------------------------------------------------- |
| `FullFill`         | *(none)*                             | —        | Order fills in full on the first opportunity.                                     |
| `VolumeBasedFill`  | `max_volume_fraction: float`         | `0.1`    | Fill capped at `max_volume_fraction × bar_volume`. Remainder stays open and is re-evaluated on subsequent bars. |

Parameters not listed above SHOULD NOT appear in the `params` dict for the named `type`. Producers introducing custom parameters SHOULD invent a new `type` name (e.g. `x-myfirm-SlippagePlus`) rather than extending a reserved built-in — see the OBTF spec's extension namespace convention.

#### Reader behaviour

- Readers MUST tolerate unknown model `type` names — they are advisory metadata. Dropping such a field MUST NOT invalidate any runs, metrics, or summaries.
- Missing `execution_config` MUST NOT block reading the runs, metrics, or summaries that go with it.
- No Parquet blob extraction applies to this field.

### Run structure

A `Run` corresponds to a single execution of the algorithm over one
date range / window. It is the `BacktestRun` dataclass.

```
Run  (= BacktestRun)
├── backtest_window: BacktestWindow          # the parent window this run belongs to.
│                                           #   Carries train_range, optional test_range,
│                                           #   and warmup / gap / step / fold metadata.
│                                           #   See §Backtest Window Structure.
│
├── # "Active range" derived fields (computed on demand from backtest_window)
├── # — active range = backtest_window.test_range if present, else train_range.
├── backtest_start_date: datetime            # start of the active range
├── backtest_end_date: datetime              # end of the active range
├── backtest_date_range_name: str            # name of the active range
│                                           #   (matches backtest_window.test_range.name
│                                           #    or backtest_window.train_range.name).
├── window_role: "train" | "test"            # which portion of the parent window this
│                                           #   run was evaluated on. "test" when the
│                                           #   window has a test_range (walk-forward /
│                                           #   holdout OOS run), otherwise "train"
│                                           #   (in-sample-only fit). Makes the run →
│                                           #   window-portion attribution explicit rather
│                                           #   than name-matching.
│
├── initial_unallocated: float              # initial cash balance
├── created_at: datetime                    # when the run finished
├── number_of_runs: int                     # always 1 for a single Run
├── number_of_days: int                     # length of the active range in days
├── number_of_hours: int                    # length of the active range in hours
├── backtest_metrics: BacktestMetrics       # full per-run metrics (scalar + series, see below)
├── portfolio_snapshots: list[PortfolioSnapshot]  # periodic portfolio state
├── trades: list[Trade]                     # all trades executed
├── orders: list[Order]                     # all orders placed
├── positions: list[Position]               # all position changes
├── number_of_trades: int
├── number_of_trades_closed: int
├── number_of_trades_open: int
├── number_of_orders: int
├── number_of_positions: int
├── data_sources: list[dict]                # data sources resolved for this run
├── signals: dict[str, dict[str, list]]     # raw buy/sell signals, keyed by symbol
├── signal_events: list[dict]               # chronological log of fired signals + dispositions
├── recorded_values: dict[str, list]        # custom values the algo recorded via record(...)
└── metadata: dict[str, str]                # free-form per-run metadata
```

### Trade structure

A `Trade` is one entry order plus one or more exit orders on the same target symbol. For a long trade the entry is a `BUY` and the exits are `SELL`s; for a short trade the entry is a `SELL` and the exits are `BUY`s. The `is_short` flag records which side the trade opened on. A trade opens the moment its entry order fills, stays `OPEN` while the position is live, and closes when the sum of exit fills covers the entry. Multiple exit orders can close the same entry (e.g. a scale-out); the framework records every order that makes up the trade so the lineage is auditable.

```
Trade  (= Trade)
├── id: str | int
├── target_symbol: str                       # the traded asset, e.g. "BTC"
├── trading_symbol: str                      # base currency, e.g. "EUR"
├── is_short: bool                           # False → long (entry=BUY, exits=SELL);
│                                            #   True → short (entry=SELL, exits=BUY).
├── status: "OPEN" | "CLOSED"                # from TradeStatus enum. OPEN while any entry
│                                            #   amount remains unmatched by exits; CLOSED
│                                            #   once the exit side has covered the full
│                                            #   filled_amount.
│
├── open_price: float                        # the entry order's fill price. A trade always
│                                            #   has exactly one entry order, so this is a
│                                            #   single value — not an average across fills.
├── opened_at: datetime                      # when the entry order filled
├── closed_at: datetime | None               # when the last exit that closed the trade filled;
│                                            #   None while the trade is still OPEN.
│
├── amount: float                            # position size opened by the entry order
│                                            #   (target_symbol units)
├── filled_amount: float                     # amount actually filled by the entry order
├── available_amount: float                  # remaining position size not yet closed by exits
├── remaining: float                         # amount − filled_amount (unfilled entry, rare)
│
├── cost: float                              # cost basis in trading_symbol, taken from the
│                                            #   entry order (including its commission).
│                                            #   See §Cost and slippage attribution.
├── net_gain: float                          # realised P&L on the closed portion, net of fees
├── total_fees: float                        # sum of Order.order_fee across the entry order
│                                            #   and every exit order in `orders`. Denominated
│                                            #   in trading_symbol.
│
├── orders: list[Order]                      # the single entry order followed by one or more
│                                            #   exit orders on the opposite side, nested via
│                                            #   Order.to_dict. Slippage and fee attribution
│                                            #   is preserved on each order; the Trade-level
│                                            #   roll-ups above are recomputable from this list.
│
├── last_reported_price: float | None        # most recent mark price (used for unrealised P&L
│                                            #   while the trade is still open)
├── last_reported_price_datetime: datetime | None
│
├── stop_losses: list[TradeStopLoss] | None  # attached stop-loss triggers, if any
├── take_profits: list[TradeTakeProfit] | None
│                                            # attached take-profit triggers, if any
│
├── updated_at: datetime | None
└── metadata: dict[str, str]                 # free-form
```

### Order structure

An `Order` is a single instruction to buy or sell a specific amount of a target symbol. Orders progress through a small state machine (`CREATED` → `OPEN` → `CLOSED` / `CANCELED` / `REJECTED`), and every fill records the applied slippage and commission so the assumptions used by the runner are preserved verbatim on disk.

```
Order  (= Order)
├── id: str | int | None                     # framework-local identifier
├── external_id: str | None                  # broker / exchange id, when relevant
├── target_symbol: str                       # asset being traded, e.g. "BTC"
├── trading_symbol: str                      # quote / base currency, e.g. "EUR"
│
├── order_side: "BUY" | "SELL"               # from OrderSide enum
├── order_type: "MARKET" | "LIMIT"           # from OrderType enum. Framework also supports
│              | "STOP" | "STOP_LIMIT"       #   trailing / OCO variants; consult the enum for
│                                            #   the current full set.
├── status: "CREATED" | "OPEN" | "CLOSED"    # from OrderStatus enum
│           | "CANCELED" | "REJECTED"        #
│           | "EXPIRED"                      #
│
├── price: float | None                      # requested (limit) price; None for pure market orders
├── amount: float                            # requested amount, in target_symbol units
├── filled: float | None                     # amount actually filled
├── remaining: float | None                  # amount − filled
│
├── cost: float | None                       # total cash cost of the order in trading_symbol.
│                                            #   For buys: (fill_price × filled) + order_fee.
│                                            #   For sells: (fill_price × filled) − order_fee.
│                                            #   Feeds Trade.cost / Trade.net_gain.
│
├── # Cost / slippage attribution
├── # — see §Cost and slippage attribution for the flow diagram.
├── order_fee: float | None                  # cash fee charged on this fill, denominated in
│                                            #   order_fee_currency. Comes from
│                                            #   ExecutionConfig.commission_model.
├── order_fee_currency: str | None           # currency the fee is billed in (usually
│                                            #   trading_symbol).
├── order_fee_rate: float | None             # fee as a decimal fraction of trade value
│                                            #   (0.001 = 10 bp). Mirrors the commission model's
│                                            #   effective rate at fill time — kept alongside
│                                            #   `order_fee` for auditability.
├── slippage: float | None                   # per-unit slippage in price units (same unit as
│                                            #   `price`). Buy: fill_price − price. Sell:
│                                            #   price − fill_price. Always non-negative. Comes
│                                            #   from ExecutionConfig.slippage_model.
│
├── stop_price: float | None                 # trigger price for STOP / STOP_LIMIT orders
├── triggered_at: datetime | None            # when a STOP order fired (None if never triggered)
│
├── created_at: datetime                     # when the order was created
├── updated_at: datetime                     # last modification
└── metadata: dict[str, str]                 # free-form
```

### Position structure

A `Position` is the current netted holding of a target symbol inside a portfolio. It is a live-state object; historical position state is captured by `PositionSnapshot` inside a `PortfolioSnapshot`.

```
Position  (= Position)
├── symbol: str                              # target symbol, e.g. "BTC"
├── amount: float                            # units held (target_symbol units)
├── cost: float                              # cost basis in the portfolio's trading_symbol
└── portfolio_id: str | int | None
```

### Portfolio snapshot structure

A `PortfolioSnapshot` records the full portfolio state at a single point in time — cash, per-symbol positions, and rolled-up totals. Snapshots are what make equity curves, drawdowns, and TWR series recomputable from first principles.

```
PortfolioSnapshot  (= PortfolioSnapshot)
├── portfolio_id: str | int | None
├── trading_symbol: str                      # base currency, e.g. "EUR"
├── created_at: datetime                     # snapshot timestamp (UTC)
│
├── unallocated: float                       # free cash on hand (not tied up in open positions
│                                            #   or pending orders)
├── pending_value: float                     # cash locked in open buy orders that haven't filled
├── net_size: float                          # unallocated + pending_value + Σ (position mark value)
│                                            #   at snapshot time. Equals total_value.
├── total_value: float                       # total portfolio equity. Redundant with net_size,
│                                            #   retained for direct access.
│
├── total_cost: float                        # sum of cost basis across all open positions
├── total_revenue: float                     # gross proceeds from closed trades since inception
├── total_net_gain: float                    # realised + unrealised gain since inception
├── cash_flow: float                         # external deposits / withdrawals since inception
│                                            #   (non-strategy cash movements)
│
├── position_snapshots: list[PositionSnapshot]
│                                            # per-symbol amount + cost basis at snapshot time
│
└── metadata: dict[str, str]                 # free-form
```

Each `PositionSnapshot` inside is a minimal per-symbol slice:

```
PositionSnapshot  (= PositionSnapshot)
├── symbol: str
├── amount: float                            # units held at snapshot time
├── cost: float                              # cost basis in trading_symbol
└── portfolio_snapshot_id: str | int | None
```

### Cost and slippage attribution

Cost and slippage attribution is a first-class concern of the format. Every fill records both the slippage-adjusted price and the applied commission, and those numbers roll up into the trade's cost basis and P&L. An auditor can therefore reconstruct exactly what was assumed at each step of the trade lifecycle.

**Where the models come from.** Each study carries an `ExecutionConfig` (§Execution config structure) with `slippage_model`, `commission_model`, and `fill_model`. These are the *authoritative* cost / fill assumptions for every run in the study.

**Order.slippage.** At fill time the runner asks the study's `SlippageModel` for a fill price:

- For a BUY: `fill_price = slippage_model.buy_fill_price(price, amount, volume)`
- For a SELL: `fill_price = slippage_model.sell_fill_price(price, amount, volume)`

The per-unit **absolute** slippage is then recorded on the resulting `Order`:

- Buy fills: `Order.slippage = fill_price − price`
- Sell fills: `Order.slippage = price − fill_price`

`Order.slippage` is always non-negative and expressed in the same price units as `Order.price`. Multiplying by `Order.filled` yields the total cash cost of slippage in `trading_symbol` for that fill.

**Order fee triplet.** The `CommissionModel` produces a cash fee for the fill; the runner records it on the `Order` in three coupled fields:

| Field                | Meaning                                                                     |
| -------------------- | --------------------------------------------------------------------------- |
| `order_fee`          | The cash amount of the fee.                                                 |
| `order_fee_currency` | Currency the fee is billed in (usually `trading_symbol`).                   |
| `order_fee_rate`     | Fee as a decimal fraction of trade value (`0.001` = 10 bp), for audit.      |

Storing all three at once preserves the producer's intent even under downstream summarisation: an analyst can inspect the rate directly instead of back-solving it from `order_fee / (fill_price × filled)`, and the currency is explicit even when the fee happens to be denominated in a non-quote asset (some exchanges bill fees in a native token).

**Order.cost.** The order's total cash outlay in `trading_symbol`:

```text
Order.cost = fill_price × Order.filled + Order.order_fee   (BUY)
Order.cost = fill_price × Order.filled − Order.order_fee   (SELL, i.e. net proceeds)
```

The parent `Trade` inherits its cost basis directly from the single entry `Order.cost`.

**Trade-level roll-up.** A `Trade` is one entry order plus one or more exit orders on the opposite side (long: entry=BUY / exits=SELL; short: entry=SELL / exits=BUY). Its cost basis is fixed at open time by the entry; fees accumulate as exits attach:

- `Trade.cost = entry_order.cost` (the entry order's own `cost`, which already includes the entry commission).
- `Trade.total_fees = entry_order.order_fee + Σ exit_order.order_fee` over every exit in `Trade.orders`.
- `Trade.net_gain` is the realised P&L on the closed portion, net of `total_fees`. Sign convention is symmetric: long trades profit when exit fills print above `open_price`, short trades profit when exit fills print below.

Because the raw `Order` list is preserved on `Trade.orders`, every roll-up is verifiable. Any consumer can recompute `total_fees` from the underlying orders, or drill into a single fill to inspect the exact slippage and commission that applied.

**Advisory.** Producers MAY leave `slippage`, `order_fee`, `order_fee_currency`, or `order_fee_rate` as `None` when no model was configured (e.g. a zero-cost sanity run). Readers MUST tolerate absence and MUST NOT re-derive missing fields — the format prefers "no information" over "guessed information" for audit fields.

### Per-run metrics structure

Each `Run.backtest_metrics` is a `BacktestMetrics` instance with the
full set of scalar metrics, time-series, and trade statistics for
that single window.

```
BacktestMetrics
├── backtest_window: BacktestWindow          # the parent window this run belongs to.
│                                           #   Carries train_range, optional test_range,
│                                           #   and warmup / gap / step / fold metadata.
│                                           #   See §Backtest Window Structure.
│
├── # "Active range" derived fields (computed on demand from backtest_window)
├── # — active range = backtest_window.test_range if present, else train_range.
├── backtest_start_date: datetime            # start of the active range
├── backtest_end_date: datetime              # end of the active range
├── backtest_date_range_name: str            # name of the active range
│                                           #   (matches backtest_window.test_range.name
│                                           #    or backtest_window.train_range.name).
├── window_role: "train" | "test"            # which portion of the parent window this
│                                           #   run was evaluated on. "test" when the
│                                           #   window has a test_range (walk-forward /
│                                           #   holdout OOS run), otherwise "train"
│                                           #   (in-sample-only fit). Makes the run →
│                                           #   window-portion attribution explicit rather
│                                           #   than name-matching.
├── initial_unallocated: float
├── # capital / P&L
├── final_value: float
├── total_growth: float
├── total_growth_percentage: float
├── total_net_gain: float
├── total_net_gain_percentage: float
├── total_loss: float
├── total_loss_percentage: float
├── gross_profit: float
├── gross_loss: float
│
├── # return curves (List[Tuple[float, datetime]])
├── equity_curve
├── cumulative_return: float
├── cumulative_return_series
├── monthly_returns
├── yearly_returns
├── drawdown_series
│
├── # risk-adjusted (scalar + rolling)
├── cagr: float
├── sharpe_ratio: float
├── rolling_sharpe_ratio: List[Tuple[float, datetime]]
├── sortino_ratio: float
├── calmar_ratio: float
├── profit_factor: float
├── annual_volatility: float
├── var_95: float
├── cvar_95: float
│
├── # drawdowns
├── max_drawdown: float
├── max_drawdown_absolute: float
├── max_daily_drawdown: float
├── max_drawdown_duration: int
│
├── # TWR (alpha-only) variants — strip external cash flows
├── twr_equity_curve: List[Tuple[float, datetime]]
├── twr_drawdown_series: List[Tuple[float, datetime]]
├── twr_max_drawdown: float
├── twr_max_drawdown_duration: int
│
├── # trade statistics
├── number_of_trades: int
├── number_of_trades_closed: int
├── number_of_trades_opened: int
├── number_of_trades_open_at_end: int
├── number_of_positive_trades: int
├── percentage_positive_trades: float
├── number_of_negative_trades: int
├── percentage_negative_trades: float
├── win_rate: float
├── current_win_rate: float
├── win_loss_ratio: float
├── current_win_loss_ratio: float
├── max_consecutive_wins: int
├── max_consecutive_losses: int
│
├── # trade durations / sizes
├── average_trade_duration: float
├── average_win_duration: float
├── average_loss_duration: float
├── average_trade_size: float
│
├── # trade returns (averages, medians, current-only variants)
├── average_trade_loss / _percentage: float
├── average_trade_gain / _percentage: float
├── average_trade_return / _percentage: float
├── current_average_trade_gain / _percentage: float
├── current_average_trade_loss / _percentage: float
├── current_average_trade_return / _percentage: float
├── current_average_trade_duration: float
├── median_trade_return / _percentage: float
│
├── # frequency
├── trade_per_day: float
├── trades_per_week: float
├── trades_per_month: float
├── trades_per_year: float
│
├── # exposure
├── exposure_ratio: float
├── cumulative_exposure: float
│
├── # best / worst
├── best_trade: Trade
├── worst_trade: Trade
├── best_month / worst_month: Tuple[float, datetime]
├── best_year / worst_year: Tuple[float, date]
│
├── # period win-rates
├── percentage_winning_months: float
├── percentage_winning_years: float
├── average_monthly_return: float
├── average_monthly_return_losing_months: float
├── average_monthly_return_winning_months: float
│
├── total_number_of_days: int
└── metadata: dict[str, str]
```

### Monte-Carlo test structure

A `MonteCarloTest` records the result of a Monte-Carlo significance
test performed on top of an engine slot's `runs`. It lives alongside
`runs` / `summary` because the null distribution is generated by
re-running the strategy against *permuted versions of the input data
that produced those runs*; a different engine or a different study
yields a different test.

Today the framework supports a single null-generation strategy:
**OHLCV shuffling**. The OHLCV bars feeding each run are permuted (the
default flavour shuffles bar-relative returns and re-walks the price
series so OHLC relationships and gap structure stay coherent), the
strategy is re-executed against each permuted history, and the *full*
`BacktestMetrics` surface is recorded per permutation. This means one
Monte-Carlo test = one shuffle campaign that yields p-values for **many**
metrics simultaneously: any scalar on `BacktestMetrics` (Sharpe, Sortino,
CAGR, max-drawdown, …) can be tested against the same null pool without
re-shuffling. The `method` field is kept as a free-form string so future
flavours (signal shuffling, trade bootstrapping, block bootstraps, …) can
be added without bumping the bundle format.

```
MonteCarloTest  (= BacktestMonteCarloTest)
├── method: str                             # null-generation strategy. Framework default:
│                                           #   "shuffle_ohlcv" — re-run strategy against permuted
│                                           #   OHLCV bars (the only flavour wired up today).
│                                           #   Reserved for future use:
│                                           #     "shuffle_ohlcv_returns" | "shuffle_ohlcv_blocks"
│                                           #     "shuffle_signals" | "bootstrap_trades" | "random_entries"
│                                           #   Custom labels allowed; readers MUST treat unknowns as opaque.
│                                           #   Advisory: framework does not persist this field explicitly
│                                           #   today; readers SHOULD infer "shuffle_ohlcv" when absent.
│
├── real_metrics: BacktestMetrics           # full BacktestMetrics from the real (un-permuted) run
│                                           #   over backtest_window's active range.
│                                           #   See §Per-run metrics structure.
├── permutated_metrics: list[BacktestMetrics]
│                                           # one full BacktestMetrics per permutation.
│                                           #   Length == number of permutations. All permutations share
│                                           #   the same window scope and null-generation method.
│                                           #   Deriving a null distribution for any metric M is a list
│                                           #   comprehension over `[pm.<M> for pm in permutated_metrics]`
│                                           #   — the full metric surface is available; readers are not
│                                           #   locked into a single test statistic.
│                                           #   NOTE: field name retains the historical spelling.
├── p_values: dict[str, float]              # p-value per tested metric. Keys are BacktestMetrics /
│                                           #   Summary scalar names (e.g. "sharpe_ratio", "cagr",
│                                           #   "max_drawdown", "win_rate"). Populated lazily by the
│                                           #   framework via `compute_p_values`; default alternative
│                                           #   is one-sided — P(null >= real). A missing key means the
│                                           #   metric was not tested (or the real value was undefined).
│
├── backtest_window: BacktestWindow         # the window this test was scoped to.
│                                           #   Same shape and semantics as Run.backtest_window
│                                           #   (carries train_range, optional test_range,
│                                           #    warmup / gap / step / fold metadata).
│                                           #   See §Backtest Window Structure.
│
├── # "Active range" derived fields (computed on demand from backtest_window)
├── # — active range = backtest_window.test_range if present, else train_range.
├── backtest_start_date: datetime           # start of the active range
├── backtest_end_date: datetime             # end of the active range
├── backtest_date_range_name: str           # name of the active range. Serves as the join key
│                                           #   back to the corresponding Run's backtest_date_range_name.
└── window_role: "train" | "test"           # which portion of the parent window this test was scoped to.
                                            #   Mirrors Run.window_role for the corresponding Run.
```

Notes:

- A slot MAY hold multiple `MonteCarloTest` entries — one per
  shuffle campaign (typically distinguished by `method` and
  `backtest_window`, e.g. an OHLCV shuffle on the OOS window and
  a block-bootstrap on the same window). The
  `(method, backtest_window)` pair is expected to be unique within
  a slot, but writers are not required to enforce it. Each entry
  produces p-values for many metrics simultaneously via its
  `p_values` dict, so there is no need for one entry per metric.
- `permutated_metrics` is the storage-heavy field — each entry is
  a full `BacktestMetrics` object, which itself carries eight
  time-series fields. For campaigns with large permutation counts
  (e.g. 500+) this can dominate bundle size. A future v2.x revision
  MAY promote the whole list to a Parquet blob under
  `studies/<study>/<engine>/monte_carlo_tests/<index>/permutated_metrics.parquet`
  (one row per permutation, one column per scalar metric —
  time-series fields dropped from permuted runs); readers MUST
  honour the `{"@blob": "<key>"}` reference convention if present.
  Until then it is stored inline as a msgpack list.
- Monte-Carlo tests are advisory metadata: dropping the
  `monte_carlo_tests` list MUST NOT change any other field on the
  bundle. Older readers that don't know about the slot MUST ignore it.

### Summary structure

A `Summary` aggregates metrics across all runs in a study's engine
slot. It is the `BacktestSummaryMetrics` dataclass — scalar only,
no time-series.

```
Summary  (= BacktestSummaryMetrics)
├── # capital / P&L (aggregated)
├── total_net_gain: float
├── total_net_gain_percentage: float
├── total_growth: float
├── total_growth_percentage: float
├── total_loss: float
├── total_loss_percentage: float
│
├── # period averages (across runs / windows)
├── average_net_gain: float
├── average_net_gain_percentage: float
├── average_growth: float
├── average_growth_percentage: float
├── average_loss: float
├── average_loss_percentage: float
│
├── # trade-level averages (pooled)
├── average_trade_return / _percentage: float
├── average_trade_loss / _percentage: float
├── average_trade_gain / _percentage: float
├── average_trade_duration: float
├── average_win_duration: float
├── average_loss_duration: float
│
├── # risk-adjusted (pooled)
├── cagr: float
├── sharpe_ratio: float
├── sortino_ratio: float
├── calmar_ratio: float
├── profit_factor: float
├── annual_volatility: float
├── max_drawdown: float
├── max_drawdown_duration: int
├── var_95: float
├── cvar_95: float
│
├── # frequency (pooled)
├── trades_per_year: float
├── trades_per_month: float
├── trades_per_week: float
│
├── # win/loss
├── win_rate: float
├── current_win_rate: float
├── win_loss_ratio: float
├── current_win_loss_ratio: float
├── max_consecutive_wins: int
├── max_consecutive_losses: int
│
├── # totals
├── number_of_trades: int
├── number_of_trades_closed: int
│
├── # exposure
├── cumulative_exposure: float
├── exposure_ratio: float
│
├── # window-level counts
├── number_of_windows: int
├── number_of_profitable_windows: int
├── number_of_windows_with_trades: int
│
├── # consistency (cross-window — does the strategy behave the same in different regimes?)
├── return_consistency: float
├── win_rate_consistency: float
├── sharpe_consistency: float
├── consistency_score: float
│
└── # stability (in-window — is the strategy stable through time within a single run?)
    ├── return_stability: float
    ├── win_rate_stability: float
    ├── sharpe_stability: float
    └── stability_score: float
```

### Sample type

`Study.sample_type` is an optional categorical tag identifying the
role a study plays in the evaluation workflow. It lives alongside
`name` and `description` on the `Study` and round-trips as a plain
string.

Built-in values (framework-recognised, but consumers MUST treat the
field as free-form):

| Value                     | Meaning                                                              |
| ------------------------- | -------------------------------------------------------------------- |
| `"in_sample"`             | Plain in-sample fit or parameter sweep.                              |
| `"out_sample_time"`       | Time-based out-of-sample validation (same universe, later windows).  |
| `"out_sample_universe"`   | Universe-based out-of-sample validation (different symbols / market).|
| `"walk_forward"`          | Rolling walk-forward with train/test splits.                         |
| `"stress"`                | Stress-test / parameter perturbation.                                |
| `"monte_carlo"`           | Monte-Carlo scenario runs.                                           |

Notes:

- The field is a **plain string**, not an enum. This keeps the
  bundle forward-compatible: writers can attach custom sample-type
  labels without a framework change, and older readers see them as
  opaque strings.
- Absence (`sample_type: null` or key missing) means the runner did
  not tag the study — typical for legacy bundles and one-shot ad hoc
  backtests. Readers MUST tolerate absence.
- The `(study_name, sample_type)` pair is a common query axis:
  *"give me every algorithm's walk-forward evidence"* is a
  `WHERE sample_type = 'walk_forward'` query.
- Adding a new sample-type value is not a format change — readers
  MUST treat unknowns as opaque.

## Bundle identity and file extension

A backtest bundle is a single file (e.g. `my_algorithm.iafbt`) that carries the full evidence for one algorithm's backtest work. It is the unit of storage and sharing, designed to be self-contained and portable.

Each bundle is uniquely identified by its `algorithm_id` — a stable fingerprint of the algorithm's code and configuration. Because the fingerprint is stable across re-runs, related studies (in-sample and out-of-sample, or vector and event evaluations of the same idea) land in the *same* bundle and are trivially comparable. The `anchor_algorithm_id` field extends this with an explicit lineage edge: a perturbed variant can point back at the anchor strategy it was derived from.

This design supports three common workflows out of the box:

- **Different windows for the same strategy.** An in-sample study and an out-of-sample study for the same algorithm live in one bundle. Both share `algorithm_id`; the runs differ by `backtest_date_range_name` (and by which `Study` they belong to). Direct side-by-side comparison of in-sample vs. out-of-sample performance.
- **Different universes for the same strategy.** The same strategy evaluated on different markets or symbol sets, again in one bundle. Runs differ by `universe`; the shared `algorithm_id` makes cross-regime aggregation straightforward.
- **Monte-Carlo significance tests on top of an existing engine slot.** A `MonteCarloTest` attaches to the `vector` or `event` slot of an existing study, so the null distributions live next to the evidence they were computed against.

## Design principles

- **Engine-agnostic.** Each `Study` carries independent `vector` and `event` engine slots (`Study.vector` / `Study.event`). One bundle can hold results from both engines side by side. Readers that only care about one engine can ignore the other.
- **Studies-first.** The `Study` is the primary unit of organisation, not the individual run. Each study owns its universe, its windows, its execution config, and — via engine slots — its runs, summary, and Monte-Carlo tests. This matches how quants actually think: *"I have an idea; I want to evaluate it multiple ways."*
- **Per-run universe.** Universes are shared across runs and studies (they describe the market, not the strategy). Each `Run` carries the `Universe` it was evaluated on so the regime axis stays inspectable at the run level.
- **Explicit window attribution.** Every `Run` and `MonteCarloTest` carries its parent `BacktestWindow`, and derives `window_role` (`"train"` or `"test"`), the active date range, and the join key back to the study's window list. No name-matching required.
- **One-campaign Monte-Carlo.** A `MonteCarloTest` records the full `BacktestMetrics` per permutation, so a single shuffle campaign yields p-values for many metrics from the same null pool. No re-shuffling to test a different statistic.
- **Extension-friendly.** Fields the framework doesn't recognise (e.g. `sample_type` values it hasn't seen) MUST be treated as opaque strings, not rejected. Custom pluggable-model `type` names SHOULD use an `x-<vendor>-<name>` prefix to avoid collision with reserved built-ins.
