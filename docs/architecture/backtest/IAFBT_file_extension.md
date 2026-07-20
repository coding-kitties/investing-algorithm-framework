# The `.iafbt` File Format — What It Is and Why It Exists

**`.iafbt`** stands for **I**nvesting **A**lgorithm **F**ramework
**B**ack**T**est. One file = one algorithm's complete backtest evidence.

---

## What the file actually contains

An `.iafbt` file is a single binary container. At the outermost layer it
is an 8-byte header followed by a zstd-compressed MessagePack document:

```
+----------+----------+--------------------------------------+
| 4 bytes  | 4 bytes  |  N bytes                             |
| "IAFB"   | uint32 LE| zstd(level=19, msgpack(body))        |
+----------+----------+--------------------------------------+
  magic      version    compressed body
```

The body, once decompressed, contains everything needed to understand a
backtest in full — no external files required:

| What | Where in the body |
|------|-------------------|
| Algorithm identity — `algorithm_id`, `anchor_algorithm_id`, `parameters`, `strategy_ids`, `tag`, `metadata` | top-level keys |
| One or more **studies** (signal variants / universe slices) | `studies: dict[str, Study]` |
| Per-study **universe** — symbols, market, trading symbol, initial capital, risk-free rate | `studies[name]["universe"]` |
| Per-study **backtest windows** — train/test ranges, gap, warmup days | `studies[name]["backtest_windows"]` |
| Per-engine (vector / event) **runs** — every date-range window execution | `studies[name]["vector_runs"]` / `["event_runs"]` |
| Per-engine **summary metrics** — cross-window scalar roll-up (Sharpe, CAGR, max DD, …) | `studies[name]["vector_summary"]` / `["event_summary"]` |
| Per-universe summary caches | `studies[name]["vector_summaries_by_universe"]` |
| **Monte-Carlo significance tests** — null distributions, p-values | `studies[name]["monte_carlo_tests"]` |
| **Parquet blobs** — eight heavy time-series per run (equity curve, drawdown series, rolling Sharpe, monthly/yearly returns, TWR variants) extracted inline as `{"@blob": "<key>"}` and stored in the `blobs` map as raw Parquet bytes | `blobs: dict[str, bytes]` |
| Trades, orders, positions, portfolio snapshots | inside each run (msgpack inline) |
| Signals, signal events, recorded values, data-source descriptors | inside each run |

Nothing is split across files. You hand someone a `.iafbt` file and they
can reproduce every chart, every trade, every p-value from a
Monte-Carlo test, without needing access to a database, a data feed, or
any other artefact.

---

## How studies are composed

A `Study` is the central unit of evidence inside a bundle. Each study
represents one *hypothesis* — a signal definition, a parameter variant,
or a universe slice. Multiple studies can live inside one bundle.

### Study serialised shape (`studies[name]`)

```
study
├── name: str                             # stable identifier, e.g. "ema_cross"
├── description: str | null
├── metadata: dict[str, str]
│
├── universe: Universe | null             # see Universe fields below
├── backtest_windows: list[BacktestWindow]  # see BacktestWindow fields below
│
├── vector_runs: list[BacktestRun]        # runs produced by the vector engine
├── vector_summary: BacktestSummaryMetrics | null   # pooled cross-window roll-up
├── vector_summaries_by_universe: dict[str, BacktestSummaryMetrics]
│                                         # per-universe summary cache, keyed by Universe.key
│
├── event_runs: list[BacktestRun]         # same shape, event engine
├── event_summary: BacktestSummaryMetrics | null
├── event_summaries_by_universe: dict[str, BacktestSummaryMetrics]
│
└── monte_carlo_tests: list[MonteCarloTest]
```

Engine slots are **emitted only when populated** — a bundle that only
ran the vector engine will have an empty `event_runs` list and
`null` event summary. Readers MUST treat a missing or empty engine slot
as "not run", not as "zero results".

### Universe fields

A `Universe` describes *what* asset set the study was evaluated on —
the symbols, the exchange, the account currency, and the assumptions
used for risk-adjusted metrics.

```
universe
├── key: str              # stable identifier, auto-generated from the fields below
│                         #   format: "<symbols>|<trading_symbol>|<market>|<initial_capital>|<risk_free_rate>"
├── symbols: list[str]    # tradable assets, e.g. ["BTC", "ETH", "SOL"]
├── trading_symbol: str   # quote / accounting currency, e.g. "EUR"
├── market: str           # exchange identifier, e.g. "BITVAVO"
├── initial_capital: float | null   # starting cash for the study
├── risk_free_rate: float           # annualised risk-free rate used for Sharpe/Sortino
│                                   #   default 0.027 (2.7 %)
└── metadata: dict[str, str]        # free-form (data source tags, basket provenance, etc.)
```

The `key` is the join key between a run and its universe. Every
`BacktestRun` that belongs to this universe will have
`metadata["universe_key"] == universe.key`. The `summaries_by_universe`
dicts on the engine slot use this same key.

### BacktestWindow fields

