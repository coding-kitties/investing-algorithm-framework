# Trade architecture

This document describes the v9.0 `Trade` lifecycle: how trades are
created from order fills, how partial fills and short positions are
represented, how stop-loss / take-profit rules attach, and how trades
close via FIFO or explicit allocation.

Companions:

- [`orders.md`](orders.md) — the order lifecycle that feeds this one.
- [`event_loop.md`](event_loop.md) — when `TradeService` is invoked.
- [§9 of the v8→v9 migration guide](../migration-v8-to-v9.md#9-order-and-trade-lifecycle) — what changed from v8.

---

## 1. Vocabulary

| Term | Meaning |
|---|---|
| **Trade** | A persistent record of one *fill event* on an opening order. v9.0 produces **one Trade per fill**, not per order. |
| **Opening order** | The order whose fill *creates* the trade. A BUY for long trades; a SELL (short) for short trades. |
| **Closing order** | An order that consumes (all or part of) a trade's `available_amount`. SELL for long trades; COVER (BUY) for short trades. |
| **`is_short`** | First-class boolean on `Trade` (#433). Determines the sign of P&L math and which direction SL/TP triggers fire. |
| **`amount`** | The size of the trade at the moment it opened. Immutable after creation. |
| **`available_amount`** | The part of `amount` not yet consumed by closing orders. Drops monotonically; trade closes when it hits zero. |
| **`net_gain`** | Realized P&L accumulated across all closing allocations. Long: `(close − open) * portion`. Short: `(open − close) * portion`. |
| **`open_price`** | The fill price of the opening order's specific fill event. |
| **`cost`** | `amount * open_price`. For shorts this is the entry notional (proceeds). |
| **`TradeAllocation`** | A child row recording how a single closing order consumed a portion of a trade (amount, fees, `net_gain_contribution`). Enables exact reversal on cancellation. |
| **`TradeStopLoss` / `TradeTakeProfit`** | Risk rules attached to a trade. Carry `percentage`, `trailing`, `sell_percentage`, and inherit `is_short` from the trade. |
| **Pending SL/TP** | Risk rules specified at order-creation time on the *order* (`Order.pending_stop_losses` / `pending_take_profits`). Materialized onto the trade when the order fills. |

---

## 2. Lifecycle at a glance

```
                  Long trade                                Short trade
  ─────────────────────────────────────────  ─────────────────────────────────────────

  BUY order placed                            SELL order placed (short)
       │                                           │
       │ OrderService.update() detects fill        │ OrderService.update() detects fill
       ▼                                           ▼
  TradeService.create_trade_at_fill           TradeService.create_short_trade_at_fill
       │  (one Trade per fill event)               │  (Trade with is_short=True)
       │                                           │
       │  materialize pending SL/TP                │  materialize pending SL/TP
       │  from order.metadata                      │  (inherits is_short=True)
       ▼                                           ▼
  Trade(status=OPEN, available_amount=fill)   Trade(status=OPEN, is_short=True, …)

  ... time passes; SL/TP may fire ...         ... time passes; SL/TP may fire ...

  SELL fill arrives                           COVER (BUY) fill arrives
       │                                           │
       │ create_trade_allocations(…)               │ close_short_trade_with_filled_cover_order
       │   FIFO across open BUY trades OR          │   FIFO across open SHORT trades OR
       │   explicit allocation via metadata        │   explicit via _cover_trade_allocations
       ▼                                           ▼
  per trade:                                  per trade:
    available_amount -= portion                 available_amount -= portion
    net_gain += (sell − open) * portion         net_gain += (open − cover) * portion
    if available_amount == 0 → CLOSED           if available_amount == 0 → CLOSED
```

The two flows are deliberately symmetric. The only differences are
the side of the orders involved and the sign of the P&L formula.

---

## 3. Roles

| Class | Responsibility |
|---|---|
| [`TradeService`](../../investing_algorithm_framework/services/trade_service/trade_service.py) | Owns all trade mutations. The only service permitted to create, allocate, or close trades. |
| [`Trade`](../../investing_algorithm_framework/domain/models/trade/trade.py) | Domain entity. Carries `amount`, `available_amount`, `net_gain`, `is_short`, lists of `stop_losses` / `take_profits`. |
| `TradeAllocation` | Audit row tying a closing order to the trade it consumed. Holds `amount`, `buy_fee`, `sell_fee`, `net_gain_contribution`, `amount_pending` for cancellation reversal. |
| `TradeStopLoss` / `TradeTakeProfit` | Risk-rule records. `is_short` propagates from the parent trade so triggers fire in the right direction (see [`orders.md` §8](orders.md#8-stop-loss--take-profit)). |
| [`OrderService`](../../investing_algorithm_framework/services/order_service/order_service.py) | Calls `TradeService.create_trade_at_fill` / `create_trade_allocations` / `close_short_trade_with_filled_cover_order` whenever it observes a positive filled-difference. |
| [`TradeOrderEvaluator`](../../investing_algorithm_framework/services/trade_order_evaluator/) | Calls `get_triggered_stop_loss_orders` / `get_triggered_take_profit_orders` each iteration and submits the returned SELL/COVER orders. |

---

## 4. Creation — one Trade per fill (#431)

Trades are no longer created when an order is *placed*. They are
created when an order *fills*, by the order-update path:

```python
# investing_algorithm_framework/services/order_service/order_service.py
filled_difference = new_filled - prior_filled
if filled_difference > 0:
    if order.order_side == OrderSide.BUY.value:
        trade_service.create_trade_at_fill(
            order, filled_difference, fill_price, opened_at
        )
    elif order.order_side == OrderSide.SELL.value and is_short_open:
        trade_service.create_short_trade_at_fill(
            order, filled_difference, fill_price, opened_at
        )
```

Consequences:

1. **Partial fills produce independent trades.** A single BUY order
   that fills in three chunks creates three `Trade` rows, each with
   its own `open_price`, `opened_at`, and SL/TP set. This makes
   per-fill cost basis exact and lets multi-fill orders survive
   intervening price moves cleanly.
2. **A canceled or never-filled order produces no trade.** No
   placeholder rows exist that have to be cleaned up later.
3. **`Trade.open_price` is the fill price, not the order price.**
   The constructor pulls `open_price` from the order's limit price
   for convenience, but `create_*_at_fill` overwrites it with the
   actual execution price before returning.

### 4.1 Short trade specifics

`create_short_trade_at_fill` differs from the long path only in
that:

- `cost = fill_amount * fill_price` is the *entry notional* (the
  proceeds the broker credits when the short is opened), mirroring
  the vector engine (#433).
- `is_short=True` is passed into `create(...)` so the SQL row stores
  it as a first-class column.
- `amount` is stored as a positive number; the `is_short` flag is
  the sign carrier (the vector engine uses a negative amount; the
  event engine does not).

---

## 5. Stop-loss / take-profit attachment

SL/TP rules can be added two ways:

### 5a. Pending (recommended) — at order-creation time

```python
order = order_service.create({...})
order.add_pending_stop_loss(percentage=2.0, trailing=False, sell_percentage=100)
order.add_pending_take_profit(percentage=5.0)
```

Pending specs live on `Order.metadata_json["pending_stop_losses"]`.
When the order fills, `create_trade_at_fill` (or
`create_short_trade_at_fill`) walks the pending lists and calls
`add_stop_loss` / `add_take_profit` on the freshly created trade.

This is the only path that survives partial fills cleanly — every
new `Trade` gets its own copy of the rule with its own trigger
price anchored to its own `open_price`.

### 5b. Direct — after the trade exists

```python
trade_service.add_stop_loss(trade, percentage=2.0)
trade_service.add_take_profit(trade, percentage=5.0)
```

Both methods accept either a `trade=` or `order=` argument. When
called with `order=`, the method appends to the order's pending
list, keeps `metadata_json` in sync via `json.dumps`, and preserves
`updated_at` with `flag_modified` so the backtest fill detector
(`updated_at >= bar.datetime`) is not falsely tripped.

### 5c. Short-side inversion

`TradeStopLoss` / `TradeTakeProfit` inherit `is_short` from their
parent trade. The trigger arithmetic flips accordingly:

| Direction | Stop-loss fires when | Take-profit fires when |
|---|---|---|
| Long | `last_price ≤ open * (1 − pct/100)` | `last_price ≥ open * (1 + pct/100)` |
| Short | `last_price ≥ open * (1 + pct/100)` | `last_price ≤ open * (1 − pct/100)` |

`get_triggered_stop_loss_orders` / `get_triggered_take_profit_orders`
emit a **SELL** order for long trades and a **COVER** (BUY) order
for short trades. The COVER order is tagged with
`metadata["_cover_trade_allocations"] = [{"trade_id": …, "amount": …}]`
so the close routine targets the exact trade the rule belonged to.

---

## 6. Closing — FIFO and explicit allocation

### 6.1 Long path: `create_trade_allocations`

When a SELL order fills, `OrderService.update` calls
`TradeService.create_trade_allocations(sell_order, filled_difference)`.
The router picks one of two strategies:

| Path | When | What it does |
|---|---|---|
| **Explicit** | `sell_order.metadata["_trade_allocations"]` is set | Honors the caller's `[{"trade_id", "amount"}, …]` list in order, falling back to FIFO if the list does not absorb the full fill. Used by SL/TP-triggered SELLs to target a specific trade. |
| **FIFO** | otherwise | Sorts open BUY trades for the symbol by `opened_at`, allocates oldest-first until the fill is consumed. |

For each consumed trade, a `TradeAllocation` row is written
(amount, allocated `buy_fee` / `sell_fee` shares,
`net_gain_contribution`) so the close is fully reversible if the
sell order is later canceled.

### 6.2 Short path: `close_short_trade_with_filled_cover_order`

The short close uses the same FIFO-with-explicit-override pattern
but skips `TradeAllocation` bookkeeping (phase 2 — explicit
allocation hints arrived in phase 3 via `_cover_trade_allocations`).
P&L is the inverse formula:

```python
net_gain_contribution = (trade.open_price - fill_price) * portion
```

When `available_amount` reaches zero the trade is marked
`CLOSED` with `closed_at = cover_order.updated_at`.

---

## 7. Cancellation reversal

When a SELL is canceled after partial fills,
`update_trade_with_removed_sell_order` walks every `TradeAllocation`
attached to the canceled order and:

- Adds the allocated `amount` back to the parent trade's
  `available_amount`.
- Subtracts the recorded `net_gain_contribution` from the trade's
  `net_gain`.
- Reverses the fee shares.
- Reopens the trade (`status = OPEN`, `closed_at = None`) if it had
  closed because of this allocation.

Because every state change went through a `TradeAllocation` row,
the undo is *exact* — there is no need to recompute from scratch.

---

## 8. Price tracking

`update_trades_with_market_data(market_data)` is called by the
evaluator each iteration. For every open trade it:

- Updates `last_reported_price` and `last_reported_price_datetime`.
- Updates `high_water_mark` (low-water for shorts) so trailing
  stops can recompute their trigger.

This is the *only* code path that writes recurring per-iteration
fields onto trades.

---

## 9. Invariants

1. **A `Trade` exists if and only if a fill happened.** No
   placeholder trades for unfilled or canceled orders.
2. **One fill → one Trade.** Partial fills never share a Trade row.
3. **`amount` is immutable.** Only `available_amount` mutates as
   closes consume it. `available_amount + Σ allocations.amount == amount`.
4. **`is_short` is immutable.** Set once at creation; the close
   path keys off it to pick the correct P&L formula.
5. **Trade IDs are stable.** A trade is never re-keyed, replaced,
   or rewritten in-place — it is only updated via
   `TradeService.update(trade_id, …)`.
6. **`net_gain` accumulates monotonically.** Every close
   allocation adds to it; only `TradeAllocation`-driven reversal
   subtracts.
7. **SL/TP `is_short` matches the parent trade.** A long trade
   never carries a short SL/TP, or vice versa.
8. **Closed trades never re-open** *except* via the cancellation
   reversal path, which is exact and bounded.

---

## 10. Where each piece lives

| Concern | File |
|---|---|
| Trade entity, constructor, `is_short` derivation | [`domain/models/trade/trade.py`](../../investing_algorithm_framework/domain/models/trade/trade.py) |
| Trade service (create / allocate / close / SL/TP) | [`services/trade_service/trade_service.py`](../../investing_algorithm_framework/services/trade_service/trade_service.py) |
| `create_trade_at_fill` (long) | `trade_service.py` line 111 |
| `create_short_trade_at_fill` (short) | `trade_service.py` line 207 |
| `close_short_trade_with_filled_cover_order` | `trade_service.py` line 276 |
| `create_trade_allocations` (FIFO + explicit) | `trade_service.py` line 619 |
| `update_trade_with_removed_sell_order` | `trade_service.py` line 705 |
| `add_stop_loss` / `add_take_profit` | `trade_service.py` lines 951 / 1065 |
| `get_triggered_stop_loss_orders` / `take_profit` | `trade_service.py` lines 1165 / 1270 |
| `Order.add_pending_stop_loss` / pending TP | [`domain/models/order/order.py`](../../investing_algorithm_framework/domain/models/order/order.py) |
| Repositories (Trade, TradeAllocation, SL, TP) | [`infrastructure/repositories/`](../../investing_algorithm_framework/infrastructure/repositories/) |

---

## 11. Reference

- [`orders.md`](orders.md) — order-side lifecycle that drives fills into this service.
- [`event_loop.md`](event_loop.md) — when fills are observed and SL/TP triggers fire.
- [`general.md`](general.md) — overall layering and persistence model.
- [§9 of the v8→v9 migration guide](../migration-v8-to-v9.md#9-order-and-trade-lifecycle) — historical context for the "one trade per fill" change.
- Issues #431 (one-trade-per-fill), #433 (`is_short` first-class), #434 (SHORT / COVER lifecycle).
