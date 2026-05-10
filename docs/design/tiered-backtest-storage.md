# Tiered Backtest Storage — Design

> Status: **Proposal**
> Targets: framework v8.10 (read-side) and v8.11 (store abstraction).
> Companion docs: [`bundle-format-v2.md`](./bundle-format-v2.md), [`ohlcv-dedup-protocol.md`](./ohlcv-dedup-protocol.md).

## 1. Motivation

Empirical measurements on a real production-shape archive (12,500 bundles, ~64 GB, 10 May 2026):

| Configuration | Avg / bundle | Total | Notes |
|---|---:|---:|---|
| v1, zstd 7 (pre-v8.9) | 569 KB | 64.0 GB | baseline |
| v2 + zstd 19 (v8.9, shipped) | 489 KB | ~55 GB | per-file ceiling |
| v2 + zstd 19 + daily snapshots | 431 KB | ~48 GB | requires user behaviour change |
| Tiered store + content-addressed dedup | n/a (decomposed) | **< 20 GB projected** | this proposal |

Two structural problems remain after v8.9:

1. **Per-file compression has hit its ceiling.** zstd at level 22 saturates at the same size as level 19. Within a single `.iafbt`, there is no remaining headroom.
2. **The `.iafbt` is the wrong primitive for two of the three real workloads.**
   - **Email / hand-off / archive** — single file is right.
   - **Listing / ranking / dashboard** — single file is wrong. Decoding 12,500 zstd payloads to read 50 scalar metrics each is a 30-minute loop instead of a 50 ms SQL query.
   - **Cross-run analytics** — single file is wrong. "Plot the equity curves for these 50 sweep variants" should be one DuckDB query, not 50 decode-and-merge round trips.

Cross-bundle redundancy is the dominant unexploited source of size:

- Strategy params/schema: identical across all bundles in a sweep
- Symbol metadata: identical across every bundle on the same universe
- OHLCV: same slice referenced by hundreds of bundles
- Recurring trade/order patterns: significant overlap when entry rules repeat

`zstd` cannot see across files. The fix lives one layer up.

## 2. Principles

1. A backtest is **not one thing** — it is a small header + heavy bulk + shared reference data. Treat them as separate citizens.
2. **Listing must not decode bulk.** Scalar metrics live in an indexable tier.
3. **Cross-bundle dedup is a storage concern**, not a per-file format trick.
4. **Columnar wins at scale, not per file.** Per-bundle Parquet was measured neutral-to-negative. Per-project Parquet over thousands of runs is a 10× analytics story.
5. **One canonical schema per artifact, additive forever.** No schema-on-read JSON.
6. **`.iafbt` becomes an export view, not the source of truth.** Assembled deterministically from the tiers on demand; still byte-portable.

## 3. The three-tier model

