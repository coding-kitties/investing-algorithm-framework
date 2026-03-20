# Squad Decisions

## Active Decisions

### 2026-03-19: Scheduling interval vs data timeframe validation
**By:** Baum (requested by Marc van Duyn)
**What:** Added a validation in `TradingStrategy.__init__` that raises `OperationalException` when the strategy's scheduling interval is faster than its smallest OHLCV data source timeframe. This is a hard error (raise), not a warning, to prevent wasteful runs.
**Why:** Issue #396 — running a strategy more frequently than data updates is always a user error and should fail fast at init time.

### 2026-03-19: Test coverage for interval validation (#396)
**By:** Vennett (Tester)
**What:** Created 7 unittest-style tests covering the new scheduling interval vs OHLCV timeframe validation in `TradingStrategy.__init__`. All pass.
**Why:** Validates the guard added for issue #396 — prevents strategies from running faster than their slowest data source can refresh.

### 2026-03-19: Fix portfolio NAV net_gain accumulator bug (#397)
**By:** Baum (requested by Marc van Duyn)
**What:** Two fixes in `trade_service.py`:
1. `create_order_metadata_with_trade_context`: Changed the portfolio-level `net_gain` loop to use a per-iteration `trade_cost` variable instead of the accumulated `cost`. The accumulated `cost` was being subtracted from each trade's revenue, causing earlier trades' costs to be double/triple-counted.
2. `_create_trade_metadata_with_sell_order_and_trades`: Changed the per-trade `net_gain` calculation from `sell_amount` (total sell order) to `trade_data["amount"]` (per-trade portion), fixing inflated individual trade net_gain when a sell order closes multiple trades.
**Why:** Both bugs caused systematic understatement of `total_net_gain` in portfolio snapshots, ~3x when closing 3 overlapping trades simultaneously.

### 2026-03-19: Test coverage for net_gain accumulation bug (#397)
**By:** Vennett (Tester)
**What:** Created 3 regression tests in `tests/services/test_trade_service_net_gain.py` covering both net_gain calculation bugs fixed in `trade_service.py`.
**Why:** Issue #397 — ensures both cost-accumulation and wrong-amount bugs in portfolio net_gain calculation stay fixed.

### 2026-03-19: CSVTickerDataProvider implementation (#331)
**By:** Baum (requested by Marc van Duyn)
**What:** Created `CSVTickerDataProvider` in `infrastructure/data_providers/csv.py`. The class loads OHLCV CSV data and returns ticker dicts with keys matching `CCXTTickerDataProvider` format. bid/ask/last are derived from Close price since CSV has no order-book data. Backtest data uses a datetime-keyed dict for O(1) lookup.
**Why:** Issue #331 requires tests for both CSVOHLCVDataProvider and CSVTickerDataProvider, but the latter didn't exist yet.

### 2026-03-20: Documentation rewrite for Tasks, Trades, Deployment (#334)
**By:** Baum (requested by Marc van Duyn)
**What:** Rewrote three documentation files (`tasks.md`, `trades.md`, `deployment.md`) in `docusaurus/docs/Getting Started/` to replace fabricated API examples with real, verified code from the actual framework source. Removed all fake parameters. Every code example now uses real class constructors, real method signatures, and real attribute names.
**Why:** Issue #334 — existing docs were misleading users with non-existent APIs.

### 2026-03-20: Eventloop tests uncommented + app.py bug fix
**By:** Vennett (Tester)
**What:** Uncommented 2 of 7 tests in `tests/app/test_eventloop.py`. Fixed a bug in `app.py:add_strategy()` where `worker_id` (non-existent attribute) was used instead of `strategy_id`. Updated `BacktestTradeOrderEvaluator` constructor call to include required `trade_stop_loss_service` and `trade_take_profit_service` params. 5 backtest tests remain commented (require live exchange data).
**Why:** Restoring test coverage for EventLoopService. The `worker_id` bug would have crashed any app that adds 3+ strategies.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
