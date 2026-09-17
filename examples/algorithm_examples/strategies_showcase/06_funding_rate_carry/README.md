# 06 — Funding Rate Carry

**Fit:** 🟡 Pattern is clean, but the framework has no native perp/funding-rate data provider today.

## Idea

Perpetual futures pay (or receive) a **funding rate** every 8 hours to keep
their price tethered to spot. A persistent funding sign means one side of
the trade is structurally paid to provide liquidity. The classic carry trade:

- **Funding > 0** (longs pay shorts) → short the perp, long the spot, harvest funding.
- **Funding < 0** (shorts pay longs) → long the perp, short the spot.

The position is delta-neutral; the alpha is the funding payment minus
financing and slippage.

## Why this is 🟡

The framework today ships with **spot OHLCV providers** (`CCXTOHLCVDataProvider`,
`PandasOHLCVDataProvider`, etc.) and a spot-style portfolio model. To run
a real funding-rate carry strategy you'd need:

1. A **funding-rate data provider** (e.g. a `CCXTFundingRateDataProvider`
   pulling `fetchFundingRateHistory` from CCXT).
2. A **perpetual futures portfolio** model that can hold a delta-neutral
   spot/perp pair and accrue funding cash flows.
3. **Margin accounting** so the perp leg is properly collateralised.

None of those exist as first-class primitives yet — they live in the
"derivatives expansion" backlog.

## What this folder contains

A **scaffold** showing how a custom `DataProvider` would deliver funding
rates into a `TradingStrategy`. The accompanying `backtest.py` is a
no-op (it raises `NotImplementedError`) so that running it makes the
limitation explicit.

If you want to prototype this pattern today, your best bet is to:

1. Subclass `DataProvider` and load funding-rate history from a CSV.
2. Use the spot portfolio as a proxy for the *cash leg only*, and book the
   funding cash flow manually via `context.create_order` against a synthetic
   "FUNDING" symbol.

## Run

```bash
python backtest.py    # raises NotImplementedError with an explanation.
```
