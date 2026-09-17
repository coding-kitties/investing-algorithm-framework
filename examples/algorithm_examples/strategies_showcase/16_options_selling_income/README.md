# 16 — Options Selling for Income (Covered Calls / Cash-Secured Puts)

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

The framework's domain model is **spot-instrument-only**. There is no
abstraction for:

- An **options chain** (per-expiry strike grid).
- Per-contract metadata: strike, expiry, contract multiplier, exercise style.
- **Greeks** (delta, gamma, vega, theta).
- **Premium settlement** at expiry / assignment.

Without these, you cannot express even the simplest option position
(e.g. *short 1 BTC-31MAR-50k call*).

## What it would take

A full options expansion would need:

1. An `OptionInstrument` domain object (underlying, strike, expiry, type, multiplier).
2. An `OptionsChainDataProvider` interface (e.g. CCXT for Deribit).
3. A pricing/Greeks pipeline (Black-76 for European, binomial for American).
4. A portfolio model that can hold short option positions with
   margin / collateral accounting.
5. An assignment / expiry settlement engine.

This is a multi-quarter expansion and is currently out of scope.

## Workaround today

If you only need *exposure* like a covered call (long underlying + capped
upside), you can approximate it on spot by **selling above-target prices via
a `take_profit_percentage`** in `StopLossRule` / `TakeProfitRule` — but this
is a payoff approximation, not a real options position.
