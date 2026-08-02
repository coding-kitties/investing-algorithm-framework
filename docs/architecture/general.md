# Framework architecture

This document describes the high-level architecture of
`investing-algorithm-framework` (IAF) as of v9.0. It covers the
package layout, the runtime lifecycle, the layering between domain /
services / infrastructure, and the main extension points exposed to
user code.

For the order / trade lifecycle in detail (creation, fills,
allocations, SL/TP materialization), see
[`order-architecture.md`](order-architecture.md).
For the dual-engine backtest design, see
[`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md).

---

## 1. Layered overview

```
┌─────────────────────────────────────────────────────────────────┐
│  user code: TradingStrategy, Task, DataProvider, OrderExecutor, │
│             PortfolioProvider, Pipeline                          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│  app/                                                            │
│    App        – container, lifecycle, hooks, CLI entry points    │
│    Context    – per-iteration façade over the services           │
│    EventLoop  – schedules + dispatches strategies / tasks        │
│    Algorithm  – user-defined collection of strategies            │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│  services/                                                       │
│    OrderService, TradeService, PortfolioService, PositionService │
│    DataProviderService, TradeOrderEvaluator (default / backtest) │
│    Pipeline engine, backtest_store, backtest_index, metrics      │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│  infrastructure/                                                 │
│    SQLAlchemy repositories + models   (database/, repositories/) │
│    CCXT-backed PortfolioProvider / OrderExecutor / Data provider │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│  domain/                                                         │
│    Pure dataclasses + abstract bases: Order, Trade, Portfolio,   │
│    Position, Schedule, DataSource, OrderExecutor (ABC),          │
│    PortfolioProvider (ABC), DataProvider (ABC), exceptions,      │
│    constants.                                                    │
└─────────────────────────────────────────────────────────────────┘
```

The dependency direction is **inward only**: `infrastructure` and
`services` import from `domain`, never the other way around. The
`app` layer wires the three together via a single
[`dependency_container.py`](../../investing_algorithm_framework/dependency_container.py).

---

## 2. Package map

| Package | Responsibility |
|---|---|
| `domain/` | Plain models (`Order`, `Trade`, `Portfolio`, `Position`, `Schedule`, `DataSource`), enums, exceptions, abstract bases (`OrderExecutor`, `PortfolioProvider`, `DataProvider`), and framework-wide constants. No side effects, no I/O. |
| `services/` | Use-cases that orchestrate repositories and external providers. Stateless w.r.t. user data — all state goes through repositories. Includes `OrderService`, `TradeService`, `PortfolioService`, `PositionService`, `DataProviderService`, the `pipeline` engine, the `backtest_store` / `backtest_index`, and the two `TradeOrderEvaluator` implementations. |
| `infrastructure/` | SQLAlchemy ORM models + repositories (under `database/`, `models/`, `repositories/`), CCXT-backed `PortfolioProvider` / `OrderExecutor` / OHLCV `DataProvider` implementations. This is the only layer that talks to a real exchange or a real DB. |
| `app/` | The application shell: `App`, `Context`, `EventLoopService`, `Algorithm`, `TradingStrategy`, `Task`, `AppHook`, the Flask web app, and the stateless action entry points. |
| `cli/` | Command-line entry points (e.g. `iaf migrate-bundles`, `iaf index`). |
| `analysis/`, `notebook/` | Read-only utilities for inspecting backtest results from scripts and notebooks. |

---

## 3. Runtime lifecycle

### 3.1 Live / paper trading

1. User builds an `App` (via `create_app` or directly) and registers
   `PortfolioConfiguration`s, `MarketCredential`s, `DataProvider`s,
   `OrderExecutor`s, `PortfolioProvider`s, `TradingStrategy`s and
   `Task`s.
2. `App.run()` instantiates the dependency container, creates the
   SQLite schema (or connects to an external DB), and synchronises
   each portfolio against its `PortfolioProvider`.
3. `EventLoopService` takes over. Each iteration:
   - Computes which strategies and tasks are **due** based on their
     `Schedule` (see *§6 of the v8→v9 migration
     guide*).
   - Fetches the union of data sources required by the due strategies
     once via `DataProviderService`.
   - Calls `OrderService.check_pending_orders(...)` (live) or the
     `BacktestTradeOrderEvaluator` (event backtest) so the framework
     reflects external fills before user code runs.
   - Runs due tasks, then due strategies, then `on_strategy_run`
     hooks.
   - Snapshots each portfolio if the configured
     `SnapshotInterval` has elapsed.
4. Sleep until the next earliest due time and loop.

### 3.2 Backtesting

v9.0 is **dual-engine native**. A single `Backtest` carries an
independent `vector` slot and `event` slot — runs, summary metrics,
and on-disk layout are scoped per engine. See
[`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md) for the
full design and the bundle format.

- **Vector engine**: vectorised polars-based simulator. Fast,
  intended for parameter sweeps. Bypasses `OrderService` /
  `TradeService` entirely.
- **Event engine**: drives `EventLoopService` over historical data and
  routes everything through the real `OrderService` / `TradeService` /
  `BacktestTradeOrderEvaluator` so the behaviour matches live
  trading.

Both engines write into the same `Backtest` envelope and produce
`.iafbt` bundles in the format described by
[`bundle-format-v2.md`](open_backtest_format.md) (v3 supersedes the slot
structure).

---

## 4. Extension points

User code interacts with the framework through a small set of
abstract bases and decorators.

