# 07 — Event-driven Signal (Volatility Breakout)

**Fit:** ✅ Clean fit for the bar-driven event loop.

## Idea

A "donchian-style" volatility breakout: at every bar close, if the close
is above the **N-bar rolling high**, enter long. Exit when the close drops
below the **N-bar rolling low**. The signal triggers on a discrete
*event* (the breakout), which is the canonical use-case for the
event-driven `run_strategy` path.

## Why this fits the framework

`run_strategy(context, data)` is called once per bar; placing a single
`create_order` per event is exactly what the engine is built for.

## Parameters

| Name | Default | Notes |
|------|---------|-------|
| `symbol` | `BTC/EUR` | |
| `time_frame` | `1h` | Faster bars produce more events. |
| `breakout_window` | `48` | Two-day rolling high/low on 1h bars. |

## Run

```bash
pip install -r requirements.txt
python backtest.py
```
