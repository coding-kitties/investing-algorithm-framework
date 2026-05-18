# Bundle Format v2 — Public Specification

**Status:** Stable. Default writer since `v8.9.0` (May 2026).
**File extension:** `.iafbt`
**Backwards compatibility:** v1 bundles remain readable indefinitely.

This document describes the on-disk binary format produced by
`save_bundle()` and consumed by `open_bundle()` /
`Backtest.open()`. Third-party tools (e.g. the Finterion upload CLI
and ingestion pipeline) can rely on this contract.

---

## Why v2

v1 stored the entire `Backtest.to_dict()` graph as a single
zstd-compressed MessagePack document. That was already efficient for
small backtests, but two structural problems became visible at scale
(thousands of bundles per user):

1. **Heavy time series stored as JSON-ish lists of `(float,
   ISO-string)` tuples** — the strings dominate the on-disk size for
   long-running backtests (e.g. 10y daily ≈ 2,500 entries × 8 series).
   ISO-8601 strings are ~25 bytes each; an `int64` epoch-ms is 8 bytes
   and Parquet's columnar dictionary compression collapses repeated
   timestamps further.

2. **No way to distinguish vector from event backtests** in the
   on-disk envelope, even though they're produced by separate engines
   with subtly different semantics. Reports and analyses had to
   guess from filename or metadata.

v2 fixes both without breaking v1.

---

## Outer envelope (unchanged from v1)

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

## v2 document structure

```python
{
    "format_version": 2,
    "engine_type": "vector" | "event" | None,

    # Engine-agnostic top-level fields (carry across both engines)
    "algorithm_id": str,
    "metadata": dict,
    "risk_free_rate": float | None,
    "strategy_ids": list,
    "parameters": dict,
    "tag": str | None,
    "backtest_permutation_tests": list | None,

    # Exactly ONE of these pairs is populated based on engine_type:
    "vector_runs":    [run_dict, ...],   # if engine_type == "vector"
    "vector_metrics": summary_dict,       # if engine_type == "vector"

    "event_runs":     [run_dict, ...],   # if engine_type == "event"
    "event_metrics":  summary_dict,       # if engine_type == "event"

    # Fallback for legacy / unknown-engine bundles:
    "backtest_runs":    [run_dict, ...],  # if engine_type is None
    "backtest_summary": summary_dict,      # if engine_type is None

    # Optional: embedded heavy-series Parquet blobs
    "blobs": {
        "runs/<idx>/metrics/<field>.parquet": bytes,
        ...
    },

    # Optional: OHLCV manifest (unchanged from v1)
    "ohlcv": {
        "store_dir": str,                  # relative to bundle file
        "manifest": {key: relative_path},
    },
}
```

### Engine routing

| `engine_type` | Runs key      | Summary key       |
| ------------- | ------------- | ----------------- |
| `"vector"`    | `vector_runs` | `vector_metrics`  |
| `"event"`     | `event_runs`  | `event_metrics`   |
| `None`        | `backtest_runs` | `backtest_summary` |

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
