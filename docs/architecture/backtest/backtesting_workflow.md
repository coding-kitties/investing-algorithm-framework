# Backtesting Workflow — Design Rationale

Why the backtest format is designed the way it is, and how it
supports state-of-the-art quantitative strategy evaluation at
scale.

---

## The Problem

Most backtesting tools produce a single result file per run: one
equity curve, one Sharpe ratio, one set of trades. When you run a
parameter sweep of 96 combinations across 10 rolling windows, you
end up with 960 disconnected result files. Comparing them requires
ad-hoc scripts. Adding an out-of-sample study means another 960
files in a different folder. Switching from a fast vectorised
engine to a realistic event engine doubles the count again.

This does not scale, not in file management, not in analysis, and
not in the statistical rigour you can apply to the results.

The bundle format was designed to solve this by making a single
file the unit of evidence for one strategy variant, regardless of
how many studies, windows, engines, or validation passes you run.

---

## Design Principles

### Inspecting an index without loading bundles

`BacktestIndex` provides distinct entity counts and sorted identifier lists
directly from its scalar DataFrame:

```python
result.get_number_of_algorithms()
result.get_number_of_studies()
result.get_number_of_engines()
result.get_number_of_universes()

result.get_algorithm_ids()
result.get_study_names()
result.get_engine_types()   # Stored strings such as "event" and "vector"
result.get_universe_keys()

result.get_summary()
# {
#     "number_of_rows": ...,
#     "number_of_algorithms": ...,
#     "number_of_studies": ...,
#     "number_of_engines": ...,
#     "number_of_universes": ...,
# }
```

`len(result)` continues to count rows, not algorithms: one algorithm may
appear in multiple study, engine, and universe rows. Study counts use
distinct names across algorithms; universe counts use distinct recorded
keys, not individual symbols, and exclude null pooled rows. Null identifiers
are excluded from every entity count/list. Empty indexes return zero counts
and empty lists. Missing identity columns on a nonempty index raise an
explicit error instead of silently reporting zero.

All utilities describe the **current** DataFrame, so filtering an index
automatically changes its counts. They never open a backtest bundle and
do not modify the index or its persistence format. Window/run counts are
not inferred from row counts because these rows contain aggregated results.
`get_summary()` describes index contents, not aggregate performance metrics.

### Loading one indexed backtest

Retrieve a saved bundle by algorithm ID directly from the index:

```python
backtest = result.get_backtest("risk_rules_enabled")
if backtest is None:
    raise ValueError("Algorithm is not present in this index")
```

The lookup uses the recorded `bundle_path` relative to the index directory,
not an assumed algorithm-based filename. It respects the current rows,
including any filters. Repeated study, engine, or universe rows referencing
one bundle load it only once. An unknown or filtered-out ID returns `None`;
multiple distinct bundles for one ID raise an explicit error so the caller
can narrow the index first. Invalid paths and bundle loading errors propagate.
The loaded bundle retains its full contents; filtering index rows does not
filter studies or runs inside the bundle.

This method does not load captured diagnostics. Use `result.load_run_reports()`
explicitly when charting persisted decision traces, as described below.

To display performance for a particular study/window, pass the index
directly to the existing run-table utility:

```python
from investing_algorithm_framework import show_backtest_runs

show_backtest_runs(
    backtest_index=result,
    workers=1,
    study=study.name,
    run=backtest_window,
    engine="event",
    columns=[
        ("initial_unallocated", "Initial balance (EUR)", ",.2f"),
        ("final_value", "Final equity (EUR)", ",.2f"),
        ("number_of_trades", "Trades", "d"),
        ("number_of_trades_closed", "Closed trades", "d"),
        ("number_of_trades_open_at_end", "Open trades at end", "d"),
        ("number_of_orders", "Orders submitted", "d"),
        ("cagr", "CAGR", ".2%"),
        ("sharpe_ratio", "Sharpe", ".2f"),
        ("total_net_gain", "Net gain (EUR)", ",.2f"),
        ("max_drawdown", "Max drawdown", ".2%"),
        ("win_rate", "Closed-trade win rate", ".2%"),
    ],
)
```

