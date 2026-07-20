# Multi-Study Bundle — Design Doc (v5 envelope)

**Status:** Draft / proposal.
**Target version:** Bundle format v5 (supersedes v4 before v4 ships externally).
**File extension:** `.iafbt` (unchanged).
**Backwards compatibility:** v2 bundles remain readable; v3 / v4 (internal) get a one-time converter.
**Owner:** TBD.

---

## 1. Motivation

Today, every "study" of an algorithm — in-sample sweep, time-OOS
validation, universe-OOS validation, walk-forward, stress test —
produces its own bundle in its own folder. To answer the question
*"how did algorithm X behave across all studies?"* we have to:

1. Build a Tier-1 index per folder.
2. Join the indexes on `algorithm_id`.
3. Materialise the relevant bundles from each store.

This works, but it pushes a fundamentally per-algorithm question
(*"is this algo robust?"*) onto a per-study storage layout. Two
concrete pains:

- **Cross-study evidence is split across files.** A reviewer looking
  at one bundle sees only one regime.
- **The runner's top-level fields (`study_name`, `universe_key`,
  `vector_summary`, …) are scalar.** They can only describe one
  study, so each study needs its own bundle.

v5 makes the bundle envelope **algorithm-centric**: one
`{algorithm_id}.iafbt` holds *all* studies for that algorithm, each
in its own first-class slot.

This is differentiated from comparable open-source frameworks
(`vectorbt`, `backtrader`, `bt`) — none of them model multi-study
evidence as a first-class on-disk concept.

---

## 2. Goals & non-goals

### Goals

1. **One file per `algorithm_id`.** All evidence about an algorithm
   lives in one place.
2. **Studies are first-class.** Each study slot owns its own runs,
   summary, universe, and window-set.
3. **Coherent summaries.** A study's `summary` aggregates over a
   homogeneous run set (same windows, same universe, same engine).
4. **Lazy load.** Opening a bundle by default returns metadata + study
   summaries only. Runs / equity curves load on demand.
5. **Concurrent-write safe.** Two processes running different studies
   on the same algorithm must not corrupt each other's slots.
6. **Study-aware Tier-1 index.** Rank / prune queries can filter or
   group by study.
7. **Migration path.** v2 bundles convert losslessly; v3 / v4 (internal
   only) get a one-shot converter.

### Non-goals

- **Re-defining engines.** Vector vs. event engine semantics are
  unchanged.
- **Cross-bundle merging.** Joining two algorithms into one bundle is
  out of scope; bundles remain keyed strictly by `algorithm_id`.
- **Multi-machine concurrent writes.** v5 targets single-machine
  parallelism. Cluster writers can layer a coordinator on top.

---

## 3. On-disk schema

### 3.1 Outer envelope (unchanged from v2)

```
+-----------+-----------+--------------------------------+
| 4 bytes   | 4 bytes   |  N bytes                       |
| "IAFB"    | uint32 LE | zstd(level=7, msgpack(doc))    |
+-----------+-----------+--------------------------------+
  magic       version     compressed body
```

`format_version` becomes `5`. Readers MUST reject `version > max_supported`.

### 3.2 Inner document

```python
{
    "format_version": 5,
    "algorithm_id": str,
    "parameters": dict,           # canonical param fingerprint
    "metadata": dict,             # algo-level static metadata
    "created_at": int,            # epoch_ms
    "updated_at": int,            # epoch_ms — last study write
    "studies": {                  # NEW: study_name -> Study
        "in_sample_top": {
            "name": "in_sample_top",
            "description": str,
            "created_at": int,
            "universe": {         # the regime axis for this study
                "key": "in_sample_basket",
                "symbols": [...],
                "trading_symbol": "EUR",
                "market": "BITVAVO",
            },
            "windows": [          # date ranges this study ran on
                {"name": ..., "start": ..., "end": ...},
                ...
            ],
            "engines": {
                "vector": {
                    "runs": <ref:parquet>,    # see §3.3
                    "summary": {...},
                },
                "event": {
                    "runs": <ref:parquet>,
                    "summary": {...},
                },
            },
        },
        "out_sample_time_oos":   {...},
        "out_sample_universe_oos": {...},
    },
}
```

