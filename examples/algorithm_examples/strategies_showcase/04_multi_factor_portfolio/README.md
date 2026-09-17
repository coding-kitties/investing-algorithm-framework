# 04 — Multi-factor Portfolio (Pipeline)

**Fit:** ✅ Pipeline composition with multiple factors blended into one alpha.

## Idea

Combine three orthogonal factors into a single composite score, then hold
the top-N symbols equal-weight:

1. **Momentum** — 30d return.
2. **Low volatility** — inverse of 30d realized vol (favours calmer names).
3. **Liquidity gate** — universe restricted to the most-traded names by
   30d average dollar volume.

The composite alpha is the average of momentum rank and (negated) volatility
rank within the liquid universe.

## Why this fits the framework

The `Factor` algebra in the `Pipeline` API supports `+`, ranking, and
masking out of the box, so the composite is one declarative class.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```