Unlike the metadata utilities, this loads the indexed bundles to access
per-run metrics. Duplicate paths are loaded once. `workers=1` loads
sequentially; omitting it uses the existing loader's worker default.
Loading failures raise rather than rendering an incomplete table.
Study, engine, window, sorting, and pagination behave exactly as for the
existing `show_backtest_runs(backtests=[...])` API; those filters apply to
the contents of the loaded bundles. Supply either `backtests` or
`backtest_index`, never both. `workers` is only applicable to the index
form. Empty indexes display the usual no-data table.
Bare column format specs use raw stored values: `".2%"` formats a decimal
ratio such as 0.25 as 25.00%, while `",.2f"` formats currency with thousands
separators. Existing template formats such as `"{:.2f}"` retain the legacy
percentage-point conversion for ratio metrics.

Run tables also accept scalar `BacktestRun` fields such as
`number_of_orders`, including for `sort_by`. Metric fields take precedence
when both objects define an attribute. The order count is the persisted
per-run count of submitted orders across all statuses, not the number of
signals or fills; cumulative run-report snapshots must not be summed.
Summary tables do not synthesize these run-only fields and show `N/A`
when a requested field is unavailable.

Initial balance applies independently to each algorithm's run. Final
equity includes open positions, whereas closed-trade counts and win rate
describe realized trades. Scaling in can create additional trade lots.
Display configuration separately from outcomes: position sizing, scaling
limits (including `cooldown_in_bars`), cooldown rules, fixed/trailing stop
losses, and take profits are strategy settings, not performance metrics.
Empty rule lists mean not configured; an indicator-based exit or an ATR
entry filter is not a protective stop loss. When displaying current
strategy instances, label them as current configuration rather than as
historical settings recovered from a bundle.

### Opt-in in-memory event accounting

SQL remains the default event accounting backend. For faster event backtests,
opt into the existing Python memory backend:

```python
result = app.run_backtest(
    strategy=strategy,
    study=study,
    run_configuration=BacktestRunConfiguration(
        event_state_backend="memory",
    ),
)
```

This keeps current portfolios and positions resident, together with a hot set
of created/open orders, created/open trades, active stop-loss/take-profit rules,
and pending exit allocations. Active accounting records retain scalar fields
and relationship IDs, not complete ORM object graphs. Reads still return
detached values: editing a returned trade or nested order does not persist
anything until an explicit save/update.

Terminal orders, closed trades, inactive risk rules and settled allocations
move to the existing temporary disk archive. Snapshots remain archive-backed.
The same order/trade services, fill evaluation, risk hooks and reports operate
on this state; no separate simplified execution engine is introduced. Python
memory accounting needs no Rust extension, and the strict Rust backend keeps
its existing archive behavior.

The hot set grows with active exposure, not completed history. This is not a
hard memory cap: unbounded open orders, large per-trade relationships, result
materialization and captured run reports can still consume substantial memory.
The private archive index still uses SQLite, even when SQLAlchemy tick
statement counts are zero. Temporary archives are scratch state, not crash
recovery or resumable live accounting.

An offline 500-candle confluence workload (20 trades, 39 orders, 42 snapshots)
measured **3.55 s archive-only versus 3.11 s with active-state caching and
immutable-copy optimization**, using alternating runs and three samples per
variant. Separate three-run validations measured 2.81-3.25 s. The final run
retained only one open trade and its active stop loss; 39 orders, 19 closed
trades, 19 inactive stop losses and 38 settled allocations were archived.
Canonical memory results match the pre-change results byte-for-byte, including signals,
orders, trades, positions, snapshots and metrics. These are local full-app
measurements, not just indicator timings or a general speed guarantee; they
do not establish bit-for-bit equivalence between SQL and memory accounting.

Reproduce the full-app workload and inspect active/history row counts:

```sh
python -m scripts.bench_event_backtest \
    --rows 500 --repeats 3 --state-backend memory --profile \
    --result-json /tmp/event-memory-results.json
```

