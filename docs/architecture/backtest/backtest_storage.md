# The `.iafbt` Bundle File — Developer Reference

This document describes how a backtest is persisted on disk as an
`.iafbt` ("**I**nvesting **A**lgorithm **F**ramework **B**ack**T**est")
bundle. It is the working reference for developers building on,
inspecting, or interoperating with the format — including third-party
tooling (the Finterion upload CLI, ingestion pipelines, `debug_iafbt.py`).

Reference implementation: [investing_algorithm_framework/domain/backtesting/bundle.py](../../investing_algorithm_framework/domain/backtesting/bundle.py).

---

## 1. What an `.iafbt` file is

An `.iafbt` file is a **single, self-contained binary container** that
holds the full results of one algorithm's backtest, across one or more
studies (signal variants) and one or more rolling windows per study.

It stores:

- All run dicts — `vector_runs` / `event_runs` — inside each study
- Summary metrics (cross-window scalar roll-ups) per engine, per study
- Per-universe summary caches (`summaries_by_universe`)
- Per-run heavy time series: equity curve, drawdown, monthly/yearly
  returns, rolling Sharpe, TWR variants — extracted as Parquet blobs
- Trades, orders, positions, portfolio snapshots (msgpack inline)
- Signals, recorded values, data-source descriptors
- Algorithm ID, strategy IDs, parameters, tag, metadata
- Study identity: name, description, universe, backtest windows
- Optional Monte-Carlo test results
- Optional universe catalogue (multi-universe bundles)

The format is:

- **Versioned** — a `format_version` integer is encoded in the header.
- **Compressed** — zstd level 19 over a MessagePack document.
- **Language-portable** — anything that reads MessagePack + zstd + Parquet
  can decode it. No Python pickle anywhere.
- **Atomic on write** — `save_bundle()` writes to `<path>.tmp` and
  `os.replace`s it into place.

---

## 2. On-disk layout

### 2.1 Outer envelope

Every `.iafbt` file starts with a fixed 8-byte header:

```
+-----------+-----------+--------------------------------+
| 4 bytes   | 4 bytes   |  N bytes                       |
| "IAFB"    | uint32 LE | zstd(level=19, msgpack(doc))   |
+-----------+-----------+--------------------------------+
  magic       version     compressed body
```

- **Magic** (`b"IAFB"`): identifies the format. Readers MUST verify this
  before doing any work.
- **Version** (`uint32` little-endian): currently `5`. Readers MUST reject
  any value greater than the highest version they understand.
- **Body**: a zstd-compressed MessagePack document.

| Constant                | Value      | Defined in  |
|-------------------------|------------|-------------|
| `_MAGIC`                | `b"IAFB"`  | bundle.py   |
| `BUNDLE_EXT`            | `".iafbt"` | bundle.py   |
| `BUNDLE_FORMAT_VERSION` | `5`        | bundle.py   |
| `_ZSTD_LEVEL`           | `19`       | bundle.py   |

### 2.2 The body document (v5 — current)

After decompression and msgpack unpacking, the body is exactly the
output of `Backtest.to_dict()` plus a `format_version` key and an
optional `blobs` map. The canonical top-level shape is:

```python
{
    "format_version": 5,

    # Algorithm identity
    "algorithm_id": str,
    "anchor_algorithm_id": str | None,
    "tag": str | None,
    "strategy_ids": list[str],
    "parameters": dict,
    "metadata": dict,

    # Studies — one entry per strategy variant / signal.
    # Each value is a Study.to_dict() dict (see §2.3).
    "studies": {
        "<study_name>": { ... },
    },

    # Optional: universe catalogue for multi-universe bundles.
    # Present only when the Backtest was constructed with universes=[...].
    # Each entry is a Universe.to_dict() dict.
    "universes": [ { "key": str, "symbols": [...], ... }, ... ],

    # Optional: embedded Parquet blobs for heavy metric series.
    # Keys follow the per-study namespacing (see §3.1).
    "blobs": {
        "studies/<study_name>/<engine>_runs/<idx>/metrics/<field>.parquet": bytes,
    },
}
```

