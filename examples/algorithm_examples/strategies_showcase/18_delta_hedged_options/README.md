# 18 — Delta-hedged Options

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

Delta-hedged options strategies (gamma scalping, vega harvesting,
synthetic-volatility carry) are the canonical use-case for an options
engine *plus* a fast spot-hedging loop. Both are missing today:

1. **No options instruments / chain primitive** — see folder 16.
2. **No Greeks pipeline** — there is no `Greeks` domain object that the
   strategy can read to compute the required spot hedge ratio.
3. **No mixed-instrument portfolio** — the portfolio model holds spot
   positions; mixing an option leg with its spot hedge inside one
   `Portfolio` requires a different P&L attribution model.

## What it would take

Folder 16's prerequisites, plus:

- A `Greeks` domain object emitted by the options pricing pipeline.
- A `MultiInstrumentPortfolio` that can mark-to-market a mixed
  spot+derivatives book.
- A re-hedge scheduler (event-driven, possibly sub-bar) that recomputes
  delta and adjusts the hedge leg.

This is a derivative-engine project of similar scope to folder 16/17.