```
┌─────────────────────────────────────────────────────────────────┐
│  Tier 1 — Index  (Postgres / SQLite)                            │
│  One row per backtest run. All scalar metrics, params,          │
│  tags, dates, engine_type, plus refs into Tiers 2 & 3.          │
│  Indexed for sort, filter, rank, sweep comparison.              │
├─────────────────────────────────────────────────────────────────┤
│  Tier 2 — Columnar bulk  (Parquet on object storage)            │
│  Per-project Parquet datasets, partitioned by run_id:           │
│    portfolio_snapshots/   trades/   orders/   metric_series/    │
│  Queryable directly by DuckDB / Polars / Arrow.                 │
├─────────────────────────────────────────────────────────────────┤
│  Tier 3 — Content-addressed chunks  (S3-compatible)             │
│  SHA-256-keyed immutable blobs:                                 │
│  OHLCV slices, symbol metadata, strategy schemas, code.         │
│  One physical copy per unique chunk, per dedup scope.           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier 1 schema (sketch)

| Column class | Examples |
|---|---|
| Identity | `run_id` (uuid7), `bundle_id`, `parent_sweep_id`, `tenant_id`, `project_id` |
| Provenance | `algorithm_id`, `code_hash`, `framework_version`, `created_at` |
| Config | `engine_type`, `params_hash`, `symbols_hash`, `date_range_name`, `start_date`, `end_date`, `tag` |
| Scalar metrics | `BacktestSummary` fields — Sharpe, Sortino, max_dd, CAGR, total_net_gain, win_rate, … |
| Refs | `snapshots_dataset_uri`, `trades_dataset_uri`, `metric_series_dataset_uri`, `ohlcv_chunk_hashes[]`, `code_chunk_hash`, `symbols_chunk_hash`, `params_chunk_hash` |

Row size: ~1–2 KB. 12,500 rows ≈ 25 MB. Fits comfortably in SQLite for local users.

### 3.2 Tier 2 schemas (Parquet, long format)

`portfolio_snapshots/`:
```
run_id (string, dict-encoded)   — partition key
ts (int64, epoch-ms UTC)
portfolio_id (string, dict)
trading_symbol (string, dict)
unallocated (float64)
total_value (float64)
total_net_gain (float64)
total_revenue (float64)
total_cost (float64)
cash_flow (float64)
net_size (float64)
pending_value (float64)
```

`trades/`:
```
run_id (string, dict)            — partition key
trade_id (string)
symbol (string, dict)
opened_at (int64, epoch-ms)
closed_at (int64, epoch-ms, nullable)
side (string)
amount (float64)
open_price (float64)
close_price (float64, nullable)
net_gain (float64, nullable)
…
```

`orders/`: analogous.

`metric_series/`:
```
run_id (string, dict)            — partition key
metric_name (string, dict)       — equity_curve, drawdown_series, …
ts (int64, epoch-ms)
value (float64)
```
(Replaces v2's per-run metric blobs with one project-wide table — better dictionary compression.)

### 3.3 Tier 3 chunks

| Chunk type | Content | Lifecycle |
|---|---|---|
| `ohlcv/<sha>` | Parquet bytes for one symbol/timeframe/date-range slice | Long-lived; protocol already specced |
| `code/<sha>` | gzip'd source of strategy module(s) | Long-lived |
| `params/<sha>` | canonical-JSON of params dict | Long-lived |
| `symbols/<sha>` | symbol metadata bundle | Long-lived |
| `schema/<sha>` | strategy class schema (signals, recorded_values shape) | Long-lived |

Dedup scope: **per-project by default, per-tenant opt-in for cross-project reuse.** No cross-tenant dedup (privacy + clarity).

## 4. Read paths

### 4.1 List / rank / filter
```sql
SELECT run_id, sharpe_ratio, sortino_ratio, max_drawdown, total_net_gain
FROM   backtest_runs
WHERE  project_id = ? AND created_at > ?
ORDER  BY sharpe_ratio DESC
LIMIT  20;
```
50 ms regardless of archive size. Today: 30 min (decompress 12,500 bundles).

### 4.2 Single-run deep view
1. Fetch Tier 1 row (~1 KB)
2. Fetch its Parquet partitions for snapshots / trades / orders (partition-pruned)
3. Resolve OHLCV chunks lazily as plot pans/zooms

### 4.3 Cross-run analytics
```python
duckdb.sql("""
    SELECT run_id, ts, value
    FROM   read_parquet('s3://.../metric_series/**')
    WHERE  metric_name = 'equity_curve'
      AND  run_id IN (SELECT run_id FROM sweep_xyz_runs)
""").df()
```
One scan, dictionary-decoded, partition-pruned. Trivially feeds Polars/pandas/plotly.

### 4.4 Download as `.iafbt`
1. Read Tier 1 row
2. Pull partitions from Tier 2
3. Pull referenced chunks from Tier 3
4. Assemble a v2 envelope, zstd-19, write `.iafbt`

Deterministic: same `run_id` → byte-identical export (modulo writer timestamp).

## 5. Write paths

### 5.1 During a backtest run (framework, in-process)
- Snapshots / trades / orders accumulate in Arrow record batches
- On run completion: append batches to the Tier 2 datasets in one transaction (per-project Parquet writer with `run_id` partition column)
- Compute scalar summary → insert Tier 1 row
- Hash & upload reference chunks via the negotiate protocol

### 5.2 Importing an existing `.iafbt`
- Decompose: scalars → Tier 1, snapshot/trade/order/metric series → Tier 2, OHLCV/code/params → Tier 3
- Idempotent on `bundle_id` (re-import is a no-op)

## 6. The `.iafbt` is now an export format

```python
backtest = store.get(run_id)
backtest.export("run_xyz.iafbt")           # deterministic packaging from tiers
imported = Backtest.import_("run_xyz.iafbt")  # re-decomposes into tiers
```

- Still **one file**, still **self-contained**, still **portable**, still **versioned**.
- No longer the storage primitive. Used for: email, archive, offline analysis, OSS-only users, regulator hand-off.

## 7. The OSS-only path stays clean

For users who never touch a server, the same `BacktestStore` interface has a `LocalTieredStore` implementation:

```
~/.iaf/store/
├── index.sqlite               # Tier 1
├── parquet/
│   └── <project_id>/
│       ├── portfolio_snapshots/
│       ├── trades/
│       ├── orders/
│       └── metric_series/
└── chunks/                    # Tier 3
    ├── ohlcv/<sha[0:2]>/<sha>.parquet
    ├── code/<sha[0:2]>/<sha>.gz
    └── …
