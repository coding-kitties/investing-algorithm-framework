# Event loop architecture

This document describes the per-iteration loop that drives both live
trading and the event-driven backtest engine in
`investing-algorithm-framework` (IAF) v9.0. It is the companion to
[`general.md`](general.md) and expands on the contract implemented by
[`EventLoopService`](../../investing_algorithm_framework/app/eventloop.py).

For the order/trade lifecycle invoked from inside an iteration, see
[`orders.md`](orders.md) and [`trades.md`](trades.md).

---

## 1. Mental model

```
                 ┌──────────────────────────────────┐
                 │  EventLoopService.start(...)     │
                 └──────────────────────────────────┘
                          │
   ┌──────────────────────┴──────────────────────┐
   │ live (no schedule arg)                      │ backtest (schedule arg)
   ▼                                             ▼
get_due_strategies(now)                  iterate over precomputed
get_due_scheduled_functions(now)         schedule frame; INDEX_DATETIME
                                         is set to each row's "date"
   │                                             │
   └──────────────────────┬──────────────────────┘
                          │
                          ▼
                  _run_iteration(strategies, scheduled_function_calls)
                          │
        ┌─────────────────┼──────────────────────────────────────────┐
        ▼                 ▼                                          ▼
  cash reconciliation  fetch market data once         trade-order evaluator
  (_tick_broker_balance + (per-iteration data_object,  (live: real venue,
   _auto_sync_markets)   backtest vs live branch)      backtest: simulated
                                                       fills against OHLCV)
                          │
                          ▼
                      run tasks
                          │
                          ▼
                run pipelines + run_strategy
                  + on_strategy_run hooks
                          │
                          ▼
              dispatch ScheduledFunction calls
                          │
                          ▼
                   take snapshot (if due)
                          │
                          ▼
                  update next-run history
```

The loop is **deliberately symmetric** between live and backtest. The
only differences are:

- How `INDEX_DATETIME` is advanced (wall clock vs. schedule frame).
- Which `TradeOrderEvaluator` is wired in
  (`DefaultTradeOrderEvaluator` vs. `BacktestTradeOrderEvaluator`).
- Which data path is used (`get_data` vs. `get_backtest_data`).
- Whether the loop sleeps between iterations.

User code never sees these differences.

---

## 2. The `INDEX_DATETIME` contract

`INDEX_DATETIME` is the framework's notion of "now". It lives in the
`ConfigurationService` and is the single source of truth for time
across the entire iteration:

- Strategies read it via `context.get_current_datetime()`.
- The evaluator stamps it onto fills (`order.updated_at`, `trade.opened_at`).
- Snapshots use it as `created_at`.
- Backtest data lookups use it as `backtest_index_date`.

| Mode | How `INDEX_DATETIME` advances |
|---|---|
| Live (no `schedule`, no `number_of_iterations`) | Reset to `datetime.now(timezone.utc)` after each iteration. The loop sleeps 1s and re-evaluates due strategies. |
| Live (with `number_of_iterations`) | Same as above, bounded loop. |
| Backtest (with `schedule`) | Set to the next entry in the precomputed schedule frame. No wall-clock dependency. |

Any code that calls `datetime.now()` directly bypasses this contract
and will break backtests. Use
`configuration_service.config[INDEX_DATETIME]` instead.

---

## 3. Scheduling — when does a strategy run?

Each strategy declares its cadence as a `Schedule` object (see
*§8 of the v8→v9 migration guide*).
`EventLoopService` keeps a per-strategy `next_run_times` dict and
asks each `Schedule` whether it is due:

```python
def _get_due_strategies(self, current_datetime=None):
    due = []
    for strategy in self.strategies:
        entry = self.next_run_times[strategy.strategy_id]
        last_run = entry.get("last_run")
        if strategy.schedule.is_due(current_datetime, last_run):
            due.append(strategy)
            entry["last_run"] = current_datetime
    return due
```

`Schedule.is_due(now, last_run)` is the *only* method strategy
cadence depends on. Built-in implementations cover `every(n, unit)`,
`on(weekdays, time)`, and cron-like patterns; user code can plug in
custom subclasses.

### 3.1 Scheduled functions

A strategy may declare extra functions with independent schedules
via `scheduled_functions = [ScheduledFunction(func="rebalance",
schedule=Schedule.every(1, TimeUnit.DAY))]`. They are tracked
separately in `_scheduled_function_last_runs` and dispatched in
**Step 5c** of `_run_iteration` after the main `run_strategy` calls.

### 3.2 Backtest schedule

In backtest mode the schedule is precomputed once before the loop
starts: every relevant strategy / scheduled-function fire time
across the date range is materialized into a `dict[datetime,
{"strategy_ids": [...], "scheduled_function_calls": [...]}]`. This
guarantees:

