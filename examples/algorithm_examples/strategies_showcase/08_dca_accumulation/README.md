# 08 — DCA Accumulation

**Fit:** ✅ Trivially simple, perfect example of a scheduled task.

## Idea

Dollar-cost averaging: buy a **fixed EUR amount** of BTC every week,
regardless of price. The point is to demonstrate the simplest possible
deployable strategy.

## Why this fits the framework

`time_unit=TimeUnit.DAY` + `interval=7` (or any cadence) is exactly the
intended use case for the bar-driven event loop. No indicators, no signal —
just a periodic side-effect.

### Funding sync — staying aware of new capital

Real DCA bots have one piece that paper examples almost always skip:
**capital arrives from outside the strategy** (a paycheck deposit, a
monthly transfer). If the bot only ever knows about its starting balance,
it will never deploy newly arrived cash and the "DCA" stops after a few
weeks.

The framework treats external cash flow as a first-class concept. You
declare it on the market and the event loop absorbs new funds for you:

```python
from investing_algorithm_framework import ScheduledDeposit, TimeUnit

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

On every iteration the engine calls `context.sync_portfolio(market=...)`
under the hood. The result is identical in both modes:

| Mode | Where "broker available" comes from |
|------|-------------------------------------|
| **Backtest** | The `BrokerBalanceTracker` materialises the schedule; due deposits land in a "pending" bucket and are drained into `unallocated`. |
| **Live** | `PortfolioProvider.get_position(...).amount` — the exchange's free balance. The schedule is informational only; any real deposit (paycheck, manual transfer, withdrawal) is absorbed automatically. |

If `broker_available < unallocated` (cash disappeared from the
exchange), `sync_portfolio` raises `PortfolioOutOfSyncError` by default.
Pass `allow_withdrawals=True` to opt into draining instead. You can also
call `context.sync_portfolio(market=...)` manually from inside a strategy
if you prefer not to use `auto_sync`.

### Production knobs

For live trading you typically want a few defaults relaxed so a single
flaky API call doesn't crash the bot:

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=2500,
    deposit_schedule=[
        ScheduledDeposit(
            amount=100.0,
            time_unit=TimeUnit.DAY,
            interval=30,
            # Optional: deposit also lands at t=0 (anchor day) instead of
            # only after the first interval has elapsed.
            fire_on_anchor=True,
        ),
    ],
    auto_sync=True,
    # "warn" → log + continue on transient broker errors; the bot keeps
    # running and retries next iteration. "raise" (default) propagates
    # and stops the loop. "halt" disables auto-sync for this market
    # after the first failure.
    auto_sync_error_mode="warn",
)
```

You can also pass `tolerance=` to `context.sync_portfolio()` to ignore
sub-cent rounding drift when reconciling against the exchange:

```python
context.sync_portfolio(market="BITVAVO", tolerance=0.01)
```

> **TWR-aware metrics:** every deposit absorbed by `sync_portfolio` is
> stamped onto the next portfolio snapshot's `cash_flow` field. CAGR,
> monthly/yearly returns, Sharpe, Sortino, volatility, VaR and the std
> metrics all subtract this from the period's ending value before
> computing the return — so depositing into a DCA bot does not inflate
> its reported alpha.

## Parameters

| Name | Default | Notes |
|------|---------|-------|
| `symbol` | `BTC/EUR` | |
| `dca_amount_eur` | `25` | EUR spent per buy. |
| `cadence_days` | `7` | Weekly. |

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## Note

DCA is *not a trading strategy* in the alpha-generation sense. It is a
behavioural commitment device that smooths entry timing. Use it as an
overlay for long-term core positions, not as a standalone alpha. Also the overall concept of rebalancing can be applied to any strategy, not just DCA, it's a general tool for keeping your actual portfolio aligned with your intended allocation and your available capital.
