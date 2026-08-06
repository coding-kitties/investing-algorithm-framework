# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [9.0.0a1] — 2026-05-28

### Headline

`v9.0.0a1` makes the framework **dual-engine native**. Every `Backtest`
object now carries an independent `vector` and `event` slot — runs,
summary metrics, and on-disk layout are all engine-scoped. The
`.iafbt` bundle format is bumped to **v3** with a nested envelope and
namespaced metric blobs (`vector_runs/...` / `event_runs/...`).

This release is **backwards compatible at read time**: v1, v2 bundles
and pre-v9.0 directory layouts still open. Writers always emit v3.
See [`docs/migration-v8-to-v9.md`](docs/migration-v8-to-v9.md) for the
upgrade path.

### Added

- **`Backtest` dual-engine API** (`domain/backtesting/backtest.py`)
  - Fields `vector_runs`, `vector_summary`, `event_runs`,
    `event_summary` replace the single `backtest_runs` / `backtest_summary`.
  - `engines()` returns engines with any populated slot (runs OR
    summary), `get_runs(engine)` / `get_summary(engine)` select per
    engine, `get_all_backtest_runs()` returns vector + event concat.
  - `index_rows(bundle_path=...)` yields one `BacktestIndexRow` per
    populated engine; `index_row(...)` is a singular shim.
  - `regenerate_summaries()` rebuilds both engine summaries from
    current run lists in place.
- **Bundle format v3** (`domain/backtesting/bundle.py`)
  - Nested `vector`/`event` slot dicts inside the envelope, each
    holding its own `runs` list and `summary`.
  - Metric blobs are namespaced as
    `<engine>_runs/<i>/metrics/<field>.parquet`.
  - `peek_bundle_format_version(path)` peeks the 8-byte header
    (magic `IAFB` + uint32 LE version) without decoding the body.
- **Merge-on-save** in `save_bundle(..., merge=True)` (default on).
  Engines absent from the in-memory backtest are restored from the
  on-disk envelope so writing one engine never erases the other.
  Atomic write: `<target>.tmp.<pid>` + fsync + `os.replace` + dir
  fsync. Set `merge=False` for legacy overwrite semantics.
- **Engine-scoped ranking & CLI**
  - `analysis.ranking.rank_results(..., engine="vector")` filters
    backtests that lack the requested engine.
  - `iaf list --engine vector|event` and `iaf rank --engine ...`
    Click options.
  - SQLite index schema **v3**: composite primary key
    `(bundle_path, engine_type)`, automatic migration from v2 with
    `COALESCE(engine_type, 'vector')` on NULL rows.
- **HTML report per-engine pages** (`app/reporting/backtest_report.py`)
  - Dual-engine bundles render as two strategy entries with name
    suffix `(vector)` / `(event)`; single-engine reports are
    unchanged.
- **`iaf migrate-bundles --to v3 <dir>` CLI**
  - In-place upgrade of v1/v2 bundles → v3 and legacy directory
    layouts → `.iafbt`. Uses `peek_bundle_format_version` to skip
    bundles already at the target version cheaply. Supports
    `--keep-source`, `--no-index`, `--dry-run`, `--workers`.

### Changed

- `BUNDLE_FORMAT_VERSION = 3`. Writers emit v3 only; passing
  `format_version=1` or `2` to `save_bundle` raises `ValueError`.
- Directory `Backtest.save()` writes per-engine subdirectories
  `vector_runs/` / `event_runs/` and per-engine summary files
  `vector_summary.json` / `event_summary.json`. `Backtest.open()`
  reads both the new layout AND pre-v9.0 `runs/`+`summary.json`
  (legacy data is routed into the vector slot).
- `combine_backtests()` now concatenates per engine (vector with
  vector, event with event).
- `migrate_backtests` directory discovery accepts both legacy
  `runs/` and per-engine `vector_runs/`/`event_runs/` layouts.

### Compatibility shims (legacy callers)

- `Backtest.backtest_runs`, `Backtest.backtest_summary`,
  `Backtest.engine_type` remain as read/write properties that
  delegate to the vector slot.
- `Backtest(..., backtest_runs=..., backtest_summary=...,
  engine_type=...)` keyword arguments are accepted and routed via
  `engine="vector"` default.

### Removed

- v1 / v2 bundle writers. v9.0 bundles are written as v3 only.
- (Internal) `Backtest.scalar_summary()` — use `get_summary(engine)`
  followed by `.to_dict()`.

### Migration

```bash
# Upgrade an entire results directory in place — bundles AND legacy dirs.
iaf migrate-bundles --to v3 ./backtest_results
```

See [`docs/migration-v8-to-v9.md`](docs/migration-v8-to-v9.md) for a
detailed walkthrough.