There are **no** top-level `engine_type`, `vector_runs`, `event_runs`,
`backtest_runs`, `study_name`, `study_description`, or `risk_free_rate`
keys. All per-study and per-engine data lives inside `studies`.

### 2.3 The study dict

Each entry in `studies` is the output of `Study.to_dict()`:

```python
{
    "name": str,                      # e.g. "in_sample_param_sweep"
    "description": str | None,

    # Single universe for this study. Universe.to_dict() shape:
    #   key, symbols, trading_symbol, market, initial_capital,
    #   risk_free_rate, metadata
    "universe": { ... } | None,

    # BacktestWindow list — one entry per rolling window / fold.
    # Each entry: {name, train_range, test_range, warmup_days, fold_index}
    # where train_range / test_range are {name, start, end} (ISO-8601).
    # gap_days is derived on read as (test_range.start - train_range.end).days.
    "backtest_windows": [ { ... }, ... ],

    "metadata": dict,

    # Monte-Carlo test results for this study.
    "monte_carlo_tests": [ { ... }, ... ],

    # Per-engine run lists and roll-up summaries.
    # These keys always appear; absent engines have empty lists / null.
    "vector_runs":                    [ <run_dict>, ... ],
    "vector_summary":                 <summary_dict> | None,
    "vector_summaries_by_universe":   { "<universe_key>": <summary_dict>, ... },

    "event_runs":                     [ <run_dict>, ... ],
    "event_summary":                  <summary_dict> | None,
    "event_summaries_by_universe":    { "<universe_key>": <summary_dict>, ... },
}
```

### 2.4 Legacy format versions (read-only)

| Version | Shape | Notes |
|---------|-------|-------|
| v1 | `{"format_version": 1, "backtest": <Backtest.to_dict()>, "ohlcv": ...}` | Heavy series inline as `[(float, iso)]` lists. No Parquet blobs. |
| v2–v4 | Top-level `engine_type`, `vector_runs`/`event_runs`, flat `study_name`/`universes` keys | Reader routes through `_envelope_to_backtest_dict` to normalise. |

All historical versions remain readable indefinitely. New code never writes v1–v4.

---

## 3. Heavy time series — Parquet blob extraction

### 3.1 Blob keying

Each heavy series is extracted out of the run's `backtest_metrics` dict
and stored as embedded Parquet bytes under the key:

```
studies/<study_name>/<engine>_runs/<index>/metrics/<field_name>.parquet
```

where `<engine>` is `vector` or `event`, `<index>` is the zero-based
offset of the run within that engine's run list, and `<field_name>` is
one of the eight series listed below.

The original field in `backtest_metrics` is replaced with a blob reference:

```python
{"@blob": "studies/in_sample_param_sweep/vector_runs/0/metrics/equity_curve.parquet"}
```

On read, blob references are resolved back to `[(value, iso_string), ...]`
so consumers always see the same shape regardless of storage format.

### 3.2 Which eight fields are extracted

All eight share the shape `List[[float_value, iso_datetime]]` when inline:

| Field                      | Notes |
|----------------------------|-------|
| `equity_curve`             | Portfolio value over time. |
| `drawdown_series`          | Drawdown vs running peak (decimal, ≤ 0). |
| `cumulative_return_series` | Cumulative return vs `initial_unallocated`. |
| `rolling_sharpe_ratio`     | Rolling Sharpe; window size is engine-defined. |
| `monthly_returns`          | One point per month; timestamp = end-of-month UTC. |
| `yearly_returns`           | One point per year; timestamp = year-boundary date. |
| `twr_equity_curve`         | Time-weighted-return variant — cash flows scrubbed. |
| `twr_drawdown_series`      | TWR variant of `drawdown_series`. |

### 3.3 Blob payload format

Each blob is a two-column Parquet table (zstd level 5):

| Column  | Type      | Semantics |
|---------|-----------|-----------|
| `ts`    | `int64`   | UTC epoch milliseconds. |
| `value` | `float64` | The metric value at that timestamp. |

### 3.4 Defensive encoding rules