Use `--state-backend sql` for a separate SQL baseline. The benchmark reports
SQLAlchemy statements only; it does not count the private SQLite index.

### Optional historical run reports

With `show_progress=True`, a single event backtest displays a per-evaluation
progress bar. `IAF_PROGRESS_BACKEND=auto` selects notebook widgets when
available, otherwise warns and uses a text bar; `text` never requires widgets.
Explicit `notebook` mode requires `ipywidgets` in the selected kernel and
raises a clear error when `IProgress` is unavailable.

For a bounded strategy inspection, use the event engine and opt into the
same report shape used by live executions:

```python
study.engines = [BacktestEngine.EVENT_DRIVEN]
app.add_strategy(strategy)
result = app.run_backtest(
    study=study,
    run_configuration=BacktestRunConfiguration(
        capture_run_reports=True,
        persist_run_reports=True,
        n_workers=0,
        continue_on_error=False,
    ),
)
reports = result.run_reports
```

The return type remains `BacktestIndex`. `run_reports` defaults to `None`;
capture returns a list, including an empty list if nothing was evaluated.
Each report contains historical `timestamp`, `started_at`, and
`completed_at`, algorithm/study/window identification, per-tick signals
as flat entries with strategy IDs, timestamps and approval/rejection reasons,
recorded decision traces, and snapshots
of simulated orders, positions, portfolios, and trades. These are
independent snapshots, not references to later portfolio state.

Each report also has a unique string execution `id`, `algorithm_id`, and a
`strategy_ids` list. Reports are algorithm-level, not duplicated per strategy.
The environment is `BACKTEST`; `is_paper` and top-level `reason` are omitted.
Specific outcomes are recorded directly in `status`, with exception text
in `error`.

The top-level `indicators` list contains every evaluated indicator output and
explicitly recorded trace entry with `group="indicators"`, even on no-signal
ticks. Each entry has `strategy_id`, `symbol`, `timestamp`, `name`, and `value`.
Multi-output indicators have one entry per output column. Duplicate card traces
do not repeat values; unavailable warm-up values are `null`. Indicator snapshots
are captured only when run-report capture is enabled, are independent across
ticks, and round-trip through persisted report sidecars. A failed tick retains
indicator values evaluated before the exception. `context.record()` values
remain in `BacktestRun.recorded_values`, not this list.

Native evaluated indicator outputs are captured automatically; custom
observations can also be supplied by decision traces. The framework does not
recalculate indicators for reporting. A signal's trace remains in its metadata.

Event-engine reports also carry separate `stop_losses` and `take_profits`
lists for protective triggers and fill updates, including no-signal ticks.
Events retain their own timestamps, order/rule/trade identifiers, direction
and price source. Fill sequences distinguish partial executions; repeated
snapshots must be deduplicated. Resting exchange-mirror orders are not triggers.
These additive fields survive the existing gzip JSONL sidecar format and
explicit `load_run_reports()`. Vector report capture remains unsupported.

`confluence_scores` independently stores every evaluated confluence card,
including warm-up, no-signal and inactive scale-in-stage evaluations, with
strategy/symbol/timestamp attribution, readiness, scores, groups, rule
evaluations and a portable decision trace. Each card also records
`signal_status` (`approved`, `rejected`, `not_emitted`, or `unknown`) and
`signal_reason`, so a qualifying card blocked by an existing position,
cooldown, or inactive/completed scale-in stage explains why it did not lead
to an approved signal. Qualification is not overwritten by pipeline rejection,
and approval does not prove execution. Incomplete execution records an unknown
outcome rather than assuming approval. Generic traces remain separate.
New captures additionally save scoring capacity, per-rule weights, conditions,
observed native values and lookbacks, aggregation and qualification policy,
actual `signal_strength`, and `position_before` (filled open-lot counts and
configured entry limit). Inspectors can therefore work from a loaded backtest
and reports alone. Score utilization is score divided by maximum, not signal
strength. Older captures keep these details unavailable; no migration or current
configuration reconstruction is performed.
`data_sources` stores only the latest completed source row available to each
strategy at each tick, not its full history window. Entries include source
identifier, symbol, type, timeframe, evaluation timestamp, source-row timestamp,
and values such as OHLCV. Empty/unready sources retain an empty `values` object
and null row timestamp. Both lists are opt-in with report capture, JSON-safe,
independent across ticks, and persisted with the report. Source inputs and
already evaluated cards remain available in failed reports.

