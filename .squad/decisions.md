# Decisions

_Append-only ledger of team decisions._

### 2026-03-29T00:00:00Z: Fix drawdown metric bugs (#407)
**By:** Richard (Backend Dev)
**What:** Three bugs fixed in drawdown metrics:
1. `get_equity_curve` now sorts snapshots by `created_at` — all downstream metrics depend on chronological order.
2. `get_max_daily_drawdown` rewritten to compute worst single-day percentage decline (via `pct_change`) instead of peak-to-trough on daily data. This makes it distinct from `get_max_drawdown`.
3. `get_max_drawdown_duration` now computes elapsed calendar days between timestamps instead of counting snapshot entries.
**Why:** Metrics were inconsistent with portfolio snapshot data. `max_daily_drawdown == max_drawdown` was a symptom of both doing peak-to-trough. Duration was wrong for non-daily snapshot frequencies.

### 2026-03-29T00:00:00Z: Drawdown edge case — positive-only returns
**By:** Dinesh (Tester), fixed by Coordinator
**What:** `get_max_daily_drawdown` must clamp to negative returns only (`min(daily_returns.min(), 0)`). When all daily returns are positive, the function was returning the smallest positive return as a "drawdown."
**Why:** Bug found during test coverage work for issue #407.
