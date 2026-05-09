---
sidebar_position: 4
---

# Portfolio Sync & Deposit Schedules

Real trading bots rarely operate on a static initial balance. Cash flows in (paychecks, transfers, profit reinvestment) and sometimes out (withdrawals). The framework treats external cash movement as a **first-class concept** so the same code works in backtests and in live deployments.

The contract is a single API: `context.sync_portfolio(market=...)`. It reconciles the portfolio's local `unallocated` cash with what is *actually* available on the broker (live) or with the simulated deposit schedule (backtest).

## TL;DR — Declarative deposit schedule on a market

The most common case — a recurring deposit (e.g. monthly paycheck DCA) — needs **zero strategy code**:

```python
from investing_algorithm_framework import (
    create_app,
    ScheduledDeposit,
    TimeUnit,
)

app = create_app()
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=2500,
    deposit_schedule=[
        ScheduledDeposit(
            amount=100.0, time_unit=TimeUnit.DAY, interval=30
        ),
    ],
    auto_sync=True,
)
```

With `auto_sync=True` the event loop calls `context.sync_portfolio(market=...)` at the start of every iteration. The strategy simply checks `context.get_unallocated()` and the new cash is already there.

## `ScheduledDeposit`

A frozen dataclass describing **one** deposit rule. Two mutually exclusive forms:

| Form | Fields | Behaviour |
|------|--------|-----------|
| **Recurring** | `amount`, `time_unit`, `interval` | Fires every `interval` units of `time_unit` from the anchor (the first time the loop sees the market). |
| **One-shot** | `amount`, `on` (timezone-aware `datetime`) | Fires once, at or after `on`. |

```python
from datetime import datetime, timezone
from investing_algorithm_framework import ScheduledDeposit, TimeUnit

# Weekly DCA top-up
ScheduledDeposit(amount=50.0, time_unit=TimeUnit.DAY, interval=7)

# One-time bonus on a fixed date
ScheduledDeposit(amount=1000.0, on=datetime(2025, 12, 24, tzinfo=timezone.utc))

# Negative amount = scheduled withdrawal
ScheduledDeposit(amount=-200.0, time_unit=TimeUnit.DAY, interval=30)
```

`MONTH` cadence is approximated as 30 days (`timedelta` has no calendar months). For exact calendar dates use one-shot deposits.

You can pass a list of `ScheduledDeposit` to `add_market(...)`, or add them later:

```python
app.add_deposit_schedule(
    market="BITVAVO",
    schedule=[ScheduledDeposit(amount=100.0, time_unit=TimeUnit.DAY, interval=30)],
)
app.set_market_auto_sync("BITVAVO", enabled=True)
```

## `context.sync_portfolio(market, allow_withdrawals=False, tolerance=1e-9) -> SyncResult`

This is the canonical reconciliation call. Behaviour depends on the environment:

| Mode | "Broker available" comes from |
|------|-------------------------------|
| **Live** (`PROD` / `DEV`) | `PortfolioProvider.get_position(...).amount` — the exchange's free balance for the trading symbol, **minus** cash reserved for orders the framework has created but the exchange has not yet acknowledged (`OrderStatus.CREATED` BUYs). This avoids flagging a brief race window between `create_order()` and the exchange ack as a phantom withdrawal. |
| **Backtest** | The `BrokerBalanceTracker` materialises the schedule. Due deposits accumulate in a "pending" bucket and are drained into `unallocated`. |

The returned `SyncResult` has fields:

```python
@dataclass(frozen=True)
class SyncResult:
    market: str
    kind: Literal["noop", "deposit", "withdrawal"]
    delta: float                  # broker_available - previous_unallocated
    broker_available: float
    previous_unallocated: float
    new_unallocated: float
    within_tolerance: bool = False         # |delta| <= tolerance, but not zero
    reserved_for_pending_orders: float = 0.0
```

### Tolerance

Pass `tolerance=` to ignore sub-cent rounding drift between the broker and your local books:

```python
# Treat anything under 1 cent of drift as a no-op
context.sync_portfolio(market="BITVAVO", tolerance=0.01)
```

When the absolute drift is at or below `tolerance` the call returns a `noop` result with `within_tolerance=True` and the raw `delta` still surfaced for diagnostics. The portfolio's `unallocated` is **not** modified.

### Withdrawal semantics

By default, `sync_portfolio` raises `PortfolioOutOfSyncError` if the broker has **less** cash than the portfolio thinks it owns. This is intentional — silently shrinking your bot's cash on a transient broker glitch would be a debugging nightmare.

Opt in to draining with `allow_withdrawals=True`:

```python
try:
    result = context.sync_portfolio(market="BITVAVO")
except PortfolioOutOfSyncError as err:
    log.warning(
        "Out of sync on %s: local=%s broker=%s delta=%s",
        err.market, err.local_unallocated, err.broker_available, err.delta,
    )
    # Decide: pause the bot, alert, or drain.
    context.sync_portfolio(market="BITVAVO", allow_withdrawals=True)
```

`unallocated` will never be pushed below zero regardless of the flag.

## Auto-sync error handling

`add_market(..., auto_sync=True)` is convenient but a single flaky API call should not crash a long-running bot. Pick the policy that matches your operational stance with `auto_sync_error_mode`:

