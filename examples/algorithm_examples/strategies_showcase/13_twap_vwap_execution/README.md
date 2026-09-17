# 13 — TWAP / VWAP Execution

**Fit:** 🟡 Bar-level TWAP works; sub-bar VWAP does not.

## Idea

A **parent order** for a fixed quantity is broken into N **child orders**
that are released **uniformly over a window** (TWAP — time-weighted
average price). The framework's bar-driven event loop slices on bar
boundaries; the example uses 10 child orders over 10 daily bars.

A true **VWAP** would weight slices by historical intra-bar volume — that
requires the engine to drop *inside* a bar (or use a fine timeframe), which
is feasible by lowering the `time_unit` to e.g. 1-minute bars.

## Why this is 🟡

- TWAP at the bar level: ✅ trivial, this folder shows it.
- VWAP at intra-bar resolution: 🟡 requires either (a) running on the
  smallest timeframe the venue exposes and treating each minute-bar as a
  slice, or (b) modelling intra-bar volume curves which the framework does
  not provide today.
- Implementation shortfall (Almgren-Chriss): see folder 14 — currently 🔴
  because the framework does not model intra-bar fills with explicit
  market-impact cost.

This example shows the **bar-level TWAP** pattern. Use it as a template;
adapt by reducing the bar size for finer slicing.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```