- The simulation is fully deterministic.
- Data prefetching can run once per backtest, not per iteration.
- `tqdm` can show a meaningful progress bar.

---

## 4. The seven steps of `_run_iteration`

The body of [`_run_iteration`](../../investing_algorithm_framework/app/eventloop.py)
is the canonical reference. The ordering is load-bearing — each step
assumes the previous one has run.

### Step 0 — Reconcile broker / cash state

- `_tick_broker_balance(env, now)`: in backtest mode, advances
  simulated `ScheduledDeposit`s whose cadence has elapsed.
- `_auto_sync_markets()`: for any market with `auto_sync=True`,
  calls `Context.sync_portfolio(...)` so deposits / withdrawals are
  absorbed before strategies see the iteration.

### Step 1 — Collect open work + data sources

- Pulls all `OrderStatus.OPEN` orders and `TradeStatus.OPEN` trades
  once (they are reused by Steps 3 and 6).
- Unions the `data_sources` declared by every due strategy and
  deduplicates them via `_get_data_sources_for_iteration`.

### Step 2 — Fetch market data once per iteration

- For each unique `DataSource`, calls the data provider service
  (backtest path uses `get_backtest_data(backtest_index_date=now)`;
  live uses `get_data(date=now)`).
- Result is a single `data_object: dict[identifier, polars.DataFrame]`
  shared across strategies, tasks, and the evaluator.
- The pending-orders / open-trades OHLCV slice is computed
  separately by `_get_pending_orders_and_trades_data_for_iteration`
  so the evaluator can simulate fills against the same bars
  strategies will see.

### Step 3 — Reconcile orders & trades (the evaluator)

`self._trade_order_evaluator.evaluate(open_trades, open_orders,
ohlcv_data)`:

- **Live** (`DefaultTradeOrderEvaluator`): asks each
  `PortfolioProvider` whether known-open orders have filled and
  feeds the result back through `OrderService.update(...)`. Also
  computes SL/TP triggers from the latest market data and places
  the resulting SELL / COVER orders.
