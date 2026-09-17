# 22 — Latency Arbitrage

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

Latency arbitrage profits from being **first** to react to a price change
on one venue and trade against a stale quote on another. Edge measured in
**microseconds** is what the strategy *is* — without low-latency
infrastructure there is nothing to capture.

The framework cannot support this strategy because:

1. **Bar-driven scheduler.** Reactions happen at the next bar boundary
   (1-min minimum). Stale quotes vanish in milliseconds.
2. **No multi-venue real-time tape.** There is no abstraction for
   subscribing to N exchanges simultaneously, normalising the streams,
   and acting on cross-venue divergence.
3. **No co-location.** The framework is designed to run on a developer
   machine or modest VPS, not in a cross-connected exchange data centre.

## What would change this

This strategy belongs in a **purpose-built HFT stack** — typically C++ or
Rust on a dedicated colocated machine, with kernel-bypass networking
(DPDK, Solarflare). It is structurally outside the scope of a Python
research framework.
