# 12 — Volatility Targeting Overlay

**Fit:** ✅ Single-asset gross-exposure scaling.

## Idea

Sit fully invested in BTC, **scaled so the trailing 30-day realized
portfolio vol** matches an annualized target (e.g. 25%). When BTC vol
spikes, position size shrinks; when vol compresses, position size grows.

Target weight on BTC:

$$ w = \min\left(\frac{\sigma_{target}}{\sigma_{realized}},\ w_{max}\right) $$

Capped at `w_max = 1.0` (no leverage on a spot venue).

## Why this fits the framework

The same delta-rebalance pattern as risk parity: compute target weight,
diff vs. current position, place a single corrective order.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```