- **Backtest** (`BacktestTradeOrderEvaluator`): simulates whether
  each open order would have filled against the next OHLCV bar
  (LIMIT, MARKET, STOP, STOP_LIMIT — see [`orders.md` §9](orders.md#9-order-types))
  and applies fills via the same `OrderService.update(...)` path.

**Step 3 always runs before strategies.** Strategies always observe
the post-reconciliation portfolio state, never the stale pre-fill
view.

### Step 4 — Run tasks

Tasks have the same `Schedule` contract as strategies but are not
expected to place orders. They run before strategies so they can
prepare auxiliary state (e.g. write a metrics row).

### Step 5 — Run pipelines, strategies, and hooks

For each due strategy:

5a. Build the per-strategy `data` dict by projecting `data_object`
    onto the strategy's declared `data_sources`.

5b. `_run_pipelines(strategy, data, data_object, as_of=now)` —
    executes any attached `Pipeline` (universe filter → signal →
    sizing → execution). See [`pipeline-api.md`](pipeline-api.md).

5c. Fire every `on_strategy_run` hook registered on the algorithm.

5d. Call `strategy.run_strategy(context=self.context, data=data)`.
    The default `run_strategy` drives the event-mode path:
    `strategy.generate_signals(context, data)` is invoked, the
    resulting `Signal`s flow through the phase pipeline
    (`Resolve → Size → ApplyBudget → Emit → AttachRisk →
    RecordCooldown`), and concrete orders are placed via
    `context.create_limit_order(...)`. Vector-mode strategies use
    a different entry point — see [`strategy.md`](strategy.md) for
    the contract of `generate_signals` vs.
    `generate_signal_series`.

After all main strategies have run, `scheduled_function_calls`
(collected in Step 1.5) are dispatched. Each entry is either:

- `(strategy_instance, ScheduledFunction)` — the live path, or
- `(strategy_id, func_name)` — the precomputed-schedule path used
  by the backtest engine.

Both paths resolve to a bound method on the strategy and invoke it
with the same `(context, data)` signature.

### Step 6 — Snapshot the portfolios

`_snapshot(now, open_orders, created_orders)` writes a
`PortfolioSnapshot` row if the configured `SnapshotInterval` is due
(`STRATEGY_ITERATION` — every iteration, `DAILY` — at least 24 h
since the last snapshot, `NONE` — never). The snapshot absorbs any
external cash flow drained from the `BrokerBalanceTracker` so the
equity curve stays consistent with on-exchange reality.

### Step 7 — Update next-run bookkeeping

`_update_history(now, strategies, hooks)` records `(timestamp,
strategy_id)` pairs onto the `EventLoopHistory` used by the backtest
report and the live introspection endpoints.

---

## 5. Live vs. backtest dispatch (`start(...)`)

`EventLoopService.start(...)` has three operating modes, each
implemented as a separate branch:

| Mode | Trigger | What it does |
|---|---|---|
| **Backtest** | `schedule` is not None | Iterates the sorted schedule keys, sets `INDEX_DATETIME` to each, calls `_run_iteration(strategies, scheduled_function_calls)`. Optional `tqdm` progress bar. |
| **Live, bounded** | `number_of_iterations` is not None | Loops N times; each pass reads `INDEX_DATETIME`, gets due strategies / SFs, runs one iteration, then resets `INDEX_DATETIME` to wall clock and sleeps 1 s. |
| **Live, indefinite** | neither | Single iteration per call; the outer process is expected to invoke `start()` in a loop (in practice this branch is rarely used — the bounded form is the canonical live entry point). |

All three branches end with `self.cleanup()` which releases pipeline
engines, flushes the snapshot buffer, and clears per-iteration
caches.

---

## 6. Data fetching contract

The two data paths look superficially similar but have different
semantics:

| Method | Returns | Index semantics |
|---|---|---|
| `DataProviderService.get_data(data_source, date, start_date, end_date)` | Live data ending at `date`. The provider may stream from cache or hit the venue. | `date == now`. |
| `DataProviderService.get_backtest_data(data_source, backtest_index_date, start_date, end_date)` | Historical slice up to and including the bar containing `backtest_index_date`. **No lookahead.** | `backtest_index_date == INDEX_DATETIME`. |

Strategies receive the same DataFrame shape in both modes — they
must not assume the provider type or the time-of-day at which they
were called.

---

## 7. Live pipeline envelope (#503)

Live pipelines are restricted by an envelope validated once per
`start(...)` call by `_validate_live_envelope`:

- **Max 50 symbols per pipeline.**
- **Timeframes must be daily or coarser** (≥ 24 h).

The envelope is enforced only outside backtest mode. Any
violation raises `OperationalException` at the first iteration
before any orders are placed. Backtests have no such cap.

---

## 8. Invariants

These hold across both engines:

1. **One reconciliation per iteration.** The evaluator runs in
   Step 3 — strategies always see the post-reconciliation state.
2. **Time is single-sourced.** `INDEX_DATETIME` is the only "now"
   for the framework; wall-clock reads from user code are a bug.
3. **Data is fetched once.** The same `data_object` is shared
   across the evaluator, tasks, pipelines, and strategies in a
   single iteration.
4. **Ordering is fixed.** Reconcile → tasks → pipelines →
   strategies → scheduled functions → snapshot → history. Never
   reordered, never partially executed.
5. **Cadence is opaque.** `_run_iteration` does not care *why* a
   strategy is due — `Schedule.is_due(...)` is the only authority.
6. **Snapshots are idempotent per interval.** Calling `_snapshot`
   when no interval has elapsed is a no-op; the configured
   `LAST_SNAPSHOT_DATETIME` is the guard.

---

## 9. Where each piece lives

| Concern | File |
|---|---|
| Iteration body, step ordering | [`app/eventloop.py`](../../investing_algorithm_framework/app/eventloop.py) — `_run_iteration` |
| Live / backtest dispatch | `app/eventloop.py` — `start` |
| Schedule evaluation | [`domain/models/scheduling/`](../../investing_algorithm_framework/domain/models/) — `Schedule.is_due` |
| Live reconciliation | [`services/trade_order_evaluator/default_trade_order_evaluator.py`](../../investing_algorithm_framework/services/trade_order_evaluator/default_trade_order_evaluator.py) |
| Backtest reconciliation | [`services/trade_order_evaluator/backtest_trade_oder_evaluator.py`](../../investing_algorithm_framework/services/trade_order_evaluator/backtest_trade_oder_evaluator.py) |
| Per-iteration data fetch | `app/eventloop.py` — `_get_data_sources_for_iteration`, `_get_pending_orders_and_trades_data_for_iteration` |
| Snapshots | `app/eventloop.py` — `_snapshot`, `_drain_cash_flow_for_snapshot` |
| Cash reconciliation | `app/eventloop.py` — `_tick_broker_balance`, `_auto_sync_markets` |
| Live envelope guards | `app/eventloop.py` — `_validate_live_envelope`, `_maybe_validate_live_envelope` |

---

## 10. Reference

- [`general.md`](general.md) — framework-wide layering and lifecycle.
- [`orders.md`](orders.md) — what happens inside `OrderService.update(...)` that the evaluator calls in Step 3.
- [`trades.md`](trades.md) — what happens inside `TradeService` when fills are detected.
- [`pipeline-api.md`](pipeline-api.md) — Step 5b internals.
- *§8 of the v8→v9 migration guide* — `Schedule` replaces `time_unit + interval`.