Capture alone is transient. Set `persist_run_reports=True` to additionally
write a versioned gzip-compressed JSON Lines sidecar in `run_reports/`.
Sidecars use format version 3. Older formats are not migrated or supported;
regenerate reports using the current framework.
Persistence requires capture; using it without `capture_run_reports=True`
raises a configuration error. Both options default to `False`. The setting
also supports `IAF_BACKTEST_PERSIST_RUN_REPORTS` with `from_env()`.

The sidecar is written once at the end of the invocation, after event
evaluations and metrics filters finish. Snapshot construction and retention
still happen at every captured evaluation; compression does not remove that
runtime or memory cost.

The framework publishes a complete sidecar atomically, then records its
relative `run_reports_path` in `backtest_session_index.parquet`. Each invocation
gets an immutable unique sidecar, even when an algorithm ID or storage
directory is reused. To retain multiple sessions in the same directory, keep
a copy of each session index before the next invocation replaces the default
session index. Keep those indexes and their `run_reports/` files together when
moving results; no reports are embedded in `.obtf` bundles or the global index.
Do not delete a sidecar while an index still references it.

Reopening an index remains lightweight and returns `run_reports=None`:

```python
index = BacktestIndex.open(
    backtest_results_directory,
    filename="backtest_session_index.parquet",
)
backtest = index.get_backtest("risk_rules_enabled")  # Bundle only
reports = index.load_run_reports(algorithm_id="risk_rules_enabled")
# Or: reports = index.load_run_reports()  # All selected rows
```

`load_run_reports()` returns a list without populating `index.run_reports` or
opening backtest bundles. It respects the current algorithm, study and engine
rows, deduplicates pooled/universe references, and preserves recorded window
identities and evaluation order within each sidecar. Universe rows share
algorithm-wide snapshots; they do not trim the report's symbols or contents.
An empty filtered index returns `[]`. An unknown/filtered-out requested
algorithm, absent persistence references, missing files, unsupported formats
or corrupt archives raise errors rather than masquerading as an empty capture.
Old indexes require a new captured-and-persisted run to gain diagnostics.

Capture replays checkpointed runs instead of silently returning a cached
backtest with no diagnostics. It preserves cumulative signal logs and
optional streamed signal history. Reports include all evaluated windows
and algorithms, including those subsequently pruned by metric filters;
`result.filter(...)` restricts the attached reports to surviving algorithm
ids. With `continue_on_error=True`, captured failed ticks retain their
error and `execution_error` (or `interrupted`) status.

Capture currently requires a single event engine, no optimization, and
sequential execution (`n_workers=None` or `0`); unsupported modes raise
explicit errors. Set `IAF_BACKTEST_CAPTURE_RUN_REPORTS=true` when using
`BacktestRunConfiguration.from_env()`. Prefer short inspection ranges:
full report snapshots (and explicitly loaded report lists) are retained in memory and are not bounded by the
backtest execution memory controls. Use ordinary backtest results for
large parameter screens.

### Experimental event-loop adapters

`BacktestService._create_event_loop_service(...)` is a protected factory
receiving the context, algorithm id, date range and study for an isolated
event run. The default constructs the ordinary `EventLoopService`.
Experimental subclasses can replace the loop without copying backtest
preparation, trade evaluation or bundle/index orchestration. They must
preserve scheduled execution, failure propagation and cleanup. This hook
does not certify feature or accounting parity for alternative loops.

