# 23 — High-Frequency Trading (HFT)

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

"HFT" is not a single strategy — it is the *latency regime* in which a
strategy operates (sub-millisecond decision-to-action). The framework
operates in the **second-to-minute** regime. Specifically:

1. **Python overhead.** Even a tight `run_strategy` callback pays
   ~50-200 µs per invocation. HFT budgets are typically <10 µs end-to-end.
2. **Bar-driven scheduling.** The smallest practical bar is 1-minute.
3. **No tick-level data model.** OHLCV bars are the native abstraction;
   there is no `Tick` event and no tick-by-tick playback.
4. **No order-book primitives.** See folder 21 / 24.

## What would change this

HFT requires its own stack — C++/Rust, kernel-bypass NICs, FPGA-accelerated
matching-engine simulators, colocated execution. Trying to add this to the
research framework would compromise both. The right answer is a separate
runtime (see the `iaf_realtime` proposal); this framework remains the
**research and slow-loop deployment** path.
