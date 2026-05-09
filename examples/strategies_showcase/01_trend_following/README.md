# 01 — Trend Following (EMA crossover)

**Fit:** ✅ Sweet spot for the framework's vector backtester.

## Idea

Classic single-asset trend follower: a fast EMA crossing above a slow EMA is
a *buy* signal, the inverse cross is a *sell*. No filters, no stops — just
the cleanest possible expression of the pattern so you can see how an
end-to-end vector backtest is wired up.

## Why this fits the framework

- One symbol, bar-aligned, no intra-bar logic — perfect for
  `run_vector_backtest`.
- `generate_buy_signals` / `generate_sell_signals` return boolean `pd.Series`
  per symbol, exactly what the vector engine expects.
- `pyindicators.ema` does the heavy lifting; no custom indicator code.

## Parameters

| Name | Default | Notes |
|------|---------|-------|
| `symbol` | `BTC/EUR` | Any spot pair on Bitvavo. |
| `time_frame` | `1d` | Daily bars keep the example fast. |
| `fast_period` | `20` | Fast EMA. |
| `slow_period` | `50` | Slow EMA. |

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## Disclaimer

The example is a *pattern reference*, not an alpha source. A trend follower
without a regime filter, a stop, or position sizing will lose money in
chop-heavy markets. Use it as the skeleton for your own research.
