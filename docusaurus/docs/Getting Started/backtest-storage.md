---
sidebar_position: 11
---

# Backtest Storage Layer

Once you start sweeping parameter grids and walk-forward windows, you quickly end up with **hundreds or thousands of backtests on disk**. Comparing them all in a single HTML dashboard stops scaling at that point — every comparison re-decodes multi-MB metric blobs just to read a Sharpe number, and the resulting `report.html` becomes too heavy for a browser to open.

The **backtest storage layer** solves this with a simple idea: save your backtests to a folder, build a small SQLite index next to them, and filter/rank in that index *before* you ever open a bundle or render a report.

:::tip Just have a handful of backtests?
If you're only running a few backtests at a time, you probably don't need any of this — just pass them straight to `BacktestReport` as shown in [Backtest Reports](./backtest-reports.md). Come back here once you're sweeping large parameter grids.
:::

## Quick Start: the 5-step workflow

This is the loop most users run, whether they have 10 backtests or 10,000.

### 1. Run a sweep, persist the bundles

```python
backtests = app.run_vector_backtests(
    strategies=[StrategyA(), StrategyB(), StrategyC()],
    backtest_date_ranges=[range_2022, range_2023, range_2024],
    n_workers=-1,
    backtest_storage_directory="./my-backtests/",   # writes .obtf here
    show_progress=True,
)
```

This gives you a folder of `.obtf` bundle files — the single source of truth for everything downstream.

### 2. Build the index

```bash
iaf index ./my-backtests/
```

Or from Python:

```python
from investing_algorithm_framework.cli.index_command import build_index

build_index("./my-backtests/")
```

This writes an `index.sqlite` file next to your bundles, with every summary metric (Sharpe, Calmar, number of trades, etc.) promoted to its own column. It's **idempotent** — re-run it any time after adding new bundles.

### 3. Filter / rank without opening any bundles

```python
from investing_algorithm_framework.cli.index_command import rank_index

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
iaf rank ./my-backtests/ --by sharpe_ratio \
    --where "summary_number_of_trades > 50" -n 20
```

This is **sub-100 ms** even over 10k+ bundles — no bundles are opened at this step.

### 4. Load only the bundles you need

```python
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
)

store = LocalDirStore("./my-backtests/")
backtests = [store.open(row["bundle_path"]) for row in top]
```

You only pay the decode cost for the backtests you actually selected.

### 5. Render the report

```python
from investing_algorithm_framework import BacktestReport

BacktestReport(backtests=backtests).save("top20.html")
```

## Keeping `report.html` fast

`BacktestReport` inlines every backtest's full data (equity curve, trades, positions, etc.) into one self-contained HTML file, so size grows with how many backtests you put in it:

| Backtests in report | Approx. HTML size | Browser experience |
|---|---|---|
| 1 – 10 | tens of KB to ~1 MB | instant |
| 10 – 50 | a few MB | smooth |
| 50 – 200 | 10 – 50 MB | slower, still usable |
| 200+ | 100 MB+ | browsers struggle / refuse to open |

**Rule of thumb: keep any single report to ≤ 50 backtests.** Use the index (step 3 above) to pick the winners, and render a few focused reports (top strategies, best Calmar, one per regime) instead of one giant one:

```python
# DON'T: decodes and inlines every bundle in the folder.
report = BacktestReport.open(directory_path="./my-backtests/")
report.save("everything.html")     # can be 100s of MB

# DO: filter first, then render only the winners.
top = rank_index("./my-backtests/", by="sharpe_ratio", limit=25)
store = LocalDirStore("./my-backtests/")
BacktestReport(
    backtests=[store.open(r["bundle_path"]) for r in top],
).save("top25_by_sharpe.html")
```

## Scaling further: `LocalTieredStore`

`LocalDirStore` (a flat folder of `.obtf` files) is the default and is enough for most users — it's simple to inspect and works with normal tools (`ls`, `rsync`, `git lfs`).

If your collection grows very large, `LocalTieredStore` is a drop-in replacement with the same API that adds:
- **Cross-bundle analytics** over Parquet sidecars, without decoding bundles (e.g. with DuckDB/Polars).
- **OHLCV deduplication** across bundles that reference the same market data.

```python
from investing_algorithm_framework.services.backtest_store.\
local_tiered_store import LocalTieredStore

store = LocalTieredStore("./my-backtests/")  # same API as LocalDirStore
```

Migrate an existing collection with:

```bash
iaf migrate-store --from local-dir    --src ./my-backtests/ \
                  --to   local-tiered --dst ./tiered/
```

## Full example

A complete, runnable example (seed bundles → build index → rank → load winners → render dashboard) lives at [`examples/storage_layer_demo/`](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/storage_layer_demo):

```bash
source .venv/bin/activate
python examples/storage_layer_demo/demo.py
```

## Reference

- CLI: `iaf index`, `iaf list`, `iaf rank`, `iaf migrate-store` (see `iaf <cmd> --help`)
- Python: `investing_algorithm_framework.cli.index_command.{build_index, list_index, rank_index}`
- Stores: `investing_algorithm_framework.services.backtest_store.{LocalDirStore, LocalTieredStore}`
- Bundle format: see [Backtest Data](../Data/backtest_data.md)
- Report API: see [Backtest Reports](./backtest-reports.md)
