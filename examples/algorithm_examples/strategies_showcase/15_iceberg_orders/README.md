# 15 — Iceberg Orders

**Fit:** 🔴 Currently not possible.

## Why it is currently not possible

An **iceberg order** displays only a small slice of the total quantity on
the book; once that slice fills, the next slice is auto-replenished by the
*venue*. It is a venue-side primitive (e.g. Binance `ICEBERG_QTY`,
NYSE/BATS reserve order types).

The framework's `OrderType` enum exposes `LIMIT`, `MARKET`, `STOP_LIMIT`
etc., but not `ICEBERG`, and the order-execution path does not currently
forward venue-specific iceberg parameters.

## What you can do today

Approximate an iceberg in **user code** by repeatedly placing small limit
orders at the same price after the previous slice fills. This requires:

1. Listening for fill events.
2. Sizing the next slice.
3. Cancelling and reposting at the new mid if the price moves.

This is a non-trivial bookkeeping exercise and is left out of the showcase.
For a venue-native iceberg the framework would need:

- An `OrderType.ICEBERG` value.
- A `display_quantity` field on `Order`.
- Per-venue mappings in each `OrderExecutor` implementation
  (CCXT supports `iceberg_qty` on Binance and a few others).
