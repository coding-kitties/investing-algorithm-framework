# 24 — Order-Book Microstructure

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

Order-book microstructure strategies (queue-position predictors,
order-flow imbalance signals, micro-price models, hidden-liquidity probes)
need the framework to model **L2 (or L3) order books** — none of which is
present today:

1. **No `OrderBook` domain object.** Just `OHLCV` and `Ticker` data types.
2. **No `BookUpdate` event stream.** Microstructure features live in the
   per-update delta, not in OHLCV summaries.
3. **No queue-position model.** Simulating where a child order sits in
   the queue requires per-level FIFO tracking, which the framework's fill
   model does not perform.
4. **No hidden-liquidity inference.** Trade-tape vs. visible-quote
   reconciliation requires a tape feed alongside the book feed.

## What would change this

A new data-type family — `DataType.ORDERBOOK_L2` plus `DataType.TRADES` —
backed by a streaming provider, plus a queue-aware fill simulator. This is
a sizeable design change and is part of the `iaf_realtime` proposal rather
than the research framework.

## Related work today

For a *very coarse* proxy, you can compute "imbalance"-style features from
1-minute OHLCV `(High - Open) - (Open - Low)` style asymmetries, but that
is a pale shadow of true microstructure analysis.
