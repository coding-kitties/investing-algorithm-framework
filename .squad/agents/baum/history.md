# Baum — Project History

## Project Context

- **Project:** investing-algorithm-framework — a Python framework for creating trading bots
- **Stack:** Python 3.10+, Flask, SQLAlchemy, ccxt, polars, schedule
- **User:** Marc van Duyn
- **Key concepts:** TradingStrategy, App, Algorithm, TimeFrame, TimeInterval, Order, Portfolio, Position, Backtest
- **Test framework:** unittest (pytest as runner only)

## Learnings

- **Scheduling interval validation (#396):** Added validation in `TradingStrategy.__init__` (strategy.py) that raises `OperationalException` when the scheduling interval (time_unit * interval) is faster than the smallest OHLCV data source timeframe. Placed after interval-is-None check, before stop_losses init. Added `DataType` to the import line.
- **Key file:** `investing_algorithm_framework/app/strategy.py` — main strategy class with all init validation
- **Pattern:** Domain enums (`TimeUnit`, `TimeFrame`, `DataType`) all have `.equals()` for comparison and `.amount_of_minutes` properties for time math
- **Pattern:** `DataSource` is a frozen dataclass; `.time_frame` is `TimeFrame | None`, `.data_type` is `DataType | None`
- **Portfolio NAV bug (#397):** Two bugs in `trade_service.py`. (1) In `create_order_metadata_with_trade_context` (~line 434), the `net_gain` loop used accumulated `cost` instead of per-iteration `trade_cost`, causing repeated subtraction of earlier trades' costs. Fixed by introducing `trade_cost` local var. (2) In `_create_trade_metadata_with_sell_order_and_trades` (~line 322), per-trade `net_gain` used `sell_amount` (total order) instead of `trade_data["amount"]` (per-trade portion), inflating individual trade net_gain when a sell order closes multiple trades.
- **Pattern:** The correct cost/net_gain pattern for trade loops is already in `update_trade_with_removed_sell_order` — always use per-iteration cost, never accumulated cost, when computing net_gain.
- **CSVTickerDataProvider (#331):** Created `CSVTickerDataProvider` in `investing_algorithm_framework/infrastructure/data_providers/csv.py`. Follows CSV OHLCV provider pattern for loading data (polars, same columns), but returns ticker dicts instead of DataFrames. Ticker keys match CCXTTickerDataProvider format: symbol, market, datetime, high, low, bid, ask, open, close, last, volume. bid/ask/last are all mapped to Close since CSV has no order-book data. Backtest data indexed by datetime in a dict for O(1) lookup. Exported from all three __init__.py levels.
- **Pattern:** CSV-based providers in this framework: `_load_data` reads with polars + schema_overrides for Datetime, casts to UTC ms. `has_data` matches by DataType + symbol + market. `copy()` returns a new instance from a DataSource.
- **Key file:** `investing_algorithm_framework/infrastructure/data_providers/csv.py` — now contains both CSVOHLCVDataProvider and CSVTickerDataProvider.
- **Documentation rewrite (#334):** Rewrote three docs files: `docusaurus/docs/Getting Started/tasks.md`, `trades.md`, `deployment.md`. All prior content was fabricated (fake params like `name`, `cron`, `interval="daily"`, `trade.side`, `trade.fee`, `trade.created_at`, YAML config files, Docker/VPS generic content). Replaced with real API examples verified against source code.
- **Task API truth:** `Task` class takes `time_unit` (TimeUnit enum: SECOND/MINUTE/HOUR/DAY), `interval` (int), `worker_id` (str). `run(self, context)` receives Context, not algorithm. `app.task()` decorator takes same params. `app.add_task()` accepts instance or class.
- **Trade API truth:** Trade has `opened_at`, `open_price`, `net_gain`, `available_amount`, `filled_amount`, `remaining`, `cost`, `metadata`. NO `side`, `price`, `fee`, `created_at`. Context methods: `get_trade()`, `get_trades()`, `get_open_trades()`, `get_closed_trades()`, `get_pending_trades()`, `count_trades()`, `add_stop_loss()`, `add_take_profit()`, `close_trade()`.
- **Deployment API truth:** CLI commands are `iaf init --type {default|default_web|azure_function|aws_lambda}`, `iaf deploy-aws-lambda`, `iaf deploy-azure-function`. NO YAML config, NO `start_trading()`, NO Docker/VPS generic content. AWS uses boto3 + S3. Azure uses azure SDK + Functions Core Tools.
