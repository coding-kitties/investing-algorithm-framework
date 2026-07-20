# Bundle Format — Public Specification

**Status:** Stable. Default since v9.0
**Author:** Marc van Duyn

This document describes the on-disk binary format produced by
`save_bundle()` and consumed by `open_bundle()` /
`Backtest.open()`.

---

## Overview

The backtest bundle format is a versioned, engine-agnostic, studies-first
envelope designed to hold the full set of backtest results for one algorithm. The goal
is to have a single file per algorithm that contains all the evidence (studies, runs,
metrics, metadata) for that algorithm's performance across different regimes and backtest engines.


### What are we trying to solve?

- **Portability**: a single file that can be easily shared, archived, or loaded across different environments.
- **Self-containment**: all relevant data (metrics, trades, orders, metadata) for an algorithm's backtests are stored together, without external dependencies.
- **Multi-study support**: the ability to store multiple studies (strategy variants, signal definitions) within the same bundle for easy comparison.
- **Engine-agnosticism**: support for both vector and event backtests within the same format, with clear routing based on `engine_type`.
- **Blob-friendliness**: the ability to offload large time-series metrics into separate Parquet blobs while keeping the main body compact and fast to read.


## High-level structure

### Structure

```
Backtest                                # keyed by algorithm_id
├── algorithm_id: str                   # unique fingerprint of the algo code + config
├── anchor_algorithm_id: str | None     # lineage edge: id of the anchor strategy this
│                                       #   bundle was derived from (None on anchors,
│                                       #   set on perturbed / sibling bundles); see §4.5
│                                       #   of docs/design/multi-study-bundle.md
├── parameters: dict                    # the canonical param fingerprint
├── metadata: dict                      # algo-level, static
├── framework_version: str              # e.g. "9.0.0"
├── bundle_format_version: int          # e.g. 2
└── studies: dict[str, Study]           # keyed by study_name
        ├── name: str                   # the strategy/signal idea (e.g. "ema_cross")
        ├── description: str
        ├── created_at: datetime
        ├── windows: list[BacktestDateRange]
        ├── universes: list[Universe]   # registry of universes this study has runs for
        │                               #   (the regime axis — per-run universe lives on Run)
        ├── vector:                     # optional engine slot
        │     ├── runs: list[Run]                       # each Run carries its own Universe
        │     ├── summary: Summary                      # pooled across all runs (overall study perf)
        │     ├── summaries_by_universe: dict[str, Summary]
        │     │                         #   per-regime view, keyed by Universe.key
        │     └── monte_carlo_tests: list[MonteCarloTest]
        │                               #   significance tests against null distributions
        │                               #   produced by shuffling the engine's runs
        └── event:                      # same shape as vector
              ├── runs: list[Run]
              ├── summary: Summary
              ├── summaries_by_universe: dict[str, Summary]
              └── monte_carlo_tests: list[MonteCarloTest]
```

