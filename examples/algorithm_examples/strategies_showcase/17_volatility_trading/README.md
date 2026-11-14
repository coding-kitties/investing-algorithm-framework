# 17 — Volatility Trading (vol surface arbitrage)

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

Volatility trading (long/short variance, dispersion, vol-of-vol, calendar
skew, etc.) requires a full options stack:

- An options chain across strikes and expiries.
- A vol-surface estimator (SVI, SABR, or non-parametric).
- Implied-vol arbitrage signals computed from the surface.
- Variance/volatility swap pricing for variance-replication trades.

The framework currently models neither **options instruments**
(see folder 16) nor an **implied-volatility surface**.

## What it would take

Folder 16's prerequisites, plus:

- A `VolatilitySurface` primitive with strike/expiry coordinates.
- Surface-fitting helpers (SVI / SABR calibration).
- A variance-swap pricing engine (`VarianceSwap` instrument).

Until then, "vol trading" in this framework is limited to **spot
realised-volatility plays** like folder [12_vol_targeting_overlay](../12_vol_targeting_overlay),
which is a vol-aware *exposure* strategy, not a vol-arbitrage strategy.
