# 03 — Cross-sectional Momentum (Pipeline)

**Fit:** ✅ Showcases the `Pipeline` API for cross-sectional ranking.

## Idea

Across a small basket of liquid crypto pairs, rebalance daily into the
top-N names by 30-day return, restricted to the most liquid universe.
This is the canonical cross-sectional momentum recipe used in equities,
adapted to crypto.

## Why this fits the framework

- The framework's `Pipeline` API is purpose-built for this pattern:
  factors per symbol → mask → rank → strategy reads the result.
- The example shows the *clean* version of what
  `examples/cross-sectional-pipelines/cross_sectional_momentum_bot.py`
  already demonstrates — see that file for a fully-commented walkthrough.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```
