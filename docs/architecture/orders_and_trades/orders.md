# Order architecture

This document describes how orders, trades, fills, and risk rules
interact in `investing-algorithm-framework` (IAF) v9.0. It is the
companion to the broader [`architecture.md`](architecture.md) and
expands on the order/trade lifecycle that
[`OrderService`](../../investing_algorithm_framework/services/order_service/order_service.py)
and
[`TradeService`](../../investing_algorithm_framework/services/trade_service/trade_service.py)
implement.

If you are migrating from v8, also read
*§9 of the v8→v9 migration guide* —
this document is the design reference; the migration guide is the
upgrade checklist.

---

## 1. Vocabulary

| Concept | What it is | Mutable? |
|---|---|---|
| **Order** | An instruction sent to a venue. Carries `order_side` (BUY/SELL), `order_type` (LIMIT/MARKET/STOP/STOP_LIMIT), `amount`, `price` / `stop_price`, `status`, `filled`, `remaining`, `external_id`. | Yes — updated as fills arrive and as status transitions occur. |
| **Position** | Aggregate holding for `(portfolio, symbol)`. The cash position is the position whose symbol equals the portfolio's `trading_symbol`. | Yes — every order placement / fill / cancel touches it. |
| **Trade** | Inventory unit created at a single BUY fill event. One BUY order may produce many trades (one per fill). A trade tracks `open_price`, `amount`, `available_amount`, accumulated `net_gain`, attached SL/TP rules, and its closure history. | Mutated by fills against it, never re-keyed after creation. |
| **TradeAllocation** | A many-to-many ledger row linking a sell order to a trade for a specific closed amount. Stores per-allocation `buy_fee`, `sell_fee`, `net_gain_contribution`, `amount_pending`. | Append-only at creation; reversed on sell-order cancel/expire/reject. |
| **TradeStopLoss / TradeTakeProfit** | Risk rule attached to a *trade*. Trailing or fixed. Triggered prices/amounts are computed from the trade's open price and current market price. | Trailing rules update their `high_water_mark`; otherwise immutable until triggered. |
| **Pending SL / TP** | A risk rule spec queued on a *BUY order* (not yet on any trade), stored under `order.metadata["pending_stop_losses" / "pending_take_profits"]`. Materialized onto each trade created at fill. | Append-only on the order; cleared implicitly by being copied to trades. |
| **Reservation price** | The price used at order-creation time to reserve cash for a BUY. Snapshotted into `order.metadata["_reservation_price"]` so slippage can be settled later even after `order.price` is overwritten by the executor. | Set once at create, read at fill. |

---

## 2. Lifecycle at a glance

```
   create_limit_order / create_market_order / create_stop_order
                          │
                          ▼
            OrderService.create(data)
                          │
        ┌─────────────────┼─────────────────────────────────────┐
        │                 │                                     │
        ▼                 ▼                                     ▼
   validate_order    execute_order (sync via OrderExecutor)   sync portfolio
                          │
                          ▼
                  order persisted (status from venue)
                          │
                          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  later iterations:                                          │
   │     EventLoop → OrderService.check_pending_orders(portfolio)│
   │                  ↳ portfolio_provider.get_order(...)        │
   │                  ↳ OrderService.update(...)                 │
   └─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              update() detects filled_difference > 0
                          │
              ┌───────────┴────────────┐
              ▼                        ▼
   _sync_with_buy_order_filled   _sync_with_sell_order_filled
              │                        │
              ▼                        ▼
   TradeService.create_trade_at_fill   TradeService.create_trade_allocations
              │                        │
              ▼                        ▼
   pending SL/TP → real SL/TP    sell order closes 1..N trades (FIFO or explicit)
```

---

## 3. Roles

- **`OrderService`** (`services/order_service/order_service.py`)
  - Owns order CRUD, validation, execution dispatch, portfolio /
    position syncing.
  - The single source of fill-detection: every state change goes
    through `update(...)` which computes the
    `filled_difference = new.filled − previous.filled` and routes a
    positive delta to `_sync_with_buy_order_filled` or
    `_sync_with_sell_order_filled`.
  - Hosts `check_pending_orders(portfolio=...)` — the loop that asks
    each portfolio provider for fresh order state and feeds it back
    through `update()`.

