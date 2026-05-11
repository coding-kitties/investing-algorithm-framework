---
sidebar_position: 11
---

# Backtest Storage Layer

Once you start sweeping parameter grids and walk-forward windows, you quickly end up with **hundreds or thousands of backtests on disk**. A flat folder of `.iafbt` bundles works for tens of them, but it stops scaling once you want to compare them all in a single HTML dashboard — every comparison re-decodes multi-MB Parquet metric blobs just to read a Sharpe number, and the resulting `report.html` becomes too heavy for a browser to open.

The **backtest storage layer** is the framework's answer to that. It separates *where bundles live* from *how you query them*, and it gives you the tools to keep your dashboards fast even when the backing collection grows into the thousands.

## Mental model

```
                ┌─────────────────────────────────────────────┐
                │  Tier-1: SQLite index   (index.sqlite)      │
                │   - one row per .iafbt                      │
                │   - all summary metrics promoted to columns │
                │   - sub-100 ms ranks / filters over 10k+    │
                └─────────────────────────────────────────────┘
                                    │ derived from
                                    ▼
                ┌─────────────────────────────────────────────┐
                │  Tier-2: Parquet sidecars (analytics-ready) │
                │   - hive-partitioned on run_id              │
                │   - portfolio_snapshots / trades / orders   │
                └─────────────────────────────────────────────┘
                                    │ derived from
                                    ▼
                ┌─────────────────────────────────────────────┐
                │  CANONICAL: .iafbt bundles                  │
                │   - the single source of truth              │
                │   - everything else can be rebuilt from it  │
                └─────────────────────────────────────────────┘
                                    │ references
                                    ▼
                ┌─────────────────────────────────────────────┐
                │  Tier-3: content-addressed OHLCV chunks     │
                │   - <sha256>.parquet, deduped across all    │
                │     bundles that reference the same data    │
                └─────────────────────────────────────────────┘
```

The `.iafbt` bundle is **canonical**. The SQLite index, the Tier-2 Parquet sidecars and the Tier-3 OHLCV chunks are all *derived* — they can be rebuilt from the bundles at any time and they're best-effort: a malformed sidecar never blocks a write or read against the bundle.

## The `BacktestStore` protocol

Two concrete implementations ship today, both exposing the same API:

| Store | Layout | Best for |
|---|---|---|
| `LocalDirStore` | flat folder of `.iafbt` files (+ `index.sqlite`) | Most users, simple to inspect, fast `ls` |
| `LocalTieredStore` | full Tier-1/2/3 layout | Large collections, OHLCV dedup, analytics workflows |

Both are drop-in interchangeable — swap the implementation without touching call sites:

```python
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
)
from investing_algorithm_framework.services.backtest_store.\
local_tiered_store import LocalTieredStore

store = LocalDirStore("./my-backtests/")
# store = LocalTieredStore("./my-backtests/")  # same API

len(store)                       # how many bundles?
"momentum_v1.iafbt" in store     # exists?
bt = store.open("momentum_v1.iafbt")
for handle in store.iter_handles():
    ...
```

## The normal developer workflow

Below is the canonical loop most users will run. The **same five steps** hold whether you have 10 backtests or 10,000 — you just lean harder on the index as the collection grows.

### 1. Run a sweep, persist the bundles

```python
backtests = app.run_vector_backtests(
    strategies=[StrategyA(), StrategyB(), StrategyC()],
    backtest_date_ranges=[range_2022, range_2023, range_2024],
    n_workers=-1,
    backtest_storage_directory="./my-backtests/",   # writes .iafbt here
    show_progress=True,
)
```

After this you have a folder of `.iafbt` bundles on disk. That folder is *the* artifact — everything downstream operates on it.

### 2. Build the Tier-1 index

```bash
iaf index ./my-backtests/
```

Or from Python:

```python
from investing_algorithm_framework.cli.index_command import build_index
build_index("./my-backtests/")
```

This walks the folder once, writes `index.sqlite` with every scalar from `BacktestSummaryMetrics` promoted to its own column, and is **idempotent** — re-run it any time after adding new bundles.

### 3. Filter / rank in SQLite (no bundles opened)

The point of the index is that **you never need to decode a Parquet metric blob just to choose which backtests are interesting**. Pick winners with a SQL `WHERE` clause:

```python
from investing_algorithm_framework.cli.index_command import (
    list_index, rank_index,
)

# Top 20 by Sharpe, but only among bundles with > 50 trades.
top = rank_index(
    "./my-backtests/",
    by="sharpe_ratio",
    where="summary_number_of_trades > 50",
    limit=20,
)

for r in top:
    print(r["algorithm_id"], r["summary_sharpe_ratio"])
```

Or from the shell:

```bash
iaf rank ./my-backtests/ \
    --by sharpe_ratio \
    --where "summary_number_of_trades > 50" -n 20
iaf list ./my-backtests/ --sort calmar_ratio --json
```