| Extension point | Purpose |
|---|---|
| `TradingStrategy` | Subclass with a `schedule = Schedule.every(...)` (or `Schedule.on(...)`) and `run_strategy(context, data)`. May declare `data_sources`, `scheduled_functions`, and a `pipeline`. |
| `Task` | Like a strategy, but for non-trading work. Same `Schedule` contract. |
| `ScheduledFunction` | Extra function on a strategy with its own independent `Schedule`; dispatched alongside `run_strategy`. |
| `Pipeline` | Declarative chain of universe-filter / signal / sizing / execution stages, run by `PipelineEngine`. |
| `DataProvider` (ABC) | Sources OHLCV / ticker / orderbook data. Multiple providers are ranked by `priority` and matched against the `DataSource`s declared by strategies. |
| `OrderExecutor` (ABC) | Submits an `Order` to a venue and returns it with `external_id` and an updated status. Selected per portfolio market via `_order_executor_lookup`. |
| `PortfolioProvider` (ABC) | Reads portfolio / position / order state back from a venue. Used by `check_pending_orders` and by initial portfolio sync. |
| `AppHook` | `on_initialize`, `on_after_initialize`, `on_strategy_run` callbacks attached at app construction time. |
| `Blotter` | Optional indirection between strategies and `OrderService.create` — lets advanced setups intercept and transform orders before they hit the executor. |

---

## 5. Context — the strategy's view of the world

`Context` is the single object passed into every
`run_strategy(context, data)` call. It is a deliberately thin façade
that delegates to the underlying services:

- **Read**: `get_portfolio()`, `get_position(...)`, `get_open_trades(...)`,
  `get_pending_orders(...)`, `get_unfilled_buy_value(...)`.
- **Write**: `create_limit_order(...)`, `create_market_order(...)`,
  `create_stop_order(...)`, `close_trade(...)`, `add_stop_loss(...)`,
  `add_take_profit(...)`.
- **Infrastructure escape hatches**: `data_provider_service`,
  `portfolio_provider_lookup`, the underlying repositories.

The Context is recreated per iteration so it always reflects the
freshest persisted state.

---

## 6. Persistence model

All state lives in a SQLAlchemy-managed relational store (SQLite by
default, configurable via `SQLALCHEMY_DATABASE_URI`).

Core tables:

- `portfolios` — one row per `PortfolioConfiguration`.
- `positions` — one per `(portfolio, symbol)` pair; the trading-symbol
  position acts as the cash position.
- `orders` — placed orders, parented by a position. Carries
  `metadata_json` for framework-private keys (e.g.
  `_reservation_price`, `pending_stop_losses`, `pending_take_profits`).
- `trades` — created at fill time (one per fill event in v9.0). One
  buy order may parent many trades.
- `trade_allocations` — many-to-many ledger between sell orders and
  trades, with per-allocation fee/net-gain breakdown.
- `trade_stop_losses`, `trade_take_profits` — risk rules attached to
  individual trades; pending rules live in `orders.metadata` until
  materialized at fill.
- `portfolio_snapshots` — point-in-time portfolio state used for
  reporting and backtest metrics.
- Backtest store / index (separate SQLite DB under the backtest
  results directory) — see [`tiered-backtest-storage.md`](tiered-backtest-storage.md)
  and [`backtest_storage.md`](backtest_storage.md).

Repositories under `infrastructure/repositories/` wrap each table and
are the *only* way services touch the DB.

---

## 7. Configuration & dependency injection

`dependency_container.py` builds a `dependency_injector` container
that wires services, repositories, lookups, and the configuration
service into one graph. The container is held on `App.container`;
each `Context` is produced by calling `container.context()`.

Configuration is a flat dict accessed through `ConfigurationService`.
Well-known keys are exposed as constants in `domain.constants`
(`RESOURCE_DIRECTORY`, `DATABASE_DIRECTORY_PATH`, `ENVIRONMENT`,
`INDEX_DATETIME`, `BACKTESTING_FLAG`, …). The same config dict is
threaded into providers/executors via their `.config` setter so they
can react to environment-specific values without going through a
singleton.

---

## 8. Where to look in the code

| You want to understand… | Start here |
|---|---|
| App startup & lifecycle | [`investing_algorithm_framework/app/app.py`](../../investing_algorithm_framework/app/app.py) |
| The per-iteration loop | [`investing_algorithm_framework/app/eventloop.py`](../../investing_algorithm_framework/app/eventloop.py) |
| What strategies can call | [`investing_algorithm_framework/app/context.py`](../../investing_algorithm_framework/app/context.py) |
| Order lifecycle | [`investing_algorithm_framework/services/order_service/order_service.py`](../../investing_algorithm_framework/services/order_service/order_service.py) — and [`order-architecture.md`](order-architecture.md) |
| Trade lifecycle | [`investing_algorithm_framework/services/trade_service/trade_service.py`](../../investing_algorithm_framework/services/trade_service/trade_service.py) |
| Backtest evaluator (event engine) | [`investing_algorithm_framework/services/trade_order_evaluator/backtest_trade_oder_evaluator.py`](../../investing_algorithm_framework/services/trade_order_evaluator/backtest_trade_oder_evaluator.py) |
| Live order/portfolio sync | [`investing_algorithm_framework/services/trade_order_evaluator/default_trade_order_evaluator.py`](../../investing_algorithm_framework/services/trade_order_evaluator/default_trade_order_evaluator.py) |
| Scheduling | `domain/models/scheduling/` + *§8 of the migration guide* |
| Backtest storage format | [`bundle-format-v2.md`](open_backtest_format.md), [`backtest_storage.md`](backtest_storage.md), [`tiered-backtest-storage.md`](tiered-backtest-storage.md) |
| Pipeline API | [`pipeline-api.md`](pipeline-api.md) |