Standalone adapters can reuse the public `prepare_backtest_data_sources`
function in `infrastructure.services.backtesting.backtest_service` with a
configured `DataProviderService`, data sources and a `BacktestDateRange`.
`BacktestService.initialize_data_sources_backtest` delegates to this same
function. It preserves registration, access-pattern-aware provider preparation,
prepared-market-data cache reuse and statistics, progress, and missing-data
options. Preparation failures propagate rather than being logged and suppressed.
It prepares the service's indexed providers and mutates their state; callers
must not share that service between concurrent active backtests.

### One bundle per algorithm, optional diagnostics alongside

A `.iafbt` bundle is keyed by `algorithm_id`. The algorithm id
is a unique identification for a strategy configuration. The framework creates it as a deterministic hash of the strategy's parameters by default, however its best if the developer provides a custom id

Every study (in-sample sweep, time-OOS, universe-OOS), every engine (vector, event), every
rolling window, and every Monte Carlo significance test for that
parameter combination lives in the same file.
Optional captured evaluation reports are the exception: their session-specific
compressed sidecars stay separate so normal bundle inspection remains light.

This means:

- **No file-juggling.** You never need to match result files from
  different folders or naming conventions. Open one bundle and you
  see everything that happened with that strategy variant.
- **Lineage is automatic.** When notebook 04 loads winning
  parameters from notebook 03 and re-hashes them, the OOS results
  land in the same bundle as the in-sample results. No explicit
  file-linking required.
- **Comparison is cheap.** Cross-study analysis (IS vs. OOS, vector
  vs. event) operates on a single in-memory object, not a join
  across files.

### Studies are first-class

A study is a named experimental context: one question, one
universe, one set of windows. The bundle format treats studies as
the primary organisational axis, not an afterthought.

```
Bundle (one algorithm_id)
└── studies
    ├── "in_sample_param_sweep"   → universe: BTC/ETH/ADA/SOL/DOT, 2022–2025
    ├── "out_sample_time_oos"     → universe: BTC/ETH, 2019–2021
    └── "out_sample_universe_oos" → universe: LINK/AVAX/ATOM/ALGO/XRP, 2022–2025
```

Each study owns:
- **One universe** — the asset basket this experiment runs against
- **One set of windows** — the date ranges used
- **Two engine slots** (vector and event) — each with its own
  runs, summary, and significance tests

This separation matters because quantitative evaluation requires
isolating variables. A time-OOS study and a universe-OOS study
test different hypotheses. Mixing their metrics in a single summary
would destroy the signal. The format keeps them apart while keeping
them together.

### Engine-agnostic, engine-aware

The bundle stores vector and event results side by side under each
study, but never mixes them. This supports the core workflow
pattern: explore fast with the vector engine, validate with the
event engine, then compare.

A strategy where the vector engine shows a Sharpe of 2.0 but the
event engine shows 0.3 has a timing or fill assumption baked in
it will fail in production. The format makes this comparison
trivial because both engines populate the same structure under the
same study.

### Summaries are materialised on disk, always recomputable

