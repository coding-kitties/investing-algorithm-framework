# Storage layer demo — `iaf index`, `iaf list`, `iaf rank`

End-to-end demo of the new tiered backtest storage layer
(epic [#540](https://github.com/coding-kitties/investing-algorithm-framework/issues/540) — phase 2).

It shows how to:

1. Save a directory of `.iafbt` backtest bundles.
2. Build a SQLite Tier-1 index over them with `iaf index` (or
   `build_index` from Python).
3. Query / sort / filter the index with `iaf list` and `iaf rank`
   (or the equivalent `list_index` / `rank_index` Python helpers)
   without ever decoding the per-run Parquet metric blobs.
4. Drop into raw SQL when you need a custom report.

## Why this matters

Previously, comparing 50 walk-forward backtest variants meant
opening every `.iafbt` bundle (each with multi-MB Parquet metric
blobs) just to read scalar headline metrics like `sharpe_ratio` or
`max_drawdown`.

The new Tier-1 SQLite index gives you a single file (`index.sqlite`)
with one row per bundle and every scalar from
`BacktestSummaryMetrics` promoted to its own column. Filtering and
ranking 12,500 bundles becomes a sub-100 ms SQL query.

The `.iafbt` bundles themselves remain the source of truth — the
index can always be rebuilt from them with `iaf index`.

## Run it

From the repo root:

```bash
source .venv/bin/activate
python examples/storage_layer_demo/demo.py
```

The script will:

1. Create a temp directory and write 6 `.iafbt` bundles with
   varying synthetic Sharpe / Sortino / drawdown values.
2. Build `index.sqlite` over them.
3. Print the equivalent `iaf` CLI commands you could run by hand.
4. Run `list_index` / `rank_index` / a raw SQL query and print
   the formatted tables.
5. Open the top-ranked bundle and print its full backtest report
   (this is the only step that decodes per-run Parquet metric blobs).
6. Walk the index in rank order and print a one-line summary per
   bundle straight out of the SQLite index — no bundle is opened.
7. Iterate every bundle in rank order and print a full per-bundle
   report so you can scan _all_ backtests at a glance.

## CLI cheatsheet

```bash
# Build the index
iaf index ./my-backtests/

# Top 5 by Sharpe
iaf rank ./my-backtests/ --by sharpe_ratio -n 5

# Same, but only among bundles with > 50 trades
iaf rank ./my-backtests/ \
    --by sortino_ratio \
    --where "summary_number_of_trades > 50" \
    -n 10

# Full listing with custom columns + JSON output
iaf list ./my-backtests/ \
    --sort calmar_ratio \
    --columns "algorithm_id,tag,summary_calmar_ratio,summary_max_drawdown" \
    --json

# Raw SQL — anything sqlite3 can do
sqlite3 ./my-backtests/index.sqlite \
    "SELECT algorithm_id, summary_sharpe_ratio
       FROM backtest_index
      WHERE summary_max_drawdown > -0.1
      ORDER BY summary_sharpe_ratio DESC LIMIT 5;"
```

## Where this is going

Phase 3 of #540 introduces a `BacktestStore` Protocol with two
implementations: `LocalDirStore` (the current behavior) and
`LocalTieredStore` (Tier-1 SQLite + Tier-2 Parquet datasets +
Tier-3 content-addressed chunks). The `iaf list` / `iaf rank`
commands shown here are forward-compatible — they will work
unchanged against any store backing the same Tier-1 schema.
