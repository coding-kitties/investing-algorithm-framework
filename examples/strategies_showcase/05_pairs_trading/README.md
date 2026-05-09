# 05 — Pairs Trading (z-score on log-spread)

**Fit:** 🟢 Workable, with bookkeeping in user code.

## Idea

Two co-moving symbols (BTC and ETH) typically have a stable log-price ratio.
When the spread `log(BTC) - β·log(ETH)` deviates by more than `z_entry`
standard deviations from its rolling mean, **fade it**:

- Spread *too high* → short the rich leg (BTC), long the cheap leg (ETH).
- Spread *too low* → long BTC, short ETH.
- Exit when `|z| < z_exit`.

## Why this is 🟢 and not ✅

The framework's vector backtester is single-asset signal-driven and does not
have a native concept of a "pair" or a hedge ratio. The example uses the
**event-driven** `run_strategy(context, data)` path and manages both legs
manually — opening/closing matched positions as the z-score crosses
thresholds.

Shorting on a spot venue (Bitvavo) is not realistic. To keep the example
self-contained and runnable, this implementation uses a **long-only
relative-value** variant: it holds the *cheap* asset and exits when the
spread mean-reverts. A proper market-neutral version would require margin
or perp support.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## Disclaimer

A *real* pairs trade requires:
- A statistically validated cointegration (ADF / Johansen).
- A rolling re-estimation of the hedge ratio β.
- Short or perp support for true market neutrality.

This example does **none** of those — it is a structural template only.