### 3.3 Run storage — sub-files inside the zip

To keep concurrent writes cheap and load lazy, **runs do not live
inline in the msgpack document**. The bundle stays a single `.iafbt`
file on disk (a zip archive) containing a small zstd-msgpack header
plus per-study parquet sub-files. The zip wrapper preserves v2's
"one bundle = one file" portability story:

```
{algorithm_id}.iafbt                 # one zip file on disk
├── header.msgpack.zst               # the document above (without runs)
└── studies/
    ├── in_sample_top/
    │   ├── vector/
    │   │   ├── runs.parquet         # one row per (window, run)
    │   │   └── equity.parquet       # long-form equity curves
    │   └── event/
    │       ├── runs.parquet
    │       └── equity.parquet
    ├── out_sample_time_oos/
    │   └── ...
    └── out_sample_universe_oos/
        └── ...
```

The `<ref:parquet>` placeholder in the header is a relative path
inside the zip. `open_bundle()` returns a `Backtest` whose
`studies[name].engines[engine].runs` is a lazy iterator that opens the
parquet on first access.

This layout means:

- Adding a new study = adding new entries; existing slots are not rewritten.
- Reading one study's summary doesn't require decoding any runs.
- Concurrent writes to different studies write to disjoint paths and
  only contend on the header rewrite.

### 3.4 Header rewrite is the only contention point

The header is rewritten whenever a study slot is added or its
`updated_at` changes. To avoid lost writes, the writer takes a
per-bundle `portalocker` lock around: read header → mutate `studies` →
write header.

Run / equity parquets are written *outside* the lock, named with a
content hash, then atomically referenced from the header on commit.

---

## 4. Domain model changes

### 4.1 `Backtest` (Python)

```python
@dataclass
class Backtest:
    algorithm_id: str
    parameters: dict
    metadata: dict
    studies: dict[str, Study]

    def get_study(self, name: str) -> Study | None: ...
    def list_studies(self) -> list[str]: ...
    def add_study(self, study: Study) -> None: ...

    # convenience accessors — see §4.3 for default-study semantics
    def get_summary(self, engine: str, study: str | None = None) -> Summary: ...
    def get_runs(self, engine: str, study: str | None = None) -> Iterator[Run]: ...
```

### 4.2 `Study`

```python
@dataclass
class Study:
    name: str
    description: str
    created_at: datetime
    universe: Universe
    windows: list[BacktestDateRange]
    engines: dict[str, EngineSlot]   # "vector" | "event"
```

```python
@dataclass
class EngineSlot:
    summary: Summary
    runs: LazyRuns          # parquet-backed iterator
```

### 4.3 Default-study semantics

When code does `bt.get_summary("vector")` with no `study=` argument:

- If the bundle has **exactly one** study → return its summary.
- If the bundle has **zero or many** studies → raise `OperationalException`.

This is the principled "explicit beats implicit" choice. It preserves
single-study ergonomics during the in-sample phase, and forces the
caller to be explicit once OOS lands.

### 4.4 Top-level summary proxies (kept permanently)

`Backtest.vector_summary` / `Backtest.event_summary` are kept as
permanent convenience properties that proxy to `get_summary(engine)`
under the default-study rules:

- If the bundle has **exactly one** study → return its summary.
- If the bundle has **zero or many** studies → raise `OperationalException`
  pointing at `bt.get_summary(engine, study=...)`.

No deprecation, no scheduled removal — these stay part of the public
API. They're the right ergonomic for the common case (one study per
bundle) and force explicit study selection only when ambiguity actually
arises.

---

## 5. Runner integration

The runner API surface stays the same:

```python
app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=windows,
    universes=[some_universe],
    study_name="out_sample_time_oos",
    study_description="...",
    backtest_storage_directory="./results",
)
```

What changes inside:

1. **Storage path resolution.** Per `algorithm_id`, the runner writes
   to `{storage_dir}/{algorithm_id[:2]}/{algorithm_id}.iafbt`. Studies
   for the same algo on the same disk land in the same file.
   (The `[:2]` shard prevents one giant directory.)
2. **Study slot creation.** On first run of a (algo × study), a new
   `Study` slot is created with the universe, window-set, and empty
   engine slots.
3. **Per-window run append.** Each completed window appends a `Run`
   row to `studies/{study}/{engine}/runs.parquet` and rewrites that
   parquet (parquet appends are by-file, not by-row, but per-study
   parquets are small enough that full rewrite per window is fine —
   see §10 for the alternative).
4. **Summary recompute.** After each window, the study's `summary` is
   recomputed from its current run set and the header is updated
   under the lock.
5. **Checkpoints.** Stay on disk in their own scratch dir
   (`{storage_dir}/.checkpoints/{algorithm_id}/{study}/`) and merge
   into the bundle on flush — same model as today.

### 5.1 `study_name` defaults to `"default"`

`study_name` stays optional. When omitted, the runner writes into the
`"default"` slot of the bundle:

```python
app.run_vector_backtests(...)                           # → studies["default"]
app.run_vector_backtests(..., study_name="in_sample")   # → studies["in_sample"]
```

This preserves single-study ergonomics (most users will never name a
study explicitly) while making multi-study workflows opt-in via the
kwarg. No deprecation cycle needed.

---

## 6. Tier-1 index

Schema bumps from `(bundle, engine)` to `(bundle, study, engine)`:

```sql
CREATE TABLE bundle_index (
    algorithm_id     TEXT NOT NULL,
    bundle_path      TEXT NOT NULL,
    study_name       TEXT NOT NULL,
    engine           TEXT NOT NULL,
    universe_key     TEXT,
    -- summary metrics (denormalised for query speed)
    sharpe           REAL,
    cagr             REAL,
    max_drawdown     REAL,
    number_of_windows           INTEGER,
    number_of_windows_with_trades INTEGER,
    number_of_profitable_windows INTEGER,
    number_of_trades_closed     INTEGER,
    -- ...
    updated_at       INTEGER,
    PRIMARY KEY (algorithm_id, study_name, engine)
);
```

`build_index`, `rank_index`, `prune_backtests` all gain a `study=`
filter. Default behaviour (no `study=`) returns rows from the
default-study rule (§4.3) — i.e. errors if the index has multiple
studies for the same algo and the caller didn't pick.

`rank_index(..., engine="vector", study="in_sample_top")` becomes
the canonical analytics call.

---

## 7. Pruning semantics

`prune_backtests` becomes study-aware:

- **`prune_backtests(..., study="in_sample_top")`** — prune the
  in-sample study slots from algos that fail the criterion. *Other
  study slots in those bundles are preserved.*
- **`prune_backtests(..., scope="bundle", study="in_sample_top")`** —
  delete the entire bundle if its in-sample study fails.
- Default: study-scoped, i.e. shrink the study not the bundle.

This matches the typical workflow: prune bad in-sample sweep entries,
keep the OOS evidence on the survivors.

---

## 8. Concurrency model

### 8.1 Single-machine, multiple studies

- Each `run_*_backtests` call writes to one study slot per algo per call.
- Run / equity parquets are written to staged content-addressed paths
  outside the bundle, then atomically referenced.
- The header is rewritten under a per-bundle file lock
  (`portalocker.Lock("{bundle_path}.lock", timeout=30)`).
- Two processes writing to the same algorithm but **different**
  studies serialise only on the header rewrite (~ms).
- Two processes writing to the same algorithm and the **same** study
  is undefined behaviour. We detect it via a `writer_id` field in the
  study slot and raise.

### 8.2 Multi-machine

Out of scope for v5. A future v6 can layer a coordinator (S3 atomic
multipart, or a queue) without changing the on-disk schema.

---

## 9. Migration

v2 bundles convert with a one-shot upgrader:

