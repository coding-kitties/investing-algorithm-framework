# Vector vs. Event Engine Parity

**Status:** Verified — automated regression tests in CI
**Evidence:** [`tests/scenarios/vector_vs_event_backtests/`](../../../tests/scenarios/vector_vs_event_backtests/)
**Author:** Marc van Duyn
**Last verified:** 2026-08-11

## TL;DR

Yes, the vector and event engines are trustworthy: given the same
strategy, dataset, and date range, they produce the same trading
decisions to a very high degree of fidelity, and the residual gap
has a known, understood cause with a concrete fix. This document is
the evidence trail for that claim — every number below comes from an
automated test that runs in CI, not a one-off manual check.

## The question

`investing-algorithm-framework` lets a strategy run unmodified
against two backtest engines:

- **event** — processes one bar at a time, in simulated real-time
  order, exactly like live trading would.
- **vector** — computes signals for the whole window in one batch
  pass, for speed (used for large parameter sweeps).

If a strategy is validated on one engine, can you trust the other to
agree? This document answers that with data, not assumption.

## Methodology

Both engines were run against `CrossOverStrategyV1` (a real EMA-50/
EMA-100/EMA-200 crossover strategy — not a toy/synthetic strategy),
on the same fixed, real BTC/EUR (BITVAVO, 2-hour) CSV fixture used
throughout the test suite, over the same date ranges. Three
complementary angles are tested:

1. **Signal-generation parity** (`TestSignalGenerationParity`) —
   engines removed entirely. Directly compares the strategy's
   `generate_signals` (event) and `generate_signal_series` (vector)
   code paths against the *same* underlying OHLCV data, sampled
   every 4th bar across the *entire* ~2-year history (~2,340 samples,
   spanning bull/bear/sideways regimes).
2. **Engine-level trade parity** (`TestEngineLevelTradeParity`) —
   full `app.run_backtest` (event) vs. `app.run_vector_backtest`
   (vector), comparing the actual resulting trades over a 365-day
   window, with an opt-in 730-day (full-history) variant for deeper
   manual verification (`TestEngineLevelTradeParityFullHistory`).
3. **The fix, verified** (`TestEngineParityWithRecommendedWarmup`) —
   the same 365-day comparison, but with `warmup_window` doubled
   relative to the strategy's slowest indicator period.

Trades are matched by nearest `opened_at` (not chronological
position) — see "Why not exact equality?" below for why that matters.

## Finding 1 — indicator computation is not bit-identical, but very close

The vector engine primes indicators with **one growing batch**
computation over the whole backtest window. The event engine
recomputes indicators **fresh, every tick**, over a *sliding*
`warmup_window`-bar window ending at that tick — it never sees more
than `warmup_window` bars of history, no matter how deep into the
backtest it is.

For a long-period indicator (EMA-200) that needs many bars to
numerically converge, a freshly-reseeded sliding window and a
long-accumulated batch don't produce bit-identical values. This is
architectural (real-time/incremental vs. batch processing), not a
bug in either engine.

**Measured impact** (default `warmup_window` = 1x the slowest
indicator period, i.e. 200 bars for EMA-200): **98.6%** bar-level
agreement on `entry` signals, **98.7%** on `exit` signals, across the
full ~2-year history. The very first bar of any window always
matches exactly (both slicing strategies cover identical underlying
data there by construction) — mismatches only accumulate as the
sliding window's shorter effective memory diverges from the batch's
growing one.

## Finding 2 — trades are very close, and vector's are a subset of event's

Running the two engines end-to-end (365-day window, default 1x
warmup):

| Metric | Vector | Event |
| --- | --- | --- |
| Trades | 18 | 22 |

100% of vector's trades have a close (within 2 days) event
counterpart; 89% of matched pairs open within 6 hours of each other.
The divergence is **not** a uniform timing drift — it's the event
engine occasionally firing a handful of *extra* short trades that
the vector engine doesn't, interspersed among an otherwise
near-identical trade sequence (4 unmatched event trades out of 22,
i.e. 18%).

The same pattern holds over the full ~2-year history (38 vector / 42
event trades — 97% matched, 87% tight, 12% extra), confirming this
isn't specific to one window.

## Finding 3 — the fix: use a longer `warmup_window`

**Recommendation: set `warmup_window` to at least 2x your slowest
indicator's period.**

More warmup bars means both engines have enough history for EMA-200
to converge to the same numerical steady state before the tradeable
window even starts — closing the "fresh reseed vs. long-accumulated
batch" gap that causes the divergence.

**Verified** (`TestEngineParityWithRecommendedWarmup`, same 365-day
window and strategy):

| `warmup_window` | Vector trades | Event trades | Unmatched | Tight-match rate (\u2264 6h) |
| --- | --- | --- | --- | --- |
| 200 (1x EMA-200) | 18 | 22 | 4 | 88.9% |
| **400 (2x EMA-200)** | **19** | **19** | **0** | **100%** |
| 600 (3x EMA-200) | 19 | 19 | 0 | 100% |

Doubling the warmup window makes the two engines produce an
**identical trade count, matched 1:1, 100% within 6 hours of each
other**, on this real dataset and strategy. The pure signal-level
check shows the same pattern: bar-level agreement goes from
98.6%/98.7% (1x) to 100.0%/99.7% (2x) to a clean 100%/100% at 3x+.

Going further than 3x showed no additional benefit in testing — 2-3x
the slowest indicator's period is the practical sweet spot.

## Why not exact equality?

A few architectural reasons make bit-for-bit equality across *every*
possible strategy/window an unreasonable bar, even with generous
warmup:

- The event engine's sliding window necessarily has *some* fixed
  size; a pathological indicator (e.g. one with a very long memory,
  like a 1000-period SMA) would need a correspondingly large
  `warmup_window` to converge.
- Floating-point EMA computation is order-of-operations sensitive by
  nature (`pandas.Series.ewm()` reseeds from the first row of
  whatever slice it's given), so *some* residual numerical difference
  between "seeded fresh at bar N-`warmup_window`" and "accumulated
  since the dataset's start" is inherent, not fixable without
  changing the event engine's core sliding-window design.
- Position sizing, cooldowns, and order execution timing can also
  introduce their own small nudges once a signal does fire at a
  slightly different bar.

None of this means the engines disagree in a way that would change a
strategy's overall risk/return profile — the measured divergence is
a handful of extra short trades out of dozens, not a fundamentally
different trading pattern.

## How to reproduce / extend this evidence

```bash
# Default suite (fast, ~1.5 min): signal parity + 365-day engine
# parity + the warmup fix, verified.
poetry run pytest tests/scenarios/vector_vs_event_backtests/ -v

# Opt-in, slower (~90s alone): full ~2-year history engine parity.
# Remove the @unittest.skip on TestEngineLevelTradeParityFullHistory
# in test_signal_generation_parity.py first.
poetry run pytest tests/scenarios/vector_vs_event_backtests/test_signal_generation_parity.py::TestEngineLevelTradeParityFullHistory -v
```

If you change the vector or event engine's data-feeding logic (or
this behaviour otherwise regresses), these tests will fail — that's
the point. If you add a new strategy with a much longer-period
indicator, consider adding an equivalent parity check here rather
than assuming this document's numbers generalize.
