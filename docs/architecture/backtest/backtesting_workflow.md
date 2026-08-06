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

### One file per algorithm, all evidence inside

A `.iafbt` bundle is keyed by `algorithm_id`. The algorithm id
is a unique identification for a strategy configuration. The framework creates it as a deterministic hash of the strategy's parameters by default, however its best if the developer provides a custom id

Every study (in-sample sweep, time-OOS, universe-OOS), every engine (vector, event), every
rolling window, and every Monte Carlo significance test for that
parameter combination lives in the same file.

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