A `Study` represents a single strategy idea / signal. Its `universes`
field is a *registry* of every universe the study has runs for, so
readers don't have to scan all runs to enumerate regimes. The
authoritative universe for any individual result lives on the `Run`
itself (see [Run structure](#run-structure)).

Per-universe summaries are stored as a cache (`summaries_by_universe`),
not derived on the fly. This keeps the "same signal evaluated across
3 regimes" case cheap to read: one study, three entries in
`summaries_by_universe`, and `summary` carries the pooled cross-regime
number.

### Run structure

A `Run` corresponds to a single execution of the algorithm over one
date range / window. It is the `BacktestRun` dataclass.

```
Run  (= BacktestRun)
├── backtest_start_date: datetime           # start of the window
├── backtest_end_date: datetime             # end of the window
├── backtest_date_range_name: str           # name of the window (e.g. "in_sample")
├── universe: Universe                      # which universe this run was evaluated on
│                                           #   (key, symbols, trading_symbol, market, …)
│                                           #   Phase 3a: looked up via
│                                           #   metadata["universe_key"] against
│                                           #   the parent Study.universes registry.
│                                           #   Phase 3b: stored directly on the Run.
├── trading_symbol: str                     # base trading currency, e.g. "EUR"
│                                           #   (mirror of universe.trading_symbol; kept for
│                                           #    back-compat and direct access)
├── initial_unallocated: float              # initial cash balance
├── created_at: datetime                    # when the run finished
├── number_of_runs: int                     # always 1 for a single Run
├── number_of_days: int                     # length of the window in days
├── symbols: list[str]                      # symbols traded in this run
│                                           #   (mirror of universe.symbols)
│
├── backtest_metrics: BacktestMetrics       # full per-run metrics (scalar + series, see below)
├── portfolio_snapshots: list[PortfolioSnapshot]  # periodic portfolio state
├── trades: list[Trade]                     # all trades executed
├── orders: list[Order]                     # all orders placed
├── positions: list[Position]               # all position changes
│
├── number_of_trades: int
├── number_of_trades_closed: int
├── number_of_trades_open: int
├── number_of_orders: int
├── number_of_positions: int
│
├── data_sources: list[dict]                # data sources resolved for this run
├── signals: dict[str, dict[str, list]]     # raw buy/sell signals, keyed by symbol
├── signal_events: list[dict]               # chronological log of fired signals + dispositions
├── recorded_values: dict[str, list]        # custom values the algo recorded via record(...)
└── metadata: dict[str, str]                # free-form per-run metadata
```

### Per-run metrics structure

Each `Run.backtest_metrics` is a `BacktestMetrics` instance with the
full set of scalar metrics, time-series, and trade statistics for
that single window.

```
BacktestMetrics
├── # window identity (mirror of the parent Run)
├── backtest_start_date: datetime
├── backtest_end_date: datetime
├── backtest_date_range_name: str
├── trading_symbol: str
├── initial_unallocated: float
│
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
├── total_number_of_days: int                # auto-computed in __post_init__
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
strategy is re-executed against each permuted history, and the metric
of interest is recorded. The `method` field is kept as a free-form
string so future flavours (signal shuffling, trade bootstrapping,
block bootstraps, …) can be added without bumping the bundle format.

```
MonteCarloTest
├── name: str                          # human label, e.g. "shuffle_ohlcv_sharpe"
├── method: str                        # null-generation strategy. Currently supported:
│                                      #   "shuffle_ohlcv"     — re-run strategy against permuted OHLCV
│                                      #                         bars (the only flavour wired up today)
│                                      # Reserved for future use:
│                                      #   "shuffle_ohlcv_returns" | "shuffle_ohlcv_blocks"
│                                      #   "shuffle_signals" | "bootstrap_trades" | "random_entries"
│                                      # Custom labels are allowed; readers MUST treat unknowns as opaque.
├── metric: str                        # which BacktestMetrics / Summary scalar is tested
│                                      #   (e.g. "sharpe_ratio", "total_net_gain_percentage",
│                                      #    "profit_factor", "max_drawdown")
├── observed_value: float              # value of `metric` on the real (un-permuted) runs
├── null_distribution: list[float]     # one entry per permutation; length == n_permutations
├── n_permutations: int                # number of Monte-Carlo trials
├── p_value: float                     # P(null >= observed) for one-sided tests,
│                                      #   2 * min(left, right) for two-sided
├── alternative: str                   # "greater" | "less" | "two-sided"
├── seed: int | None                   # RNG seed used to generate the null (None = non-deterministic)
├── window: BacktestDateRange | None   # optional: scope the test to a single window
│                                      #   (None = pooled across every run in the slot)
├── universe_key: str | None           # optional: scope to a single universe within the slot
├── created_at: datetime
└── metadata: dict[str, str]           # free-form (e.g. block size for block-bootstrap, etc.)
```

Notes:

- A slot MAY hold multiple `MonteCarloTest` entries — one per
  metric, method, or scope combination. The `(name, method, metric,
  window, universe_key)` tuple is expected to be unique within a
  slot, but writers are not required to enforce it.
- `null_distribution` is stored inline as a msgpack list of floats.
  For very large `n_permutations` (>10k) a future v2.x revision MAY
  promote it to a Parquet blob under
  `studies/<study>/<engine>/monte_carlo_tests/<index>/null.parquet`;
  readers MUST honour the `{"@blob": "<key>"}` reference convention
  if present.
- Monte-Carlo tests are advisory metadata: dropping the
  `monte_carlo_tests` list MUST NOT change any other field on the
  bundle. Older readers that don't know about the slot MUST ignore it.

> Eight time-series fields (`equity_curve`, `drawdown_series`,
> `cumulative_return_series`, `rolling_sharpe_ratio`, `monthly_returns`,
> `yearly_returns`, `twr_equity_curve`, `twr_drawdown_series`) are
> extracted into Parquet blobs by the v2 writer. See the
> [Metric blob extraction](#metric-blob-extraction) section.

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

## Why this format?

This format is designed to be:

- **Engine-agnostic**: it can hold vector backtests, event backtests,
  or both in the same bundle. The `engine_type` field routes readers to
  the right section.
- **Studies-first**: the `Study` is the primary unit of organisation, not the
  backtest run. Each `Study` holds its own universe and metadata, and
  can contain either or both engine slots. This reflects the mental
  model of "I have a strategy idea (study) that I want to test in
  different ways (vector vs event backtest)".
- **Blob-friendly**: the `blobs` map allows writers to offload large
  metric series into separate Parquet blobs while keeping the main
  body compact. Readers treat the `blobs` map as authoritative, so they
  can safely ignore unknown blob keys for forward compatibility.
- **Versioned**: the `format_version` field allows for future revisions of
  the on-disk format while maintaining backward compatibility. Readers
  reject unsupported versions, and writers default to the latest version.

## What is a .iafbt file?

A .iafbt file is a single file (e.g. `my_algorithm.iafbt`) that contains the full set of backtest results for one algorithm. It is the unit of storage and sharing for backtest results, designed to be self-contained and portable.
Each .iafbt file is uniquely identified by its `algorithm_id`, which is a fingerprint of the algorithm's code and configuration. Its therefore important that the `algorithm_id` is stable across different runs of the same algorithm, so that related studies (e.g. in-sample and out-of-sample) can be co-located in the same bundle. Additionally, the `anchor_algorithm_id` field allows for explicit lineage tracking between related bundles (e.g. a perturbed strategy variant can point to its anchor strategy's `algorithm_id`). This is an opinionated design. We designed it this way to support the following common workflows:

- Different windows for the same strategy: you can run an in-sample study and an out-of-sample study for the same algorithm, and save both into the same .iafbt bundle. Both studies will share the same `algorithm_id` (because the code/config is the same) but have different `backtest_date_range_name` values on their runs. This makes it easy to compare in-sample vs out-of-sample performance side by side.
- Different universes for the same strategy: you can run the same strategy on different markets or trading symbols, and save all the studies into the same .iafbt bundle. Each study's runs will have different `universe` values, but they will all share the same `algorithm_id`. This allows you to compare how the same strategy performs across different regimes.
- Adding Monte-Carlo significance tests for vector or event backtests: you can run a Monte-Carlo test on top of an existing study's engine slot, and save the test results into the same .iafbt bundle.

### Running a Monte-Carlo significance test (App API)

The framework exposes a single high-level entry point for producing
the `monte_carlo_tests` records that ultimately land in an engine
slot of a bundle:

```python
from investing_algorithm_framework import (
    create_app, BacktestDateRange, BacktestMonteCarloTest,
)

app = create_app()

mc_test: BacktestMonteCarloTest = app.run_monte_carlo_test(
    strategy=my_strategy,
    backtest_date_range=BacktestDateRange(
        start_date=..., end_date=..., name="oos"
    ),
    number_of_permutations=200,        # number of OHLCV shuffles
    initial_amount=1_000.0,
    risk_free_rate=0.04,
)
```

`App.run_monte_carlo_test` does three things:

1. Runs the **real** vector backtest on the supplied date range and
   captures its `BacktestMetrics`.
2. Builds the null distribution by shuffling the OHLCV bars
   (`BacktestService.create_ohlcv_permutation`) `number_of_permutations`
   times and re-running the strategy through the vector engine on each
   shuffled dataset.
3. Returns a single `BacktestMonteCarloTest` that pairs the real
   metrics with the list of permuted metrics, the per-metric
   p-values, and references to the original / shuffled OHLCV frames
   used for the run.

Persisting the result back into a bundle is then a matter of
attaching it to the matching `Backtest` and saving:

```python
backtest = app.run_vector_backtest(
    strategy=my_strategy, backtest_date_range=mc_test.date_range,
    initial_amount=1_000.0,
)
backtest.add_monte_carlo_test(mc_test)
backtest.save(directory_path)        # or save_bundle(...)
```

On the on-disk side this maps onto:

- **Bundle (.iafbt)** — `mc_test` is appended to
  `studies/<algorithm_id>/<engine>/monte_carlo_tests` of the active
  study/engine slot in the studies-first envelope. Today only the
  vector engine is wired through `App.run_monte_carlo_test`; the
  event-engine slot is reserved for future per-engine Monte-Carlo
  tests (see §Monte-Carlo test structure for why both slots exist).
- **Directory layout** — `BacktestMonteCarloTest.save()` writes a
  child directory under `monte_carlo_tests/monte_carlo_test_<start>_<end>/`
  containing the real metrics, the per-trial `permuted_metrics/`
  subdir, and the computed p-values.

The `method` field on a `MonteCarloTest` is currently always
`"shuffle_ohlcv"` — bootstrap and parametric flavours are reserved
for future revisions and MUST be ignored by readers that do not
recognise them.

### What is a study?

A study represents a single idea within an algorithm — e.g. a specific signal definition or strategy variant. Each study has its own metadata, universe registry, and per-engine slots for runs and summaries. Multiple studies can coexist within the same bundle, allowing you to compare different ideas side by side.

For example, you might want to change the cooldown windows of an strategy and see how that affects performance. You can run a new study with the same strategy code but different cooldown parameters, and save it into the same bundle. Both studies will be discoverable and comparable within that bundle.

### What is a universe?

### What is an algorithm id

### What does the

## Use cases

The format is designed to support the workflows below. Each use case
ends with a note on whether it works in **Phase 3a** (today, additive
single-study layout) or requires **Phase 3b** (the v5 zip + per-study
parquet layout that makes `studies: dict[str, Study]` the source of
truth on disk).

### In-sample backtests

1. Strategy definition and parameterization.
2. Study definition (e.g. `"in_sample_signal_sweep"`).
3. Universe definition (key, symbols, market, trading symbol, metadata).
4. Backtest windows definition, creating *x* date ranges
   (e.g. 2020–2022, 2021–2022, 2020–2021).
5. Parameter sweep generation, creating *y* strategy variants.
6. Vector backtest execution, producing *y* `.iafbt` bundles
   (one per strategy variant, keyed by `algorithm_id` fingerprint).
   Each bundle contains one study with *x* runs.

> **Coverage:** ✅ Phase 3a — single study per bundle is the
> existing layout.

### In-sample study extension (additional study in same bundles)

1. Load the in-sample study from the previous step
   (`"in_sample_signal_sweep"` — *x* runs per variant).
2. Define a new study (e.g. `"in_sample_signal_sweep_with_cooldown"`)
   covering the same *y* variants (or a top-*n* selection).
3. Load the parameters from each saved `.iafbt` bundle.
4. Initialise the strategies — same fingerprint per variant as the
   original in-sample study.
5. Create *x* backtest windows with the same date ranges as the
   original in-sample study.
6. Execute the backtests, producing *x* runs per variant.
7. Save the new study into the same `.iafbt` bundles. Each bundle
   now contains **two** studies, each with *x* runs per variant.

> **Coverage:** ⚠️ Phase 3b — needs `studies: dict[str, Study]` on
> disk so a bundle can hold more than one study. Phase 3a's
> derived-view `studies` always exposes exactly one slot.

### Out-of-sample backtests

1. Load the strategy variants from the in-sample study
   (`"in_sample_signal_sweep"`) you want to test out-of-sample.
2. Study definition (e.g. `"out_sample_time_oos"`).
3. Universe definition (different from in-sample — different market,
   trading symbol, universe key/symbols, etc.).
4. Initialise the strategies from the saved fingerprints.
5. Backtest windows definition, creating *x* date ranges
   (e.g. 2022–2023, 2022–2024, 2023–2024).
6. Vector backtest execution.
7. Save the results, appending a new study (`"out_sample_time_oos"`)
   to the same `.iafbt` bundles already containing the in-sample
   study. Each appended study has *x* runs per variant. Because the
   `algorithm_id` fingerprint is unchanged, the new out-of-sample
   study is co-located with its in-sample counterpart in the same
   bundle.

> **Coverage:** ⚠️ Phase 3b — same reason as study extension above
> (multi-study per bundle).

### Event backtests as a new study

1. Load the strategy variants from `"in_sample_signal_sweep"` you
   want to evaluate via the event engine.
2. Study definition (e.g. `"in_sample_signal_sweep_event"`).
3. Universe definition (same as in-sample).
4. Event backtest execution.
5. Save the results, appending a new study
   (`"in_sample_signal_sweep_event"`) to the same `.iafbt` bundles
   already containing the in-sample vector study. Each appended
   study has *x* runs per variant. Shared fingerprint makes the
   event-engine study discoverable next to the original.

> **Coverage:** ⚠️ Phase 3b — multi-study per bundle.

### Event backtests on the same study (new engine slot)

1. Load the strategy variants from `"in_sample_signal_sweep"` you
   want to evaluate via the event engine.
2. Universe definition (same as in-sample).
3. Event backtest execution.
4. Save the results, populating the `event` engine slot on the
   *existing* `"in_sample_signal_sweep"` study (the study isn't new
   — only its `event` slot is). Each bundle's existing study now
   has both `vector` and `event` slots, each with *x* runs per
   variant. Discoverable via the shared fingerprint *and* the
   shared study name.

> **Coverage:** ✅ Phase 3a — both `vector` and `event` slots
> already coexist on the same `Backtest` (via the legacy
> `vector_runs` / `event_runs` fields, surfaced as
> `Study.engines["vector"]` / `Study.engines["event"]`).

---

## Outer envelope

```
+-----------+-----------+--------------------------------+
| 4 bytes   | 4 bytes   |  N bytes                       |
| "IAFB"    | uint32 LE | zstd(level=7, msgpack(doc))    |
+-----------+-----------+--------------------------------+
  magic       version     compressed body
```

The 4-byte little-endian uint32 holds the format version (1 or 2).
The body is always zstd-compressed MessagePack with `use_bin_type=True`.

Readers MUST reject any version > the highest they support, and SHOULD
inspect the magic before attempting to decompress.

---

### Engine routing

| `engine_type` | Runs key      | Summary key       |
| ------------- | ------------- | ----------------- |
| `"vector"`    | `vector_runs` | `vector_metrics`  |
| `"event"`     | `event_runs`  | `event_metrics`   |

A bundle holds exactly **one** engine's results. Mixing engines in a
single bundle is not supported in v2 — produce two bundles and store
them in the same directory.

### Metric blob extraction

Eight `BacktestMetrics` fields are extracted from each run's
`backtest_metrics` dict and replaced with a `{"@blob": "<key>"}`
reference; the actual Parquet bytes go into the top-level `blobs` map.

The eight fields are all `List[Tuple[float, datetime|date]]`:

- `equity_curve`
- `drawdown_series`
- `cumulative_return_series`
- `rolling_sharpe_ratio`
- `monthly_returns`
- `yearly_returns`
- `twr_equity_curve`
- `twr_drawdown_series`

Each blob is a 2-column Parquet file (zstd compression level 5):

| Column | Type   | Semantics                                  |
| ------ | ------ | ------------------------------------------ |
| `ts`   | int64  | UTC epoch milliseconds                     |
| `value`| float64| The metric value                           |

The blob key follows the convention
`runs/<index>/metrics/<field_name>.parquet` where `<index>` is the
zero-based offset of the run within `vector_runs` / `event_runs` /
`backtest_runs` and `<field_name>` is one of the eight names above.

If a series has fewer than 2 entries, the writer leaves it inline
(no blob extraction). Readers MUST handle both cases for any field.

### Other fields

Fields that are NOT extracted into Parquet blobs in v2:

- `portfolio_snapshots`, `trades`, `orders`, `positions` — stay as
  msgpack lists of dicts. Their schemas are unstable across model
  changes, and msgpack is sufficient for the typical row counts.
- All scalar metrics (`sharpe_ratio`, `max_drawdown`, etc.) — stay
  inline. The whole point is keeping these fast to read.
- `signals`, `signal_events`, `recorded_values`, `data_sources`,
  `metadata` on each run — stay inline.

A future v2.x revision MAY extract additional fields. Readers MUST
treat the `blobs` map as authoritative: any key found there
overrides the inline value (the writer is required to leave the
inline placeholder as `{"@blob": "<key>"}` to make this unambiguous).

---

## Reader contract

`open_bundle(path)` MUST:

1. Read 8 bytes; verify magic, parse version.
2. Decompress (zstd) and unpack (msgpack) the body.
3. If `version == 1`: dispatch through the v1 reader (legacy
   `{"backtest": <to_dict>}` envelope).
4. If `version == 2`: route runs/summary based on `engine_type`,
   resolve blob references against the `blobs` map (replacing each
   `{"@blob": "<key>"}` with the decoded `[(value, iso_string), ...]`
   list), and reconstruct a `Backtest` via `Backtest.from_dict`.
5. Reject any `version > BUNDLE_FORMAT_VERSION`.

### Summary-only mode

`open_bundle(path, summary_only=True)` skips the Parquet decode step.
Each blob reference is replaced with an empty list (so
`BacktestMetrics.from_dict` doesn't choke). All scalar summary
metrics (Sharpe, Sortino, max DD, CAGR, win-rate, …) remain fully
populated. Use this for bulk listing / ranking pipelines that don't
draw charts.

---

## Writer contract

`save_bundle(backtest, path)` MUST:

1. Default to `format_version = BUNDLE_FORMAT_VERSION` (currently 2).
2. Accept `format_version=1` for explicit downgrade.
3. Write atomically (write to `<path>.tmp`, then `os.replace`).
4. Set `engine_type` from `backtest.engine_type`.
5. For v2: extract the eight metric series into Parquet blobs only
   when the source list has at least one usable `(value, datetime)`
   pair; leave malformed or empty series inline.

### OHLCV float32 quantization

`save_bundle(..., float32_ohlcv=True)` downcasts float64 OHLCV
columns to float32 before Parquet encoding. Typical reduction is ~2x
on the OHLCV side store; backtest metrics are unaffected for
crypto / equity time series. Off by default to preserve the v1
exact-round-trip contract — opt in for upload / archive workflows.

---

## Size expectations

For a 10-year daily backtest with one run, three trades per week,
typical metric-series savings:

| Item                           | v1 inline (ISO strings)| v2 Parquet blob |
| ------------------------------ | ----------------------:| ---------------:|
| `equity_curve` (2,500 entries) | ~120 KB                | ~25 KB          |
| `drawdown_series` (2,500)      | ~120 KB                | ~22 KB          |
| `monthly_returns` (120)        | ~6 KB                  | ~2 KB           |
| 8 series total                 | ~500 KB                | ~80 KB          |

Typical full-bundle size reduction for "metric-heavy" backtests
(many runs, long horizons): **30-80%**. For "snapshot-heavy"
backtests where `portfolio_snapshots` dominates, savings are smaller
(snapshots aren't extracted in v2.0); a future v2.x revision will
address this.

For tiny / smoke-test backtests with <50 entries per series, v2 can
be **slightly larger** than v1 because Parquet's per-file overhead
(~100 bytes) exceeds the savings. This is expected and harmless.

---

## Versioning policy

- Bumping the bundle `format_version` integer is a **breaking change
  for readers** of older framework versions.
- The framework will continue to read all historical versions
  indefinitely. There is no plan to drop v1 read support.
- Writers default to the highest version the framework knows about.
- Additive changes within v2 (e.g. extracting more fields into
  blobs) MUST be safe for v2 readers that don't know about the new
  blobs — they should receive the inline value as a fallback.
- A bundle with `format_version=2` MAY contain blob keys the reader
  doesn't recognise. Readers MUST ignore unknown blob keys.
