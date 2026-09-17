# 02 — Mean Reversion (Bollinger + RSI)

**Fit:** ✅ Vector backtest, single symbol.

## Idea

Buy when price is **below the lower Bollinger band** *and* RSI is oversold.
Sell when price returns to the **middle band** *or* RSI crosses overbought.
This is the textbook "fade extremes" pattern.

## Why this fits the framework

Same as `01_trend_following` — single asset, bar-aligned signals, no
intra-bar dependency. Vector backtest path runs in a fraction of a second.

## Parameters

| Name | Default | Notes |
|------|---------|-------|
| `symbol` | `BTC/EUR` | |
| `time_frame` | `1d` | |
| `bb_period` | `20` | Bollinger window. |
| `bb_std` | `2.0` | Bollinger band width. |
| `rsi_period` | `14` | |
| `rsi_buy_below` | `30` | Oversold threshold. |
| `rsi_sell_above` | `70` | Overbought threshold. |

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## Disclaimer

Mean-reversion in crypto is regime-dependent — it can lose badly during
strong trends. This example does not include a regime filter.