- If a series has fewer than 2 usable entries it is left **inline**
  (Parquet per-file overhead exceeds the savings for tiny series).
- Readers MUST handle both blob references and inline lists for every
  one of the eight fields.
- `summary_only=True` skips Parquet decode; blob fields come back as `[]`.

---

## 4. OHLCV side store (optional)

When `save_bundle(..., include_ohlcv=True)`, OHLCV DataFrames are written
to a sibling content-addressed directory (`<bundle_parent>/ohlcv/`) and
the bundle embeds a manifest:

```python
"ohlcv": {
    "store_dir": "ohlcv",   # relative to the bundle file
    "manifest": {
        "BTC/USDT__1h": "a3f1c4...e9.parquet",
    },
}
```

On read, `backtest.ohlcv` exposes a `LazyOhlcvDict` — Parquet blobs are
decoded only when their key is accessed. See
[ohlcv-dedup-protocol.md](ohlcv-dedup-protocol.md) for cross-bundle
deduplication semantics.

---

## 5. Read and write APIs

### 5.1 Writer

```python
save_bundle(backtest, path, *, include_ohlcv=False, summary_only=False) -> Path
```

1. Calls `backtest.to_dict()` to get the canonical dict.
2. Adds `"format_version": BUNDLE_FORMAT_VERSION`.
3. Extracts the eight heavy series into Parquet blobs per study/engine/run.
4. Writes atomically (`<target>.tmp` → `os.replace`).

If `path` is a directory, the filename resolves to `<algorithm_id>.iafbt`.

### 5.2 Reader

```python
open_bundle(path, *, summary_only=False) -> Backtest
```

1. Reads 8 bytes; verifies magic; parses version.
2. Decompresses (zstd) and unpacks (msgpack).
3. For v5: passes the doc directly to `Backtest.from_dict()`.
4. For v1–v4: normalises through `_envelope_to_backtest_dict()` first.
5. Resolves every `{"@blob": ...}` reference (skipped when `summary_only=True`).

`summary_only=True` is the fast path for ranking pipelines — all scalar
summary metrics are populated; the eight heavy series come back as `[]`.

### 5.3 Detection

```python
is_bundle_file(path)   # True iff first 4 bytes == b"IAFB"
peek_bundle_format_version(path)  # int, no full decode needed
```

---

## 6. Quick reference — public surface

```python
from investing_algorithm_framework import (
    BUNDLE_FORMAT_VERSION,   # int, currently 5
    Backtest,
)
from investing_algorithm_framework.domain.backtesting.bundle import (
    BUNDLE_EXT,              # ".iafbt"
    save_bundle,
    open_bundle,             # supports summary_only=True
    is_bundle_file,
    peek_bundle_format_version,
)
```

---

## 7. Compatibility & versioning policy

- The framework reads **all historical versions** indefinitely.
- Writers always emit `BUNDLE_FORMAT_VERSION` (currently 5).
- The 4-byte `IAFB` magic and `uint32 LE` version field are guaranteed
  stable across all future versions.
- Additive changes within v5 (new keys inside a study dict) MUST be safe
  for existing v5 readers — unknown keys are ignored on read.

---

## 8. The run dict — full reference

A study's `vector_runs` / `event_runs` list contains one **run dict** per
backtest window. Each is the output of `BacktestRun.to_dict()` and is
reconstructed by `BacktestRun.from_dict()` on read.

### 8.1 Top-level run fields

#### Window identity & sizing

| Field                       | Type                  | Notes |
|-----------------------------|-----------------------|-------|
| `backtest_start_date`       | ISO-8601 string (UTC) | Inclusive start of this window. |
| `backtest_end_date`         | ISO-8601 string (UTC) | Inclusive end of this window. |
| `backtest_date_range_name`  | string \| null        | Human label (e.g. `"w1-train"`). |
| `created_at`                | ISO-8601 string (UTC) | When this run was produced. |
| `trading_symbol`            | string                | Quote currency (e.g. `"EUR"`). |
| `initial_unallocated`       | float                 | Starting cash for this window. |
| `number_of_days`            | int                   | `(end - start).days`. |
| `symbols`                   | list[string]          | All instruments traded during the window. |

