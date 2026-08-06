# Orders & trades

Two closely-linked concepts documented together:

- An **`Order`** is a single instruction to buy or sell an amount of a target symbol. It moves through a small state machine (`CREATED` → `OPEN` → `CLOSED` / `CANCELED` / `REJECTED`) and records the applied slippage and commission at fill time.
- A **`Trade`** is one buy order plus one or more sell orders on the same symbol, representing a round-tripped position. The trade owns the cost basis, the realised P&L, and any attached stop-loss / take-profit rules.

## Docs in this folder

| Document | What it covers |
|---|---|
| [`orders.md`](orders.md) | Full order lifecycle. Creation, validation, execution, fills, BUY / SELL / SHORT / COVER routing, pending stop-loss / take-profit on unfilled orders, `order_fee` / `order_fee_currency` / `order_fee_rate` / `slippage` attribution triplet, metadata persistence, and the order/trade allocation ledger. |
| [`trades.md`](trades.md) | Full trade lifecycle. When trades are materialised (one per fill event), `is_short` semantics, FIFO close behaviour, partial fills, realised vs. unrealised P&L, and how `StopLossRule` / `TakeProfitRule` records attach to a trade at open time. |

## Related

- [`../strategy/`](../strategy/) — where the signals that become orders originate.
- [`../event_loop.md`](../event_loop.md) — when fills are reconciled and trades materialised inside the runtime loop.
- [`../backtest/open_backtest_format.md`](../backtest/open_backtest_format.md) §Order structure / §Trade structure / §Cost and slippage attribution — the on-disk shape of every field documented here, plus the cost-attribution flow from `ExecutionConfig` → `Order` → `Trade`.
