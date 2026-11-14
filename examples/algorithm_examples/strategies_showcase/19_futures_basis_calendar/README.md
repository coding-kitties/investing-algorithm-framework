# 19 — Futures Basis / Calendar Spread

**Fit:** 🟡 Pattern is shown on a spot proxy; no native futures-curve model.

## Why this is 🟡

The framework's data and portfolio models are **spot-only**. To run a
real futures basis (cash-and-carry) or calendar-spread strategy you need:

1. **Per-expiry futures contracts** with explicit expiry dates and
   contract-roll handling.
2. A **futures curve** data structure (front month, back month, generic
   continuous contract) so the strategy can read the term structure.
3. **Margin accounting** for short futures legs.

None of those exist yet. The pattern it expresses, however — *take a
long-short position when two related instruments diverge* — is **already
shown on spot** in folder [05_pairs_trading](../05_pairs_trading) as a
long-only relative-value variant.

## What it would take

- A `FuturesContract` domain object (underlying, expiry, multiplier,
  tick size, settlement).
- A `FuturesCurveDataProvider` interface.
- A continuous-contract roll policy (calendar / open-interest based).
- A margin-aware portfolio model.

## What this folder contains

A short README only — the working *pattern* is the long/short z-score
trade in folder 05; the gap is purely the **instrument model**.
