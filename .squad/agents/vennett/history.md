# Vennett — Project History

## Project Context

- **Project:** investing-algorithm-framework — a Python framework for creating trading bots
- **Stack:** Python 3.10+, Flask, SQLAlchemy, ccxt, polars, schedule
- **User:** Marc van Duyn
- **Key concepts:** TradingStrategy, App, Algorithm, TimeFrame, TimeInterval, Order, Portfolio, Position, Backtest
- **Test framework:** unittest (pytest as runner only)

## Learnings

### 2026-03-19: Scheduling interval vs OHLCV timeframe validation tests (#396)
- Created `tests/app/test_strategy_interval_validation.py` — 7 test cases covering the new `__init__` guard
- Minimal concrete subclass pattern: override `run_strategy` with a no-op (see `_ConcreteStrategy`)
- Validation is in `investing_algorithm_framework/app/strategy.py` lines ~162-185
- Guard uses strict `<`: equal intervals pass, only faster-than-data intervals raise
- `DataSource` is a frozen dataclass — pass all fields to constructor, no setattr
- `TimeFrame.amount_of_minutes` and `TimeUnit.amount_of_minutes` are properties, not methods
- Existing test at `tests/app/test_strategy.py` uses `StrategyForTesting` with class-level attrs — good reference pattern

### 2026-03-19: Portfolio net_gain accumulation bug tests (#397)
- Created `tests/services/test_trade_service_net_gain.py` — 3 test cases covering two net_gain bugs
- Bug #1 (cost accumulation): `create_order_metadata_with_trade_context` portfolio loop used accumulated `cost` in net_gain subtraction. Only manifests with 2+ trades per sell order.
- Bug #2 (wrong amount): `_create_trade_metadata_with_sell_order_and_trades` used `sell_amount` instead of `trade_data["amount"]` for per-trade net_gain.
- Test pattern: `_create_filled_buy_order` helper → fill via order_service.update → create sell via order_service.create → assert trade.net_gain + portfolio.total_net_gain
- Explicit `trades` param in sell order data triggers the `_create_trade_metadata_with_sell_order_and_trades` path (bug #2)
- Without explicit `trades`, the queue-based `_create_trade_metadata_with_sell_order` path runs (bug #1 still applies in portfolio loop)
- `storage_repo_type = "pandas"` required for all service tests
- `external_balances` must cover total buy cost or order creation fails validation
- Portfolio re-read via `portfolio_repository.get(id)` needed to see updated total_net_gain

### 2026-03-20: Uncommented eventloop tests (test_eventloop.py)
- Uncommented `test_initialize` and `test_get_data_sources_for_iteration` — both pass
- Found and fixed bug in `app.py:add_strategy()`: used `worker_id` (non-existent attribute) instead of `strategy_id` for duplicate check. Also fixed incorrect nested loop logic.
- `BacktestTradeOrderEvaluator.__init__` now requires `trade_stop_loss_service` and `trade_take_profit_service` — updated test constructor call
- 5 backtest tests remain commented: they depend on `CCXTOHLCVDataProvider.prepare_backtest_data()` which downloads live OHLCV data from Bitvavo exchange — can't run in CI
- `window_size` in DataSource is deprecated but still works (converted to `warmup_window` in `__post_init__`)
- `time_frame` as string (e.g., "2h") still works — converted via `TimeFrame.from_string()`
- `EventLoopService.__init__` takes: context, order_service, trade_service, portfolio_service, configuration_service, data_provider_service, portfolio_snapshot_service
- `initialize()` takes: algorithm, trade_order_evaluator. Sets `next_run_times` from `INDEX_DATETIME` config value
- `initialize_config()` sets `INDEX_DATETIME` to `datetime.now(utc)` if not already set
