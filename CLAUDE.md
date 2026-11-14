# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`investing-algorithm-framework` (IAF) is a Python framework (Poetry, Python >=3.10) for building, backtesting and deploying trading bots. The v9 line is in alpha. An optional Rust/PyO3 extension lives in `native/confluence` and is published separately as `iaf-confluence-native`.

PRs target the `dev` branch upstream (`coding-kitties/investing-algorithm-framework`).

## Commands

```bash
poetry install                       # main + test + dev groups
poetry install --all-extras          # add yahoo/polygon/aws/azure/notebook extras

# Lint: CI runs only flake8, and only on the package (config in .flake8)
flake8 ./investing_algorithm_framework

# Full suite, exactly as CI runs it (slow: CI allows 90 minutes)
poetry run coverage run -m unittest discover -s tests -v

# One module / class / method
poetry run python -m unittest tests.services.test_order_backtest_service
poetry run python -m unittest tests.app.test_eventloop.TestEventloopService.<test_method> -v
```

Tests are `unittest.TestCase` classes and must be run from the repository root, because they import `tests.resources`. `pytest` is not a Poetry dependency; the native CI job installs it with pip and uses it for the parity selection, so both runners work on the suite, but `unittest` is the contract.

### Native extension (optional)

```bash
poetry run python -m pip install ./native/confluence     # needs Rust/Cargo; builds via maturin
cargo fmt    --manifest-path native/confluence/Cargo.toml --check
cargo test   --locked --manifest-path native/confluence/Cargo.toml
cargo clippy --locked --manifest-path native/confluence/Cargo.toml --all-targets -- -D warnings
python -I native/confluence/tests/wheel_smoke.py         # after installing the wheel
```

The Python/Rust parity test selection is listed in the `installed-parity` job of `.github/workflows/native.yml`. Run it after touching anything with a native counterpart.

### Docs site

`docusaurus/` is the public documentation site (deployed by `.github/workflows/deploy-docs.yml`). `docs/` holds the internal architecture and design references and is not published.

## Architecture

Read `docs/architecture/README.md` and `docs/architecture/general.md` first; they index per-subsystem documents (event loop, strategy API, orders and trades, backtest storage format). Some details there lag the code: the web layer is FastAPI, not Flask, and the bundle extension in code is `.obtf` (some docs still say `.iafbt`).

### Layering

`app` → `services` → `infrastructure` → `domain`. Dependencies point inward only.

- `domain/`: models, enums, exceptions, config, and the ABCs users extend (`DataProvider`, `OrderExecutor`, `PortfolioProvider`, `Blotter`). No I/O.
- `services/`: business logic: order, trade, position and portfolio services, trade hooks, metrics, the two `TradeOrderEvaluator` implementations, `backtest_store` and `backtest_index`.
- `infrastructure/`: SQLAlchemy models and repositories, CCXT-backed providers and executors, AWS/Azure services, and the backtest engines under `infrastructure/services/backtesting/`.
- `app/`: `App`, `Context`, `EventLoopService`, `TradingStrategy`, `Task`, `AppHook`, the FastAPI web app, the reporting dashboard and stateless (serverless) entry points.
- `cli/`: the `investing-algorithm-framework` console script (init, deploy to AWS Lambda / Azure Functions, index, store migration, checkpoint validation, MCP server).
- `analysis/`, `notebook/`: read-only helpers for inspecting backtest results.

The public API is whatever `investing_algorithm_framework/__init__.py` re-exports; tests and examples import from the top-level package.

### Wiring

`create_app()` builds an `App` and `dependency_container.py` wires a `dependency-injector` `DeclarativeContainer`. Repositories are `Factory` providers, services and lookups are `ThreadSafeSingleton`s, reachable as `app.container.<name>()`. A new service or repository must be registered there to be injectable.

### Runtime

`EventLoopService` (`app/eventloop.py`) drives each iteration: work out which strategies and tasks are due from their `Schedule`, fetch the union of required data once, reconcile fills (pending-order check live, `BacktestTradeOrderEvaluator` in event backtests), run tasks then strategies then hooks, and snapshot portfolios. `Context` is the facade strategies use to read state and create orders; it delegates to the services.

### Dual backtest engines

A `Backtest` carries independent `vector` and `event` slots:

- **Vector** (`vector_backtest_service.py`): polars-based simulator for parameter sweeps. It bypasses `OrderService` and `TradeService` entirely.
- **Event** (`event_backtest_service.py`): replays history through the real `EventLoopService`, `OrderService` and `TradeService`, so behaviour matches live trading.

Strategies expose `generate_signal_series` for vector mode and `generate_signals` for event mode. A change to order, trade or accounting semantics usually has to be made in both engines; `tests/scenarios/vector_vs_event_backtests` checks they agree.

Results persist as `.obtf` bundles (msgpack + zstd, Parquet blobs, embedded SQLite index) via `services/backtest_store`, with tiered storage and cross-bundle OHLCV dedup.

### Native kernels

Python is always the default; the Rust extension is opt-in per call (for example `card.evaluate_series(frame, backend="rust" | "auto")`). Each kernel has a Python adapter that guards the import: `domain/models/confluence_native.py`, `domain/native_event.py`, `app/native_schedule.py`, `services/metrics/native.py`, `services/trade_order_evaluator/native.py`, `infrastructure/services/backtesting/vector_native.py`.

Results must match the Python implementation exactly. The extension exports semantics version strings (`SEMANTICS_VERSION`, `NETTING_SEMANTICS_VERSION`) that CI asserts; bump them together with the Python side when behaviour changes. `native/confluence/README.md` records what is and is not integrated, and warns against assuming the Rust paths are faster.

## Tests

- Base classes are in `tests/resources/test_base.py`. `TestBase` builds an app with `Environment.TEST`, stub `OrderExecutorTest` / `PortfolioProviderTest`, and class attributes for configuration (`portfolio_configurations`, `market_credentials`, `external_balances`, `initial_orders`).
- Orders stay pending by default in tests. Set `auto_fill_orders = True` on a test class that asserts trade or position state immediately after creating an order.
- Fixture OHLCV data and saved backtest reports are under `tests/resources/` (`test_data`, `data`, `backtest_reports_for_testing`).
- `tests/` mirrors the package layout; `tests/scenarios/` holds end-to-end backtests, including tests that execute the README and `examples/` code, so changing a public example means updating its scenario test.
- `test.py` at the repo root is a manual showcase script, not part of the suite.

## Conventions

- flake8 excludes `app/reporting/`, `services/metrics/`, `infrastructure/database/sql_alchemy.py` and `examples/`.
- Release tags: `v<VERSION>` or `<VERSION>` publishes the framework (version from the root `pyproject.toml`); `native-v<VERSION>` publishes the native package (version must match both `native/confluence/pyproject.toml` and `Cargo.toml`).
- User-visible changes are recorded in `CHANGELOG.md`.