- **`TradeService`** (`services/trade_service/trade_service.py`)
  - Owns trade CRUD and the SL/TP repositories.
  - `create_trade_at_fill(buy_order, fill_amount, fill_price, opened_at)`:
    creates a single trade for one BUY fill event. Also materializes
    any pending SL/TP specs from the BUY order onto the new trade.
  - `create_trade_allocations(sell_order, trades, stop_losses, take_profits)`:
    closes inventory against a SELL order. Two paths:
    - **FIFO** (`_create_trade_allocations_fifo`): no explicit
      `trades=` list → match against open trades in priority order.
    - **Explicit** (`_create_trade_allocations_explicit`): caller
      specifies which trades and how much to close. Used by the
      SL/TP triggering path.
  - Both paths funnel through a single allocation primitive
    `_allocate_sell_to_trade(trade_id, sell_order, amount_to_close)`
    that computes fees and `net_gain_contribution` and writes one
    `TradeAllocation` row.

- **`PositionService`**
  - Maintains aggregate `(portfolio, symbol)` amounts. Drives cash
    reservation on BUY create and cash release on BUY fill/cancel.

- **`OrderExecutor`** (abstract, in `domain/`)
  - Submits an order to a venue. Sets the returned order's
    `external_id`, `status`, `filled`, `remaining`, and (when known)
    `price`. Must **not** raise on rejection — it should return an
    order in a terminal status instead.

- **`PortfolioProvider`** (abstract, in `domain/`)
  - Reads order / position / portfolio state from the venue.
    `check_pending_orders` uses it to detect fills.

- **`TradeOrderEvaluator`** (`services/trade_order_evaluator/`)
  - Two implementations:
    - `DefaultTradeOrderEvaluator` — live mode; computes SL/TP
      triggers from market data and calls `OrderService.create(...)`
      to place the resulting SELL orders.
    - `BacktestTradeOrderEvaluator` — event-backtest mode; also
      simulates whether a pending order would have filled against
      the next OHLCV bar.

---

## 4. Order creation (`OrderService.create`)

`OrderService.create(data, execute=True, validate=True, sync=True)`
is the single entry point for placing an order. Strategies normally
reach it via the `Context.create_*_order(...)` helpers, which build
the data dict and forward it.

The method runs in this order:

1. **Build** an in-memory `Order` from `data` (not yet persisted).
2. **Snapshot the reservation price** for BUY orders:
   `order.metadata["_reservation_price"]` ← `order.reservation_price`,
   then `order.metadata_json` is updated so the value survives the
   eventual `order_repository.save`. The reservation chain falls
   back `price → stop_price → estimated_price` so MARKET and STOP
   orders still get a meaningful value.
3. **Validate** (`validate_order`): per-side and per-type checks
   against the portfolio's unallocated cash and the position size.
   STOP / STOP_LIMIT orders reuse MARKET / LIMIT validation with
   `stop_price` as the price reference.
4. **Execute** via `execute_order(order, portfolio)`, which looks up
   the right `OrderExecutor` and copies back `external_id`, `status`,
   `filled`, `remaining`, and `price` (if the venue reported one).
5. **Honour explicit `filled` / `remaining` / `status`** passed in
   `data` if the caller pre-knew the fill result (e.g. tests, or
   synchronous executors that return CLOSED immediately). The
   default `OrderStatus.CREATED` is filtered out — it must never
   override a terminal status produced by the executor.
6. **Persist** the order against its position (create the position
   if it does not exist).
7. **Side-specific sync** with the portfolio:
   - **SELL**: build `TradeAllocation` rows via
     `trade_service.create_trade_allocations(...)`. If `stop_losses`
     or `take_profits` are in `data`, they identify which rules
     created the order so cancel/expire can restore them.
   - **BUY**: reserve cash on the portfolio
     (`_sync_portfolio_with_created_buy_order`). **No trade is
     created here** — that happens at fill time. If the executor
     reported the order already filled, a *synthetic previous order*
     with `filled=0` is constructed and fed into
     `_sync_with_buy_order_filled` so the fill path runs uniformly.

---

## 5. Order updates and fill detection (`OrderService.update`)

`update(object_id, data)` is the only path for any state change
post-creation. It always works on `previous = get(id)` vs.
`new = repository.update(id, data)` so it can compute deltas.

```python
filled_difference = new.filled - previous.filled
if filled_difference > 0:
    if BUY:
        _sync_with_buy_order_filled(previous, new)
    else:
        _sync_with_sell_order_filled(previous, new)

if "status" in data:
    if status in (CANCELED, EXPIRED, REJECTED):
        _sync_with_<side>_order_<terminal>(new)
```

This means:

- **Partial fills** are first-class. Every positive
  `filled_difference` produces its own trade for BUYs, and its own
  set of allocation rows for SELLs.
- **Cancellation / expiry / rejection** never produce a trade; they
  reverse the reservation (BUY) or restore inventory and pending
  rules (SELL).

---

## 6. BUY fill (`_sync_with_buy_order_filled`)