This step is **sub-100 ms** even over 10k+ bundles. No Parquet, no decompression, no bundle opens.

### 4. Materialise only the bundles you actually need

```python
store = LocalDirStore("./my-backtests/")
backtests = [store.open(row["bundle_path"]) for row in top]
```

`bundle_path` from the index row is exactly the store handle, so this is a one-liner. **You only pay the bundle-decode cost for the bundles you selected**, not the whole collection.

### 5. Render the report

```python
from investing_algorithm_framework import BacktestReport

BacktestReport(backtests=backtests).save("top20.html")
```

That's the whole loop.

## Avoid overloading your `report.html`

The `BacktestReport` produces a **self-contained** HTML file: every backtest's full per-run data (equity curve, drawdown series, trades, positions, monthly returns) is inlined into the document so the dashboard works offline with no server.

The trade-off: file size grows linearly with the number of backtests inlined. Rough orders of magnitude:

| Backtests in report | Approx. HTML size | Browser experience |
|---|---|---|
| 1 – 10 | tens of KB to ~1 MB | instant |
| 10 – 50 | a few MB | smooth |
| 50 – 200 | 10 – 50 MB | slower load, still usable |
| 200+ | 100 MB+ | browsers struggle / refuse to open |

The point of the storage layer is that **you don't need to put 200 backtests in one report to compare them**. The Tier-1 index is your comparison surface for the full collection; the HTML report is your deep-dive surface for a small, hand-picked subset.

### Anti-pattern

```python
# DON'T do this with thousands of bundles.
report = BacktestReport.open(directory_path="./my-backtests/", workers=-1)
report.save("everything.html")     # multi-hundred-MB file, browser dies
```

This decodes every bundle in the folder and inlines all of them. Fine for a few dozen; fatal at scale.

### The right pattern

```python
# Filter in SQLite first, then render only the winners.
top = rank_index("./my-backtests/", by="sharpe_ratio", limit=25)
store = LocalDirStore("./my-backtests/")
BacktestReport(
    backtests=[store.open(r["bundle_path"]) for r in top],
).save("top25_by_sharpe.html")
```

Same principle applies for slicing by anything else — most-trades, best-Calmar, lowest-drawdown, only-2024-windows, only-momentum-strategies, etc. Compose multiple narrow reports rather than one giant one.

### Rules of thumb

- **Keep any single `report.html` to ≤ 50 backtests.** Past that, render multiple narrower reports (one per strategy family, one per regime, one for the top-N) instead of one mega-report.
- **Use the index as your comparison plane** for the full collection. CLI: `iaf list` / `iaf rank`. Python: `list_index` / `rank_index`. SQL: `sqlite3 index.sqlite` for anything ad-hoc.
- **Render for the audience.** A "winners" report (top 10–20) is what you actually send to teammates. A "full deep-dive" report on one strategy is what you keep for yourself.
- **Don't trust `BacktestReport.open(directory_path=…)` at scale.** It walks and decodes the whole folder; it's a convenience for ≤ 50-bundle directories, not a scaling story.

## When to use which store

- **`LocalDirStore`** — start here. A flat folder of `.iafbt` files is what every other tool understands (you can `ls`, `rsync`, `tar`, `git lfs` it). Tier-1 SQLite gets built next to the bundles. This is the default for `app.run_vector_backtests(backtest_storage_directory=...)`.

- **`LocalTieredStore`** — switch to this when you need any of:
  - **Cross-bundle analytics** without decoding bundles (DuckDB / Polars over the Tier-2 Parquet sidecars: `read_parquet('store/parquet/trades/**/*.parquet', hive_partitioning=True)`).
  - **OHLCV deduplication** — every bundle that references the same `BTC/EUR:1h` data shares one `<sha256>.parquet` blob on disk; reclaim orphans with `store.garbage_collect_ohlcv()`.
  - **Migration target** for archival / production pipelines.

Move a whole collection between store kinds with a single command:

```bash
iaf migrate-store --from local-dir    --src ./my-backtests/ \
                  --to   local-tiered --dst ./tiered/
```

## End-to-end runnable example

A complete worked example (seed bundles → build index → rank → load winners → render dashboard) lives in the repo at [`examples/storage_layer_demo/`](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/storage_layer_demo). Run it from a checkout:

```bash
source .venv/bin/activate
python examples/storage_layer_demo/demo.py
```

It prints each step, leaves the bundles + index + dashboard in a temp directory, and shows you the exact `iaf` CLI commands you could run by hand against the same data.

## Reference

- CLI: `iaf index`, `iaf list`, `iaf rank`, `iaf migrate-store` (see `iaf <cmd> --help`)
- Python: `investing_algorithm_framework.cli.index_command.{build_index, list_index, rank_index}`
- Stores: `investing_algorithm_framework.services.backtest_store.{LocalDirStore, LocalTieredStore}`
- Bundle format: see [Backtest Data](../Data/backtest_data.md)
- Report API: see [Backtest Reports](./backtest-reports.md)
