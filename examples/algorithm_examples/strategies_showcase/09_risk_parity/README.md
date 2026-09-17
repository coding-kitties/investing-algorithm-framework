# 09 — Risk Parity (inverse-volatility weighting)

**Fit:** ✅ Periodic-rebalance pattern is well-supported.

## Idea

Allocate capital across the basket so that **each asset contributes the
same risk** to the portfolio. The simplest proxy is inverse-volatility
weighting: weight ∝ 1/σ, then renormalise. Rebalance monthly.

## Why this fits the framework

- Portfolio targets are pure functions of the OHLCV history.
- The strategy reads target weights, computes the per-symbol delta vs.
  current positions, and emits the matching orders.
- Rebalance cadence is set with `time_unit=DAY` + a monthly gate.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## Disclaimer

True risk parity uses **marginal risk contributions** under the full
covariance matrix; inverse-volatility is its first-order approximation,
which is what most practitioners actually run.