For each positive `filled_difference`:

1. Determine the fill price (`current_order.price`, else the
   reservation chain as a defensive fallback).
2. Read the snapshotted reservation price from
   `current_order.metadata["_reservation_price"]`.
3. Compute:
   ```
   filled_size      = filled_difference * fill_price
   reserved_for_fill = filled_difference * reservation_price
   slippage_delta   = reserved_for_fill - filled_size
   ```
4. Update the target-symbol position
   (`update_positions_with_buy_order_filled`).
5. Book `filled_size` into `portfolio.total_cost` and
   `total_trade_volume`. If `slippage_delta != 0`, refund (or
   charge) it against `portfolio.unallocated` so the difference
   between *reserved* and *actually spent* cash is settled exactly
   once — uniformly for LIMIT, MARKET, STOP, and STOP_LIMIT.
6. Call `trade_service.create_trade_at_fill(...)`. This:
   - Creates one `Trade` row for the fill amount at the fill price.
   - For each spec in `buy_order.pending_stop_losses`, calls
     `trade_service.add_stop_loss(trade, ...)`.
   - For each spec in `buy_order.pending_take_profits`, calls
     `trade_service.add_take_profit(trade, ...)`.

Result: by the time `_sync_with_buy_order_filled` returns, a real
`Trade` with real `TradeStopLoss` / `TradeTakeProfit` rows exists,
the portfolio cash is correct, and downstream evaluators can act on
it.

---

## 7. SELL fill (`_sync_with_sell_order_filled` + allocations)

A SELL order does not own inventory — it consumes it. When a SELL
fills:

1. `_sync_with_sell_order_filled` updates the position and books the
   proceeds against `portfolio.unallocated`.
2. The allocation rows created at SELL **placement** time
   (`create_trade_allocations`) determine which trades the fill is
   credited against. Two creation paths:
   - **FIFO** (`_create_trade_allocations_fifo`): the SELL had no
     explicit `trades` list. Open trades for the symbol are
     consumed in a priority queue ordered by
     `(opened_at, trade_id)`. Each allocation closes as much of a
     trade as fits, and any leftover spills into the next.
   - **Explicit** (`_create_trade_allocations_explicit`): the SELL
     was created with `trades=[{"trade_id": ..., "amount": ...}, ...]`.
     This is the path used by SL/TP triggering — a stop-loss
     against trade *X* must close trade *X*, never some FIFO
     neighbour.
3. Each allocation goes through `_allocate_sell_to_trade`, which
   stores `buy_fee`, `sell_fee`, and `net_gain_contribution` *on
   the allocation row* so cancellation reversal can be exact.

When a SELL is cancelled / expired / rejected,
`update_trade_with_removed_sell_order` reads the stored values from
the allocation rows and restores trade state with no re-derivation.

> **Ordering matters.** `check_pending_orders` sorts the pending
> orders by `(created_at, id)` ascending before feeding them into
> `update(...)`. This guarantees the trades materialized at fill
> time appear in the same order as the BUYs were placed, which is
> what FIFO sell-allocation downstream depends on.

---

## 8. Risk rules: stop-loss / take-profit

Two binding modes, both reachable from the same Context methods:

```python
# (a) Bind before fill — recommended in v9.0
buy = context.create_limit_order(target_symbol="BTC", price=50_000,
                                 amount=0.1, order_side=OrderSide.BUY)
context.add_stop_loss(order=buy, percentage=5)
context.add_take_profit(order=buy, percentage=10, sell_percentage=50)

# (b) Bind after fill (when you already hold an open trade)
trade = context.get_open_trades(target_symbol="BTC")[0]
context.add_stop_loss(trade=trade, percentage=5, trailing=True)
```

Internally:

- Mode **(a)** calls `Order.add_pending_stop_loss(...)` /
  `Order.add_pending_take_profit(...)`, which append a spec dict to
  `order.metadata["pending_stop_losses" | "pending_take_profits"]`.
  The order is then re-saved by the order repository. At fill,
  `create_trade_at_fill` walks these lists and creates real
  `TradeStopLoss` / `TradeTakeProfit` rows on the resulting trade(s).
- Mode **(b)** calls `TradeService.add_stop_loss(trade, ...)` /
  `add_take_profit(trade, ...)` directly.
- Passing both `trade=` and `order=`, or neither, raises
  `OperationalException`.

Triggering happens in `TradeOrderEvaluator`. When a rule fires, the
evaluator builds a SELL order with an *explicit* `trades=` list
pointing at the rule's parent trade, plus the corresponding
`stop_losses=` / `take_profits=` metadata so cancellation can
restore the rule.

---