#### Counters (denormalised for fast listing)

| Field                       | Type | Notes |
|-----------------------------|------|-------|
| `number_of_trades`          | int  | Total trades touched. |
| `number_of_trades_closed`   | int  | Closed inside the window. |
| `number_of_trades_open`     | int  | Still open at end. |
| `number_of_orders`          | int  | Orders placed. |
| `number_of_positions`       | int  | Distinct positions held. |

#### Free-form attachments

| Field          | Type           | Notes |
|----------------|----------------|-------|
| `metadata`     | dict[str, str] | Per-run free-form labels. The framework never inspects keys. |
| `data_sources` | list[dict]     | Descriptors for data consumed (provider, symbol, timeframe, start/end). |

### 8.2 `backtest_metrics` — per-run metrics dict

Serialised `BacktestMetrics`. Three layers:

1. **Window context** — repeats identity fields so the metrics object is
   self-contained.
2. **Scalar metrics** — every numeric performance / risk statistic. Always
   inline; populated by `summary_only=True`.
3. **Heavy time series** — the eight fields extracted into Parquet blobs
   (see §3). Come back as `[(value, iso_string), ...]` on read.

Key scalar fields:

| Field | Notes |
|-------|-------|
| `total_net_gain` / `_percentage` | Net P&L for this window. |
| `cagr` | Compound annual growth rate. |
| `sharpe_ratio` | Annualised; uses `study.universe.risk_free_rate`. |
| `sortino_ratio` / `calmar_ratio` / `profit_factor` | Standard risk-adjusted metrics. |
| `max_drawdown` / `max_drawdown_duration` | Decimal (≤ 0) and days. |
| `number_of_trades_closed` | Closed-trade count. |
| `win_rate` | Decimal share of winning closed trades. |
| `exposure_ratio` | Avg fraction of capital deployed. |

### 8.3 Trades, orders, positions, portfolio snapshots

Stored as msgpack lists of dicts on the run dict (not inside `backtest_metrics`).

| Field                | Element type |
|----------------------|--------------|
| `trades`             | `Trade.to_dict()` |
| `orders`             | `Order.to_dict()` |
| `positions`          | `Position.to_dict()` |
| `portfolio_snapshots`| `PortfolioSnapshot.to_dict()` — typically the largest collection. |

### 8.4 Signals, signal events, recorded values

| Field            | Notes |
|------------------|-------|
| `signals`        | `{symbol: {"buy": [iso_ts, ...], "sell": [iso_ts, ...]}}` — only `True` ticks kept. |
| `signal_events`  | Audit log: `[{date, symbol, signal, executed, reason}, ...]`. |
| `recorded_values`| Strategy-defined per-tick diagnostics: `{name: [{datetime, value}, ...]}`. |

---

## 9. The summary dict — full reference

Each study's engine slot carries a `vector_summary` / `event_summary` —
the serialised `BacktestSummaryMetrics` — representing an **aggregate
across all runs** in that slot.

The summary is the **source of truth for the Tier-1 SQLite index**. Every
scalar is promoted to its own column so `rank_index()` can sort 10k+
bundles without opening any `.iafbt`.

Key fields mirror the per-run metrics but aggregate across windows:

| Field | Notes |
|-------|-------|
| `total_net_gain` / `_percentage` | Sum across all windows. |
| `average_net_gain` / `_percentage` | Time-weighted mean across windows. |
| `sharpe_ratio` / `sortino_ratio` / `calmar_ratio` | Pooled across runs. |
| `max_drawdown` | Worst drawdown across all windows. |
| `number_of_windows` | Total window count. |
| `number_of_profitable_windows` | Windows with positive net gain. |
| `number_of_windows_with_trades` | Windows with ≥ 1 closed trade. |
| `return_consistency` / `win_rate_consistency` / `sharpe_consistency` | Cross-window stability scores (0–1). |
| `consistency_score` | Composite of the three stability scores. |

---
