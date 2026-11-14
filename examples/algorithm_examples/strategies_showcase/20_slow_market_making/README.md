# 20 — Slow Market Making

**Fit:** 🟢 Workable as a slow, bar-driven quoting strategy.

## Idea

Every bar, **post a single buy limit slightly below mid** and a single
**sell limit slightly above mid**. If the buy fills, you accumulate
inventory; if the sell fills, you offload it. Net P&L = the spread you
captured minus inventory drift.

This is the **slow** version of market-making — it operates on bar
boundaries, *not* sub-second. It is a useful template for showing how the
framework supports passive limit quoting; for true market-making see
folder 21 (which is 🔴 — currently not possible).

## Why this is 🟢 and not ✅

Bar-level posting works, but a real MM strategy requires:

- **Continuous quote management.** Cancelling and reposting on every tick
  is the entire game.
- **Inventory-aware skew.** Quotes should lean to flatten inventory; this
  example does not implement that.
- **A realistic fill model.** The default backtest fill model decides
  whether your limit fills based on whether the next-bar OHLC range
  intersects your price. That is a coarse approximation of real queue
  dynamics; live performance will differ.

Treat this folder as **structural scaffolding** for a passive quoting bot,
not as a production MM engine.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```
