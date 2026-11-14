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

### Live Run Reports

`report = app.run(number_of_iterations=1)` returns the persisted report as a
dictionary in live and paper mode. Bounded invocations aggregate their ticks.
Continuous runs persist one report per strategy execution tick, including
ticks that emit no signals. Idle polling does not create reports. Signals and
decision traces are tick-local; positions, portfolios, trades, and pending
orders describe current state and can legitimately appear in multiple reports.

Every report has a string `id` formatted as
`<algorithm_id>_<UTC-start-datetime>_<unique-suffix>`, including transient
backtest reports. The suffix distinguishes separate executions at the same
timestamp. Reports remain algorithm-level: `strategy_ids` lists the configured
strategies covered by the invocation; per-tick signals, orders, trades and
decision traces retain their individual `strategy_id` attribution.

`signals` is a flat list, not a list of per-strategy wrappers. Each emitted
signal has `strategy_id`, evaluation `timestamp`, `symbol`, `side`, `strength`,
`source`, `metadata`, pipeline `status`, and rejection `reason` (otherwise
`null`). Sides remain `open_long`, `close_long`, `open_short`, `close_short`,
`scale_in`, and `scale_out`. A no-signal tick has `signals: []`.

`stop_losses` and `take_profits` are independent protective-execution lists,
also populated on no-signal ticks. Each event has `event_type` (`trigger` or
`fill`), UTC `timestamp`, `order_id`, owning `strategy_id`, `symbol`, `direction`,
`amount`, `order_amount`, cumulative `filled_amount`, `price`, `price_source`,
`order_status`, and recorded `rules`/`trades` references. Rules retain their
threshold and trailing flag. Trigger prices preserve the triggering observation,
even when execution changes the order price. Each fill update records its own
time, price, delta amount and sequence; cancellations do not create extra fills.
Snapshots can repeat these events: consumers should deduplicate by order/event
type and fill sequence, not sum snapshots.

Resting broker-mirror placement is not a protective trigger. A reported broker
trigger (or an actual fill when the broker omits a separate trigger notification)
is required; its trigger price source is the recorded stop `threshold`, not an
invented market observation. Legacy orders with an explicit protective
`order_reason` can provide creation/update-time evidence, marked with
`legacy_order_price` for fills, but unavailable rule details are not reconstructed.
Lists default to empty for old reports and survive JSON, SQL and API serialization.

`confluence_scores` contains every evaluated confluence card, whether or not
it produced a signal. Each entry has `strategy_id`, `timestamp`, `symbol`,
`card_id`, `side`, readiness and qualification flags, total/minimum scores,
group scores and rule evaluations, and a portable `decision_trace`. Native
evaluation includes inactive scale-in stages, since those cards were scored
too. Qualification is kept separate from the signal outcome: `signal_status`
is `approved`, `rejected`, `not_emitted`, `not_triggered`, or `unknown`, and `signal_reason`
contains the blocking reason (otherwise `null`). For example, a qualified
long-entry card may have `signal_status: "rejected"` and
`signal_reason: "resolve_conflicts.state_block_open"`. Unready/unqualified
cards use `confluence.indicators_not_ready`/`confluence.not_qualified`.
Qualified scale-in cards that are not emitted distinguish
`confluence.scale_in_requires_position`, `confluence.scale_in_stage_inactive`,
and `confluence.scale_in_stage_completed`. Failed/interrupted execution uses
`unknown` with `strategy.execution_incomplete` when no final pipeline outcome
is available. Approval is not proof of an order fill or trade execution.
Generic explanations remain in `decision_traces`.

`resolve_conflicts.state_block_open` means an existing position prevents a
new-position entry; it does not identify a cooldown. Actual cooldown gates
capture `signals[].reason_details`, copied to
`confluence_scores[].signal_reason_details`, with `cooldown_bars` (when the
configured duration is known) and `remaining_bars`. CooldownRule details also
record scope, trigger and blocked side. Counts use evaluation ticks and preserve
the existing release boundary: a rule triggered at tick `t` releases at
`t + bars`. Older reports without these details do not imply any duration or
remaining count; charts must not borrow current configuration to fill them.

Stateful event evaluation checks the position before scoring exit cards. With
no matching long/short position, native and default concrete exit cards have
`evaluation_status: "skipped"`, `signal_status: "not_triggered"` and reason
`confluence.long_exit_requires_position`/`confluence.short_exit_requires_position`.
Their score, readiness, qualification, groups and rule results are absent, not
fabricated as zero or false. No exit signal is emitted. Shared indicators and
lookback histories continue updating so cards evaluate normally once a position
opens. A long asset holding without an open trade still qualifies as a position.
Pure `generate_signals_from_cards(EvaluationContext(...))` calls and vector
masks have no portfolio context and remain state-independent.
Prepared backtests still precompute their score caches; the position gate skips
per-tick cache copies/scoring and detailed scoring-report construction. It does
not claim to eliminate shared indicator computations or all backtest preparation.

