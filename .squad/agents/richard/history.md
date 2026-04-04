# Richard — History

## Learnings
- Project initialized: investing-algorithm-framework, Python algorithmic trading framework
- User: marcvanduyn
- **Drawdown metrics (2026-03-29):** Fixed 3 bugs in `services/metrics/drawdown.py` and `services/metrics/equity_curve.py`.
  - `get_equity_curve` must sort by `created_at` — all drawdown functions depend on it for peak-tracking.
  - `get_max_daily_drawdown` should use `pct_change()` for worst single-day decline, not peak-to-trough.
  - `get_max_drawdown_duration` must diff actual timestamps (`.days`), not count snapshot entries.
  - Existing tests only cover `get_drawdown_series`, `get_max_drawdown`, `get_max_drawdown_absolute` — the three fixed functions need tests added by Dinesh.
  - Test runner: `python3 -m pytest` (not `python`).
  - Edge case: `get_max_daily_drawdown` must clamp to negative returns only — `min(daily_returns.min(), 0)`. Found by Dinesh during testing.
  - Dinesh wrote 18 tests covering all fixed functions at `tests/services/metrics/test_drawdowns.py`.