| Mode | Behaviour on transient broker error |
|------|-------------------------------------|
| `"raise"` *(default)* | Propagate the exception. The event loop stops. Best during development — fail loudly. |
| `"warn"` | Log a warning and continue. Auto-sync retries on the next iteration. Best for live trading: a single 502 from the exchange shouldn't take the bot down. |
| `"halt"` | Log an error and disable auto-sync **for that market** until the app is restarted or `set_market_auto_sync(...)` is called again. The strategy keeps running on whatever cash it currently has. |

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=2500,
    auto_sync=True,
    auto_sync_error_mode="warn",
)
```

`PortfolioOutOfSyncError` is **always** re-raised regardless of mode — that's a hard data-integrity signal, not a transient.

## `fire_on_anchor` — deposit at t=0

By default a recurring deposit fires at `anchor + interval`, not at the anchor itself. Set `fire_on_anchor=True` to also fire on the anchor day:

```python
ScheduledDeposit(
    amount=500.0,
    time_unit=TimeUnit.DAY,
    interval=30,
    fire_on_anchor=True,  # also fires on day 0
)
```

This is useful for "fund the bot immediately at start, then top up monthly" patterns. Only valid for recurring deposits (one-shots fire on `on=` regardless).

## TWR-aware return metrics

Every deposit/withdrawal absorbed by `sync_portfolio` (or replayed by the vector backtest) is stamped onto the next `PortfolioSnapshot.cash_flow`. The framework's return metrics use this to compute **time-weighted returns** so that depositing $1,000 into your bot does not show up as $1,000 of P&L:

$$ r_t = \frac{V_t - \text{cash\_flow}_t}{V_{t-1}} - 1 $$

The following metrics are TWR-adjusted: **CAGR**, **monthly returns**, **yearly returns**, **mean daily return**, **Sharpe**, **Sortino**, **volatility**, **VaR / CVaR**, and the standard-deviation family. Snapshots without a `cash_flow` field (legacy data, mocks) gracefully fall back to the classic `pct_change()` behaviour.

> **Equity curve and drawdown** are exposed in **two flavours**:
>
> - `get_equity_curve` / `get_drawdown_series` / `get_max_drawdown` / `get_max_drawdown_duration` — raw account value, including deposits. Use these when you want to see "how many dollars did the account hold?".
> - `get_twr_equity_curve` / `get_twr_drawdown_series` / `get_twr_max_drawdown` / `get_twr_max_drawdown_duration` — alpha-only path scrubbed of external cash flows. Use these when comparing risk profiles across portfolios funded differently — depositing $1,000 during a drawdown won't artificially erase it.
>
> ```python
> from investing_algorithm_framework.services.metrics import (
>     get_twr_equity_curve, get_twr_max_drawdown,
> )
> # Growth-of-$1 alpha curve
> curve = get_twr_equity_curve(snapshots, base=1.0)
> dd = get_twr_max_drawdown(snapshots)  # e.g. 0.18 for 18%
> ```

## Mid-run schedule changes

`tracker.set_schedule(market, [...])` and `add_deposit_schedule` can be called at any time. The tracker preserves:

- **`pending`** — any deposits that already fired but haven't been absorbed by `sync_portfolio` yet.
- **`cash_flow_since_snapshot`** — TWR bookkeeping waiting to be drained by the next snapshot.

Only the schedule itself and `last_fired` anchors are reset — so swapping a 30-day schedule for a 7-day schedule mid-backtest doesn't accidentally "swallow" a pending deposit.

## Manual sync (without `auto_sync`)

If you prefer explicit control, leave `auto_sync=False` and call `sync_portfolio` from your strategy:

```python
class MyStrategy(TradingStrategy):
    def run_strategy(self, context, data):
        context.sync_portfolio(market="BITVAVO")
        cash = context.get_unallocated()
        ...
```

This pattern is useful if you want to sync only on specific bars, or after specific events (e.g. only after a fill notification in live mode).
or if you want to run a one-shot sync declare a task that calls `sync_portfolio` once at startup:

```python
from investing_algorithm_framework import Task

class SyncTask(Task):
    interval = None  # run once at startup

    def run(self, context):
        context.sync_portfolio(market="BITVAVO")
        log.info("Initial sync complete")

## Vector backtests

Vector backtests respect the same `deposit_schedule`. Because vector workers run in subprocesses, the schedule travels with `PortfolioConfiguration` (it is pickled). Each iteration's cash track has the due deposits added before signals are evaluated, so the equity curve includes external cash flows.

```python
from investing_algorithm_framework import PortfolioConfiguration, ScheduledDeposit, TimeUnit

PortfolioConfiguration(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=2500,
    deposit_schedule=[
        ScheduledDeposit(amount=100.0, time_unit=TimeUnit.DAY, interval=30),
    ],
)
```

## Worked example

See [`examples/strategies_showcase/08_dca_accumulation`](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/strategies_showcase/08_dca_accumulation) for a complete DCA bot that uses `deposit_schedule` + `auto_sync` to model recurring monthly deposits across a 2-year backtest.

## API summary

| Symbol | Where | Purpose |
|--------|-------|---------|
| `ScheduledDeposit` | `investing_algorithm_framework` | Declarative deposit rule (recurring or one-shot). |
| `SyncResult` | `investing_algorithm_framework` | Outcome of a sync call. |
| `PortfolioOutOfSyncError` | `investing_algorithm_framework` | Raised when broker balance < local unallocated and withdrawals are not opted in. |
| `app.add_market(deposit_schedule=, auto_sync=)` | App | Register a market with optional schedule and auto-sync flag. |
| `app.add_deposit_schedule(market, schedule)` | App | Attach a schedule to an existing market. |
| `app.set_market_auto_sync(market, enabled=True)` | App | Toggle per-market auto-sync. |
| `context.sync_portfolio(market, allow_withdrawals=False)` | Context | Reconcile local cash with broker / tracker. |
