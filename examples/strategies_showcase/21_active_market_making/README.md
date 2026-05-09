# 21 — Active Market Making

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

Active market making — continuously quoting bid and ask, cancelling and
re-posting on every order-book update, managing inventory in microseconds —
has fundamentally different requirements than the framework provides:

1. **Sub-millisecond event loop.** The current scheduler is bar-driven
   (`TimeUnit.MINUTE` is the practical floor). Active MM needs an event
   loop that wakes on every L2 update — typically *thousands per second*.
2. **L2 order-book data model.** There is no `OrderBook` domain object,
   `BookUpdate` event type, or per-level resting-quote state.
3. **Quote-management primitives.** No `replace_order`, no batched
   cancel-and-resubmit, no native rate-limit / weight tracking.
4. **Co-located venue connectivity.** WebSocket round-trips at
   ~30-100 ms are an order of magnitude too slow to compete with venue-side
   liquidity providers.

## Workaround today

Run the **slow market-making** template in folder
[20_slow_market_making](../20_slow_market_making) — bar-level passive
quoting is implementable and still useful for slow-moving books or
maker-rebate harvesting.

## What would change this

A separate, low-latency runtime — see the `iaf_realtime` design proposal —
is the right home for active MM. Trying to bolt sub-ms semantics onto the
bar-driven engine would compromise the rest of the framework's clarity.