```python
def migrate_v2_to_v5(path: Path) -> None:
    """In-place migration. Wraps the v2 single-engine document into a
    Backtest envelope with one study named ``"default"`` whose
    universe / windows are derived from the v2 ``metadata``."""
```

v3 and v4 are internal-only; their migrations are similar but read
the (now-removed) top-level `study_name` / `universe_key` fields and
populate the matching study slot.

We keep v2 readers indefinitely (they round-trip through the
migration into a v5 in-memory object).

---

## 10. Open questions

1. **Parquet append vs. full rewrite per window.** Each window
   appends one row. Options: rewrite the whole parquet on each window
   (simple, fine for ≤ ~1k windows × ~50 KB), or use a "fragment per
   window" layout and merge on read. *Provisional answer:* full
   rewrite — simple, and per-study parquets stay small.

2. **Equity curve granularity.** Dual-engine bundles can produce both
   per-window equity and per-bundle aggregated equity. v5 stores both
   under the engine slot; the question is whether to gzip/zstd the
   parquet beyond Parquet's own compression. *Provisional answer:* no
   — Parquet's snappy/zstd column compression is enough.

3. **Lazy-load API surface.** Should `bt.studies["x"].engines["vector"].runs`
   be an iterator (always lazy) or a list (always eager)? *Provisional
   answer:* iterator with a `.collect()` for the eager case.

4. **Header rewrite performance.** With ~5 studies × ~3 engine slots
   per bundle the header is ~10 KB compressed. Even at 10k bundles
   that's manageable, but profiling needed.

5. **Backwards compatibility for existing notebooks.** Notebooks 03 /
   04 / 05 currently use folder-per-study. With v5 they'd use one
   `backtest_results/algorithms/` directory and pass `study_name=` to
   the runner. Deprecation period TBD.

---

## 11. Phased delivery

| Phase | Scope | Definition of done |
|---|---|---|
| **3a** | Domain model. New `Backtest` / `Study` / `EngineSlot` dataclasses. Default-study semantics + permanent `vector_summary` / `event_summary` proxies. Pure in-memory. | Domain tests pass; no on-disk change. |
| **3b** | `bundle.py`. v5 writer + reader (zip + header + parquet sub-files). Per-bundle `portalocker`. v2 → v5 migrator. | Round-trip tests pass; lock contention tests pass. |
| **3c** | Runner write path. `run_*_backtests` write to study slots. `study_name` defaults to `"default"` when omitted. Checkpoint flush merges into study slot. | Phase 2b test suite passes against v5. New multi-study integration tests pass. |
| **3d** | Tier-1 index. Schema bump. `build_index` / `rank_index` / `prune_backtests` gain `study=` parameter. Migration of existing index. | Index tests pass; pruning tests pass. |
| **3e** | Notebooks 03 / 04 / 05. One shared `backtest_results/algorithms/` directory; pass `study_name=` per study; nb05 trivially joins via Tier-1. | Tutorial notebooks run end-to-end. |

---

## 12. Risks

- **Concurrent writers on the same study.** Detected and raised, but
  user-facing — needs clear error message and docs.
- **Parquet schema evolution.** Adding a new metric to `runs.parquet`
  requires either a migration step or schema-on-read. *Mitigation:*
  store metrics as a JSON-serialised `extra` column for
  forward compatibility; promote frequently-used ones to typed columns
  later.
- **Lazy-load surprises.** Code that today does
  `bt.vector_runs[0].equity_curve` will trigger a parquet read. Needs
  doc-level callouts.
- **Storage size.** 200 algos × 5 studies × 18 windows × ~50 KB / run
  ≈ 900 MB. Lazy load handles the working set; absolute disk usage
  becomes a quota concern for users with thousands of algos.

---

## 13. Decision

**Recommendation:** proceed with v5. v4 has not been released
publicly so we have a free hand. The cost (Phase 3a–3f) is real but
the design is genuinely state-of-the-art for the domain.

**Sign-off:** TBD.
