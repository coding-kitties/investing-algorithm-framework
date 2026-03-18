### 2026-03-18: Tests for issue #384 — None price handling in stop-loss/take-profit
**By:** Hudson (Tester)
**What:** Added 6 new test cases across both `test_trade_stop_loss.py` and `test_trade_take_profit.py` covering `has_triggered(None)` for fixed, trailing, and post-high-water-mark scenarios. Tests expect `False` return (not TypeError). These tests validate Vasquez's fix.
**Why:** Issue #384 — `last_reported_price` can be `None` when no market data is available yet, causing TypeError crashes in stop-loss/take-profit evaluation.