New captures also include configured `maximum_score`, per-group
`maximum_score`/`aggregation`, and per-rule `weight`, `maximum_points`,
`condition`, and explicit `required` flags. Native rules retain their observed
`value`, indicator/output binding, timeframe, threshold, comparison and lookback
so a rolling trigger is not mistaken for a current-value threshold crossing.
Capacities respect sum/max aggregation and signed weights; credited `points`
are unchanged. `overall_minimum_score` is null for group-threshold cards, which
instead carry `qualification_description` including any override path.
`signal_strength` is the actual emitted signal's strength, or null when no
signal was emitted. It is not score divided by maximum.
`position_before` records flat/long/short/hedged state, filled open-lot counts
(`long_entries`/`short_entries`), and the configured scaling `maximum_entries`
before strategy execution. These counts describe open lots, not remaining
ladder capacity. Older captures remain unchanged; missing details must not be
reconstructed from current strategy settings.

`data_sources` contains one latest completed row per source per strategy/tick:
`identifier`, `strategy_id`, `symbol`, `data_type`, `time_frame`, `market`,
evaluation `timestamp`, `source_timestamp`, and a `values` object (for example
`Open`, `High`, `Low`, `Close`, `Volume`). OHLCV rows are eligible only when
their opening timestamp plus the timeframe is at or before evaluation time.
Calendar month/year frames use calendar completion boundaries. Custom frame
rows are available at their recorded timestamp. Empty/unready sources have
`source_timestamp: null` and `values: {}`. Non-tabular source observations
retain their mapping/scalar values; unavailable observation times remain
`null`. Full history windows, provider credentials and source HTTP headers
are not copied. Inputs are captured before strategy code can mutate them.

Every report has an `indicators` list, independent of whether signals fired:

```json
{
  "indicators": [
    {
      "strategy_id": "mean_reversion",
      "symbol": "BTC",
      "timestamp": "2025-01-01T12:00:00+00:00",
      "name": "z_score_long.zscore",
      "value": -2.4
    }
  ]
}
```

It contains every evaluated indicator output (`<indicator_id>.<output_column>`)
and explicitly recorded decision-trace entries with `group="indicators"`,
including traces attached to approved or rejected signals. Values are
deduplicated per strategy/symbol/tick/name; evaluated outputs take precedence
over duplicate trace entries. Decision traces themselves are unchanged.
Warm-up and other non-finite numeric values are represented as `null`.
`context.record()` remains separate because it can contain arbitrary metrics.

Bounded invocations retain observations from every tick, with each observation's
own timestamp. Continuous reports contain only the current tick's observations,
including values evaluated before a strategy failure. Reports that evaluated
no indicators and recorded no indicator trace entries contain `indicators: []`.
The same tick-local lifecycle applies to confluence scores and source rows.
The list is persisted in SQL and exposed by the run-report API. Custom indicator
engines should implement `snapshot(evaluation)` returning flat
`symbol`/`name`/`value` records, as the built-in engines do.

Reports have `status` (`completed`, `algorithm_disabled`, `execution_error`,
`interrupted`, `no_strategy_due`, or `loop_stopped`) and optional `error` text.
There is no top-level `reason`; signal rejection reasons are unchanged.
Disabled invocations use `algorithm_disabled`, and accepted manual requests
stopped before execution use `loop_stopped`.
A synchronous failure persists a fresh `execution_error` or `interrupted` report
before re-raising its original exception. `app.get_last_run_report()` exposes
the latest outcome; `app.get_run_reports()` reads persisted history. Storage
failures cannot guarantee persistence and never substitute an earlier report.

`Environment` has `PROD` (real trading), `PAPER` (simulated trading), `BACKTEST`
(historical simulation), and `TEST` (automated tests). `DEV` has been removed;
use `PROD` or `PAPER` according to how orders execute. There is no report-level
`is_paper`. Existing all-paper portfolio configurations resolve to `PAPER`
unless running in `TEST` or `BACKTEST`. Setting `ENVIRONMENT="PAPER"` makes
`add_market()` default to paper trading; directly supplied portfolio
configurations must use `paper_trading=True`. Mixed real/paper portfolios
are rejected. Paper mode uses `paper-database.sqlite3`, separate from
`prod-database.sqlite3`.
Existing database files are not moved automatically; set
`SQLALCHEMY_DATABASE_URI` explicitly to reuse an earlier paper-only database.

Legacy run reports are not migrated or backfilled. Use a fresh database
when switching from the previous report schema.

For a running web algorithm, use
`app.container.algorithm_runner().invoke_now(wait=True, timeout=30)` or
`POST /api/algorithm/invoke?wait=true&timeout=30`. The result is the report for
the requested execution tick, not the latest unrelated report. Requests queued
before the same tick are coalesced and share its report. The HTTP response
contains it in `report`. Python raises `TimeoutError` and HTTP returns 504 when
the wait expires; execution is not cancelled and its outcome is still persisted.
Without `wait`, invocation only acknowledges queueing. Unknown strategy IDs
are rejected before queueing. Background strategy failures return failed
reports to waiters and retain the runner's existing stop-on-error behavior.

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
