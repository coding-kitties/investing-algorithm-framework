# 14 — Implementation Shortfall (Almgren-Chriss)

**Fit:** 🔴 Currently not directly implementable.

## Why it is currently not possible

Implementation Shortfall as a strategy *type* (Almgren-Chriss, Obizhaeva-Wang,
etc.) requires three things the framework does not model today:

1. **Intra-bar fill simulation.** The optimisation trades off market impact
   against price drift over a continuous time horizon. The current backtest
   engine fills orders at the *next bar*, which collapses the impact /
   timing trade-off into a single discrete decision.
2. **An explicit market-impact cost model.** The framework has a
   `SlippageModel` abstraction (`PercentageSlippage`, `VolumeImpactSlippage`,
   etc.) which is a step in this direction, but the AC closed form requires
   a temporary-impact and permanent-impact decomposition that is not
   currently exposed.
3. **A scheduled child-order policy.** AC produces an *optimal trajectory*
   of trade rates; expressing that requires the engine to step at a
   resolution finer than the bar.

## What you can do today

Use folder [13_twap_vwap_execution](../13_twap_vwap_execution) — bar-level
TWAP is the simplest member of the IS family and *is* implementable.

For a true IS implementation, the framework would need:
- a continuous-time (or at least minute-bar) fill model,
- a parent-order abstraction that owns a schedule of child orders,
- a `MarketImpactModel` primitive separate from `SlippageModel`.