A `BacktestWindow` describes one fold of the walk-forward split. The
study keeps a list of these so the window catalogue can be read without
scanning all run dates.

```
backtest_window
├── name: str | null           # human label, e.g. "fold_0" or "2020–2022"
├── fold_index: int | null     # zero-based index in a k-fold split; null for rolling windows
├── warmup_days: int           # days at the start of train_range reserved for indicator warm-up
│                              #   (e.g. a 26-day EMA needs 26 warmup days)
│                              #   these days are NOT counted as effective training
├── train_range:
│     ├── name: str | null     # e.g. "in_sample"
│     ├── start: str           # ISO 8601 UTC datetime
│     └── end: str             # ISO 8601 UTC datetime
└── test_range: null | {
      ├── name: str | null     # e.g. "out_of_sample"
      ├── start: str           # ISO 8601 UTC datetime
      └── end: str             # ISO 8601 UTC datetime
    }
```

`gap_days` (the gap between `train_range.end` and `test_range.start`)
is **not stored** — it is always derived on read as
`(test_range.start − train_range.end).days`. This keeps the window
definition canonical: there is only one source of truth for each date.

`test_range` is `null` for purely in-sample windows where no OOS period
has been defined yet.

---

## Why this format?

### 1. A single fingerprint per algorithm

The `algorithm_id` is a hash of the algorithm's code and configuration.
Every backtest produced by the same algorithm (in-sample, out-of-sample,
different universes, event engine) writes into the **same file**. No
directory archaeology, no cross-referencing CSV exports. One file, one
strategy identity.

The `anchor_algorithm_id` extends this with a lineage edge: perturbed
variants (cooldown stress tests, param robustness perturbations) point
back to their anchor so a single `GROUP BY anchor_algorithm_id` query
recovers an entire neighbourhood of related strategies.

### 2. Multi-study in one envelope

A `Study` is one hypothesis (a signal definition, a parameter variant, a
universe slice). Multiple studies can coexist in the same bundle:

- In-sample study + out-of-sample study for the same algo → same file.
- Vector study + event-engine study comparing the two engines → same file.
- Same strategy evaluated on three different crypto universes → three
  studies, same file.

Comparing apples-to-apples is trivial: everything is already in one place.

### 3. Both backtest engines coexist

The vector engine and the event engine produce structurally identical
result shapes (`vector_runs` / `event_runs`). A single bundle can hold
both, so you can quantify the gap between a vectorised approximation
and the event-driven ground truth without juggling two separate files.

### 4. Parquet blobs for heavy time series

Eight metric fields per run — equity curve, drawdown series, rolling
Sharpe, monthly returns, yearly returns, cumulative return series, and
their TWR variants — are extracted from the MessagePack body and stored
as compact Parquet bytes inside the `blobs` map. A typical equity curve
for a 10-year daily backtest shrinks from ~120 KB (ISO-string lists in
msgpack) to ~25 KB (zstd-compressed Parquet int64 timestamps +
float64 values).

Crucially, the **scalar summary metrics stay in the main body**. Reading
the body without decoding any blobs gives you the complete headline
numbers (Sharpe, CAGR, max DD, win rate, …) for every study and engine.
This is the `open_bundle(summary_only=True)` path — fast enough to rank
thousands of bundles without touching the blob layer.

### 5. Language-portable, no Python pickle

The body is MessagePack + zstd. The blob layer is Parquet. Both are
language-neutral, stable formats readable by any tooling (Rust, Go,
TypeScript, R) without a Python runtime. There is no pickle, no joblib,
no opaque serialisation.

### 6. Atomic writes, safe to copy

`save_bundle()` writes to `<path>.tmp` then calls `os.replace()` —
a POSIX atomic rename. A crash mid-write leaves the previous version
intact. The file is safe to `rsync`, copy to S3, or attach to a git
commit at any point.

### 7. Versioned for forward compatibility

The 4-byte little-endian version field in the header lets readers detect
format changes before attempting to decompress. The current version is
**5**. The framework reads all historical versions (1–5) and rejects
anything above the highest it knows about. Adding new fields to the body
document is always backwards-compatible within the same version; the
msgpack reader ignores unknown keys.

---

## When you open a bundle in Python

```python
from investing_algorithm_framework.domain.backtesting.bundle import (
    open_bundle, save_bundle,
)

# Full load — all runs, all time-series, all trades
backtest = open_bundle("my_algo.iafbt")

# Summary-only — scalars only, no Parquet decode (fast for ranking)
backtest = open_bundle("my_algo.iafbt", summary_only=True)

# Access results
study = backtest.get_study("default")
runs  = backtest.get_runs("vector")                 # list[BacktestRun]
summ  = backtest.get_summary("vector")              # BacktestSummaryMetrics
print(summ.sharpe_ratio, summ.cagr, summ.max_drawdown)
```

See [backtest_storage.md](backtest_storage.md) for the full on-disk
specification, blob key conventions, and reader/writer contracts.
See [data_model.md](data_model.md) for the complete in-memory type
hierarchy.