## 9. Order types

| Type | Validation | What gets reserved | Fill behaviour |
|---|---|---|---|
| `LIMIT` | `amount > 0`, `amount * price ≤ unallocated` (BUY) or `amount ≤ position` (SELL). | `amount * price`. | Fills at the venue's reported price (slippage settled at fill). |
| `MARKET` | Same as LIMIT, but uses `data["price"]` as an **estimate** for the reservation. | `amount * estimated_price`. | Slippage delta is refunded / charged against `portfolio.unallocated` at fill. |
| `STOP` | Requires positive `stop_price`. Composes the shared `_validate_sell_amount` / `_validate_buy_cash` helpers with `stop_price` as the reference. | `amount * stop_price`. | `order.price` stays `None` until the venue reports an execution price. Allocation code uses `stop_price` as a fallback. |
| `STOP_LIMIT` | Requires `stop_price` and `price`. Composes the shared helpers with `price` (limit) as the buy-cash reference; enforces `limit ≥ stop` for BUY and `limit ≤ stop` for SELL. | `amount * price`. | Same as LIMIT once triggered. |

> The v8 behaviour of forcing `order.price = order.stop_price` for
> STOP orders was removed in v9.0. Calling code must not rely on
> `order.price` being populated for STOP orders before fill.

---

## 10. Invariants

These hold across the live engine and the event backtest engine:

1. **A trade exists if and only if a BUY fill happened.** No
   `CREATED`-state placeholder trades.
2. **One BUY fill ⇒ one new trade.** Partial fills produce
   independent trades at the per-fill price.
3. **Reservation chain.** Every BUY records a `_reservation_price`
   in `order.metadata` at create time; this is the *only* number
   used to compute slippage at fill.
4. **Fill detection is centralised.** Only `OrderService.update`
   transitions order state; everything else (executors, providers,
   evaluators) feeds into it.
5. **Sell allocations are explicit on the row.** A
   `TradeAllocation` carries enough state
   (`net_gain_contribution`, `buy_fee`, `sell_fee`,
   `amount_pending`) to undo itself if the sell order is cancelled.
6. **Pending rules are an order property; real rules are a trade
   property.** They never coexist for the same instance — pending
   specs are converted to real rules exactly once, at the
   originating BUY fill.
7. **`OrderStatus.CREATED` is never an explicit terminal.** The
   default-status filter in `OrderService.create` guarantees that a
   synchronously-CLOSED executor result is not clobbered by the
   creation-time default.

---

## 11. Where each piece lives

| Concern | File |
|---|---|
| Order CRUD, validation, fill dispatch | [`services/order_service/order_service.py`](../../investing_algorithm_framework/services/order_service/order_service.py) |
| Pending-order sync against venue | `OrderService.check_pending_orders` (same file) |
| Trade creation at fill + SL/TP materialization | [`services/trade_service/trade_service.py`](../../investing_algorithm_framework/services/trade_service/trade_service.py) — `create_trade_at_fill`, `add_stop_loss`, `add_take_profit` |
| Allocation ledger (FIFO + explicit) | `TradeService._create_trade_allocations_*`, `_allocate_sell_to_trade` |
| Pending SL/TP on orders | [`domain/models/order/order.py`](../../investing_algorithm_framework/domain/models/order/order.py) — `add_pending_stop_loss`, `add_pending_take_profit`, `pending_*` properties, `reservation_price`, `get_size` |
| Trade model | [`domain/models/trade/trade.py`](../../investing_algorithm_framework/domain/models/trade/trade.py) |
| OrderExecutor contract | [`domain/order_executor.py`](../../investing_algorithm_framework/domain/order_executor.py) |
| PortfolioProvider contract | [`domain/portfolio_provider.py`](../../investing_algorithm_framework/domain/portfolio_provider.py) |
| Live evaluator | [`services/trade_order_evaluator/default_trade_order_evaluator.py`](../../investing_algorithm_framework/services/trade_order_evaluator/default_trade_order_evaluator.py) |
| Backtest evaluator | [`services/trade_order_evaluator/backtest_trade_oder_evaluator.py`](../../investing_algorithm_framework/services/trade_order_evaluator/backtest_trade_oder_evaluator.py) |

---

## 12. Reference

- *§9 of the v8→v9 migration guide* — upgrade checklist for the v9 lifecycle.
- GitHub issue [#431](https://github.com/coding-kitties/investing-algorithm-framework/issues/431) — the defer-trade-creation refactor.
- [`architecture.md`](architecture.md) — framework-wide overview.
- [`v9.0-dual-engine-design.md`](v9.0-dual-engine-design.md) — backtest engine model.