```

Zero behavioural difference vs today. Single-file `.iafbt` users get `export()` / `import_()`.

## 8. Migration path

| Phase | Change | Risk |
|---|---|---|
| **v8.9 (shipped)** | Bundle format v2; engine_type split; zstd 19; summary_only read | — |
| **v8.10** | `Backtest.scalar_summary()` (no decode of bulk); `iaf index <dir>` builds a SQLite index over a folder of bundles; `BacktestSummary` DTO with stable schema | Low — additive read paths |
| **v8.11** | `BacktestStore` interface with `LocalDirStore` (today) and `LocalTieredStore`. `.iafbt` becomes export format; service constructors accept a store | Medium — touches every backtest service constructor; deprecation flag for one minor cycle |
| **Finterion (closed)** | `RemoteTieredStore` over Postgres + S3 + chunk service | Closed-source, unblocked by v8.11 |

No flag day. v1 and v2 bundles remain readable inputs forever.

## 9. Non-goals

- Per-bundle Parquet for everything (measured neutral-to-negative on real data)
- Custom binary column format (Parquet is solved; leverage it)
- Lossy snapshot/trade compression (user data, hands off)
- Cross-tenant dedup (privacy)
- Schema-on-read JSON anywhere (`(value, ISO-string)` lists are exactly the trap that led to v2)
- A unified "do everything" mega-file (the original `.iafbt` mistake)

## 10. Open questions

- **Chunk boundary strategy** for Tier 3 of opaque blobs: fixed-size vs FastCDC. Default to whole-object (one chunk per logical artifact) until profiling proves otherwise.
- **Tier 2 compaction**: per-run partitions are write-cheap but read-suboptimal at 10⁴+ runs. Periodic compaction job that merges small partitions by sweep — schedule TBD.
- **Tier 1 scalar metric set**: freeze the column set or allow extension? Lean toward a fixed core + a `JSONB extras` column for forward compat.
- **Local SQLite contention** under multi-process backtest sweeps. WAL mode + per-process write batching should be enough for the OSS user; revisit if profiling shows otherwise.

## 11. Headline

> Today's design treats a backtest as a file. The future design treats a backtest as **a row that points to chunks**, with the file as one of several possible views.
>
> That single shift turns the 64 GB problem into the 20 GB problem, makes "list 12,500 backtests sorted by Sharpe" a 50 ms query instead of a 30-minute decode loop, and unlocks DuckDB/Polars analytics over the entire archive without writing any new code.
