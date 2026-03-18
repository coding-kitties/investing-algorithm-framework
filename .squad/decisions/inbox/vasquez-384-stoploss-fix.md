### 2026-03-18: Fix #384 — None price guard in stop-loss/take-profit evaluation
**By:** Vasquez
**What:** Added `if current_price is None: return False` guard at the top of both `TradeStopLoss.has_triggered()` and `TradeTakeProfit.has_triggered()`. This prevents a `TypeError` when `last_reported_price` is `None` for newly created trades during backtest evaluation.
**Why:** In `BacktestTradeOrderEvaluator.evaluate()`, orders are filled first via `_check_has_executed()`. Newly created trades from those fills haven't received OHLCV price updates yet, so `last_reported_price` is `None`. When `_check_stop_losses()` internally re-queries all open trades (including the new ones), `has_triggered(None)` was called, causing `<=` comparison to fail with `TypeError`.
**Branch:** `squad/384-fix-stoploss-none-price`
