# Dinesh — History

## Learnings
- Project initialized: investing-algorithm-framework, Python algorithmic trading framework
- User: marcvanduyn
- Test convention: unittest.TestCase, pytest as runner only
- Drawdown metrics live in `investing_algorithm_framework/services/metrics/drawdown.py`
- Tests at `tests/services/metrics/test_drawdowns.py` — 18 tests across 4 test classes
- `get_equity_curve()` does NOT sort snapshots by timestamp — relies on input order
- `get_max_daily_drawdown()` uses pandas resample('1D').last() + pct_change() for daily returns
- `get_max_drawdown_duration()` tracks drawdown via (timestamp - drawdown_start).days
- Edge case bug found: `get_max_daily_drawdown` returns abs(min(daily_returns)) even when all returns are positive — needs clamping to negative returns only. Filed in decisions inbox for Richard.
- Mock snapshots need `created_at` (datetime) and `total_value` (float) attributes
- Positive-only returns edge case was fixed by Coordinator via `min(daily_returns.min(), 0)` clamping — all 18 tests now pass.
- Richard confirmed: `get_equity_curve` sorts by `created_at`, `get_max_daily_drawdown` uses `pct_change()`, `get_max_drawdown_duration` uses `.days` on timestamp diffs.
- Issue #412: Wrote tests for new TimeFrame enum members (TWENTY_MINUTE, SIX_HOUR, EIGHT_HOUR, THREE_DAY) in `tests/domain/models/test_time_frame.py`
- 6 test classes, ~30 tests covering: enum values, amount_of_minutes, from_string (case variants), from_value (string + enum), equals (string + enum + not-equal), ordering (lt/le/gt/ge relative to neighbors)
- TimeFrame.from_string handles case via explicit checks: "H"→"h" for hours, "d"→"D" for days — tests cover both variants
- `tests/domain/models/` already had `__init__.py` — no new init files needed
- Import path: `investing_algorithm_framework.domain.models.time_frame.TimeFrame`