Each engine slot carries a `summary` that aggregates metrics across
all runs in that study. The framework materialises it on disk (so
rankers don't have to decode and aggregate every bundle), but also
**recomputes it from the run set** on `Backtest.save()`,
`Backtest.open()`, and `merge()` so per-engine summaries always
stay self-consistent with per-run metrics. This gives you three
properties at once:

- **Speed.** Ranking 10,000 bundles by Sharpe ratio should take
  milliseconds, not minutes. The materialised summary lets the
  Tier-1 index skip the run decode entirely.
- **Determinism.** Summaries are derived by one aggregation
  function (`generate_backtest_summary_metrics`) applied to the
  canonical run set. No risk of different tools producing
  different numbers from the same data.
- **Indexability.** The Tier-1 SQLite index (`build_index()`)
  promotes summary scalars into a flat table. This enables
  pure-SQL ranking and filtering without touching the binary
  bundles at all.

### Consistency and stability are first-class metrics

The summary does not just aggregate means — it measures
cross-window consistency and stability:

| Metric | What it measures |
|---|---|
| `return_consistency` | How stable are per-window returns? (1 - coefficient of variation) |
| `win_rate_consistency` | How stable is the win rate across windows? |
| `sharpe_consistency` | How stable is the Sharpe ratio across windows? |
| `consistency_score` | Weighted composite of the above + profitable window ratio |
| `return_stability` | How low is the standard deviation of per-window returns? |
| `stability_score` | Weighted composite of stability metrics |

A strategy that wins big on one window and loses on three scores
well on average return but poorly on consistency. The ranking
system weights both, and the `RISK_ADJUSTED` focus preset weighs
consistency and stability at 2.5 each — higher than raw return.

---

## Why This Format Does Not Limit You

### It supports any validation methodology

The format stores results, not methodology. The studies you create
and the order you run them in is your choice. The format does not
prescribe walk-forward vs. CPCV, or progressive pruning vs.
exhaustive search. It stores whatever you produce.

**Walk-forward rolling windows** — generate 10 windows, run them
sequentially with progressive pruning, store the survivors.

**Combinatorial Purged Cross-Validation (CPCV)** — generate all
$\binom{S}{S/2}$ train/test partitions with purging gaps, run
them, store the results as runs within a study. The format carries
arbitrary window sets; CPCV is just a different window generator.

**Monte Carlo permutation tests** — the bundle has a dedicated
`monte_carlo_tests` slot per engine per study. Each entry stores
the full `BacktestMetrics` from the real (un-permuted) run plus
the full `BacktestMetrics` from *every* permutation, and a
`p_values` dict keyed by metric name. One shuffle campaign
therefore yields p-values for many statistics simultaneously
(Sharpe, Sortino, CAGR, max-drawdown, …) from the same null pool.
See `docs/architecture/backtest/open_backtest_format.md` §Monte-Carlo test
structure.

**Deflated Sharpe Ratio** — requires the number of trials, the
observed Sharpe, skewness, kurtosis, and track record length. All
of these exist in the summary or can be derived from the runs. DSR
is a scoring function, not a storage format concern — it operates
on data the format already captures.

**IS→OOS decay analysis** — both the in-sample and OOS studies
live in the same bundle. Computing `oos_sharpe / is_sharpe` is a
single-object operation, not a cross-file join.

### It supports any execution model

Cost and fill assumptions are captured per study by three
pluggable models on `ExecutionConfig`:

- **`SlippageModel`** — how much price impact each fill takes.
  Built-ins range from `NoSlippage` (signal development) through
  scalar (`PercentageSlippage`, `FixedBasisPointsSlippage`) up to
  volume-aware (`VolumeImpactSlippage`, `VolumeShareSlippage`).
  Custom subclasses register automatically via `__init_subclass__`.
- **`CommissionModel`** — how the fee for each trade is computed.
  Built-ins: `NoCommission`, `PercentageCommission`,
  `FixedCommission`. Custom subclasses register the same way.
- **`FillModel`** — whether an order fills fully on the first bar
  (`FullFill`) or gets capped by traded volume (`VolumeBasedFill`,
  and any user extension).

All three models serialise as `{"type": <class_name>, "params":
{...}}` on disk, so the study's cost / fill assumptions stay
auditable and reproducible after the fact. See
`docs/architecture/backtest/open_backtest_format.md` §Execution config structure
and §Cost and slippage attribution for how each fill records the
applied slippage and commission on its `Order`, and how those roll
up into `Trade.cost` and `Trade.net_gain`.

Because the format stores results, not methodology, you can re-run
the same study under a more realistic model overlay and compare
directly — the runs are structurally identical.

### It scales to large sweeps

The three-tier storage architecture is designed for sweeps with
thousands of parameter combinations:

**Tier 0 — Bundle files.** One `.iafbt` per algorithm, binary
format (zstd-compressed msgpack). Compact and self-contained.

**Tier 1 — SQLite index.** `build_index()` scans bundle headers
and promotes every summary scalar into a flat SQLite table.
`rank_index()` runs weighted multi-metric scoring as a SQL query.
Ranking 10,000+ bundles takes milliseconds, with no full bundle
decode.

**Tier 2 — In-memory.** `Backtest.open()` materialises the full
object graph (runs, trades, equity curves) for detailed analysis
of selected winners only.

This means you can run a 10,000-combination sweep, rank them in
milliseconds via the index, promote the top 20, and only decode
those 20 for detailed analysis. The other 9,980 bundles stay on
disk untouched.

### It preserves lineage across notebooks

The `algorithm_id` is a deterministic hash of the strategy
parameters (excluding metadata keys prefixed with `_`). This
hash is the primary key for the bundle.

When a downstream notebook loads winning parameters from an
upstream notebook's bundles and re-hashes them, it gets the same
`algorithm_id`. The OOS or event-engine results land in the same
bundle file as the in-sample results — a new study slot is added,
not a new file.

The `anchor_algorithm_id` field extends this to perturbation
analysis: if you derive a variant by tweaking one parameter, the
variant's bundle records which original it came from. This
supports lineage trees where you can trace any strategy back to
the sweep that produced it.

### It supports regime-aware evaluation

Each run carries the full per-window metrics, and the study carries
the universe descriptor. This means you can:

- Filter runs by date range to isolate regime-specific performance
- Compare the same study across different universes
- Compute regime-conditional Sharpe ratios from the stored
  per-window metrics without re-running anything

The data for regime analysis is already in the bundle. The
`analyze_backtest_windows()` utility labels windows with regime
tags (bull, bear, sideways, high-vol). Carrying these labels
through to the run metadata is a small enhancement, not a format
change.

---

## How It Maps to a SOTA Pipeline

| SOTA Requirement | How the format supports it |
|---|---|
| Walk-forward with rolling windows | Studies carry arbitrary window lists; runs are keyed by date range |
| Progressive pruning | `window_filter_function` prunes between windows; survivors are the runs stored in the bundle |
| Multiple OOS axes (time + universe) | Separate studies in the same bundle, each with its own universe |
| Dual-engine validation | Vector and event slots under each study, same structure |
| Deflated Sharpe Ratio | Summary stores Sharpe, skewness, kurtosis, number of windows; DSR is a scoring function on existing data |
| Probability of Backtest Overfitting (CPCV) | CPCV partitions are just window sets — the format stores any window configuration |
| Monte Carlo significance tests | Dedicated `monte_carlo_tests` slot per engine per study |
| Familywise testing (White/Hansen) | Requires cross-bundle comparison — the SQLite index enables this at scale |
| IS→OOS decay ratio | Both studies in one bundle — single-object comparison |
| Market impact modelling | Event engine accepts any fill model; results stored identically |
| Regime-conditional evaluation | Per-window metrics + regime labels in run metadata |
| 10,000+ candidate ranking | Tier-1 SQLite index with millisecond weighted scoring |
| Bundle lineage and provenance | `algorithm_id` hash + `anchor_algorithm_id` edge |

---

## What the Format Deliberately Does Not Do

The format stores evidence. It does not prescribe how you produce
it or what conclusions you draw from it.

- **It does not enforce a specific validation methodology.** You
  choose walk-forward, CPCV, or something else. The format stores
  whatever runs you produce.
- **It does not compute statistical tests at save time.** DSR,
  PBO, and SPA are scoring and analysis functions that operate on
  the stored data. They belong in the analysis layer, not the
  storage layer.
- **It does not limit the number of studies.** You can have 2
  studies or 20. Each one is independent.
- **It does not limit the number of runs per study.** A study with
  10 rolling windows has 10 runs. One with 100 CPCV partitions
  has 100. The format handles both.
- **It does not couple strategy logic to result storage.** The
  same `TradingStrategy` class runs unchanged across vector
  backtest, event backtest, and live trading. The bundle is a
  pure output format.

The design goal is a format that captures everything you need for
rigorous evaluation, imposes no methodological constraints, and
scales from a single exploratory run to a production-grade research
pipeline with thousands of candidates.
