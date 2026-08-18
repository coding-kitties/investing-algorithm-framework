# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [9.0.0a3] — 2026-08-18

### Added

- **Web API: algorithm control and insights** (`app/web/controllers/algorithm.py`)
  - `GET /api/algorithm/status` — run status plus the persisted enabled/disabled
    control state.
  - `POST /api/algorithm/start` / `POST /api/algorithm/stop` (`?wait=true`,
    `?reason=...`) — start/stop the live event loop. The enabled/disabled flag
    is persisted to the resource directory (and pushed immediately via a
    configured `StateHandler`), so stateless deployments (AWS Lambda, Azure
    Functions) honor it on their next scheduled invocation too. New
    `App.start_algorithm()` / `App.stop_algorithm()` / `App.is_algorithm_enabled()`
    / `App.get_algorithm_control_state()` expose the same control directly to
    serverless handler code, without needing Flask at all.
  - `GET /api/algorithm/insights` — equity curve, drawdown series, max drawdown,
    win rate, Sharpe ratio, trade/portfolio counts, computed from live data.
- **Web API: `GET /api/trades` / `GET /api/trades/count`** — trades previously
  had no REST endpoint at all, unlike orders/positions/portfolios.
- Wired the new algorithm start/stop/status controls into the AWS Lambda and
  Azure Function project scaffolds (`iaf init --type aws_lambda|azure_function`).

### Fixed

- **Real bug in `EventLoopService.start()`** (`app/eventloop.py`): the live/
  unbounded loop (no `schedule`, no `number_of_iterations`) ran exactly one
  iteration and returned instead of looping indefinitely as documented. Fixed
  by wrapping it in a `while` loop gated on a new stop flag
  (`request_stop()`/`reset_stop()`), which is also what makes the new
  start/stop API actually work.

### Changed — reduced default install footprint

- Removed `plotly` as a core dependency; all backtest-report charts now render
  via `finterion-charts` (lighter, no bundled JS payload) instead.
- Removed `jupyter` from core dependencies (never imported at runtime; moved to
  the `dev` dependency group).
- Removed the unused `Flask-Migrate` dependency (and its transitive `alembic`/
  `Flask-SQLAlchemy`/`Mako`).
- `boto3` and the Azure SDK packages (`azure-storage-blob`, `azure-identity`,
  `azure-mgmt-*`) are now optional extras (`pip install
  investing-algorithm-framework[aws]` / `[azure]`) instead of hard
  dependencies — they were previously imported eagerly at package-import time
  even for users who never touch cloud state storage.

## [9.0.0a2] — 2026-08-10

### Fixed

- **`BacktestReport` multi-study bundles** (`app/reporting/backtest_report.py`)
  - `BacktestReport`/`BacktestReport.open` accept a new `study=` argument
    (a study name or `Study` instance) to scope a report to a single study
    on a multi-study bundle. Previously, opening a report over a bundle
    with more than one study always raised `OperationalException:
    Backtest has N studies — pass study= to disambiguate`, with no way to
    pass a `study=` through `BacktestReport` itself.
  - Without an explicit `study=`, every study on a bundle is now rendered
    as its own strategy entry (labelled with the study name) instead of
    raising.
  - Progressively-pruned strategies (via a `window_filter_function`) are
    now labelled "Pruned after `<window>`" in the Window Coverage panel,
    using the `filtered_out` / `filtered_out_at_date_range` metadata the
    backtest service already persists on the bundle.
- **Yearly returns in the HTML report** (#597)
  - Fixed a scale mismatch where `_build_run_data()`'s yearly-returns
    series embedded raw decimal ratios (e.g. `0.358`) while the chart
    renders values as already-scaled percentages, showing `+0.4%`
    instead of `+35.8%`.
  - Fixed `get_yearly_returns()` (`services/metrics/returns.py`)
    silently dropping a backtest's first calendar year: `shift(1)` has
    no prior year-end for the first row, so it was `NaN` and removed by
    `dropna()`. The first year's return is now anchored to the initial
    portfolio snapshot when more than one snapshot exists in that year.

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
