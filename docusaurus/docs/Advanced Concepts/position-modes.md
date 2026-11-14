---
sidebar_position: 5
---

# Position Modes: NETTING vs. HEDGE

By default, the framework enforces **one open position direction per symbol**: a long and a short on the same symbol can never coexist, and an opposite-side signal is rejected. `PositionMode.HEDGE` relaxes this so a strategy can hold an independent long **and** short on the same symbol at the same time, each with its own entry, stop-loss/take-profit, cooldown, and P&L.

This page explains how the two modes differ and how each part of the framework behaves under `HEDGE`.

## Configuring the mode

`PositionMode` defaults to `NETTING` and is set per portfolio, either via `add_market` or directly on `PortfolioConfiguration`:

```python
from investing_algorithm_framework import create_app, PositionMode

app = create_app()
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000,
    position_mode=PositionMode.HEDGE,  # default: PositionMode.NETTING
)
```

```python
from investing_algorithm_framework import PortfolioConfiguration, PositionMode

PortfolioConfiguration(
    market="BITVAVO",
    trading_symbol="EUR",
    position_mode=PositionMode.HEDGE,
)
```

## What changes under HEDGE

### Position accounting

A `Position` still stores exactly one row per `(portfolio, symbol)`, but it tracks the long and short legs independently:

```python
position.long_amount   # units held long
position.short_amount  # units held short
position.amount        # net exposure: long_amount - short_amount
position.gross_amount  # long_amount + short_amount
position.long_cost
position.short_cost
position.net_cost       # long_cost - short_cost
position.gross_cost     # long_cost + short_cost
```

In `NETTING` mode, only one leg is ever nonzero, so `amount` and `cost` behave exactly as before. `HEDGE` is fully additive — nothing about `NETTING` accounting changes.

### Order validation and fills

- `BUY` / `SELL` only ever affect the **long** leg.
- `SHORT` / `COVER` only ever affect the **short** leg.
- Opening a `SHORT` no longer requires a flat long position (and vice versa) — the two legs are independent.
- `SELL` can only close as much as `position.long_amount`; `COVER` can only close as much as `position.short_amount`.

### Trades

Each leg is backed by its own set of `Trade` rows (`Trade.is_short` distinguishes them). `SELL` orders only ever close long trades; `COVER` orders only ever close short trades — a `SELL` can never accidentally close a short trade or vice versa.

### Stop-loss / take-profit

`StopLossRule` and `TakeProfitRule` accept an optional `side`, so the same symbol can have independent rules per leg:

```python
from investing_algorithm_framework import StopLossRule, TakeProfitRule

stop_losses = [
    StopLossRule(symbol="BTC", percentage_threshold=5, sell_percentage=100, side="long"),
    StopLossRule(symbol="BTC", percentage_threshold=8, sell_percentage=100, side="short"),
]
take_profits = [
    TakeProfitRule(symbol="BTC", percentage_threshold=10, sell_percentage=100, side="long"),
]
```

If `side` is omitted, the rule applies to whichever leg is open (same behaviour as `NETTING`). A rule with an explicit `side` only attaches to orders opening that side.

### Cooldowns

`CooldownRule` needs no extra configuration — in `HEDGE` mode, cooldown state is tracked per `(symbol, "long" | "short")` instead of per `symbol`. Closing (or triggering a stop-loss/take-profit on) the long leg starts a cooldown that only blocks new long signals; the short leg is unaffected, and vice versa.

### Strategy signals

`ResolveConflictsPhase` relaxes its single-slot-per-symbol rule in `HEDGE` mode: `OPEN_LONG` and `OPEN_SHORT` can both be approved for the same symbol on the same tick. Same-side conflicts (e.g. two long opens) are still resolved by the strategy's `conflict_policy`, exactly as in `NETTING`.

### Engines

Both the event-driven and vector backtest engines support `HEDGE` — each maintains independent long/short state (open trade, cooldown, risk rules) per symbol and can open, scale, and close either leg on the same bar. A run's effective mode is recorded in `metadata["position_mode"]`.

### Reporting

Backtest reports and the dashboard expose net exposure, gross exposure, and the long/short breakdown per position, in addition to the existing net-only fields — see [Signal Rejections](#signal-rejections-and-flips) below for how rejected signals are surfaced regardless of mode.

## Interaction with `flip_on_opposite_signal`

`TradingStrategy.flip_on_opposite_signal` (default `False`) only applies in `NETTING` mode. When enabled, an `OPEN_SHORT` signal against an open long closes the long and opens the short on the same bar (and symmetrically for `OPEN_LONG` against an open short) — a `SELL`/`COVER` and the opposite open are emitted together instead of the signal being rejected.

```python
class MyStrategy(TradingStrategy):
    flip_on_opposite_signal = True
```

In `HEDGE` mode this flag has no effect, since both directions can simply coexist — there is nothing to flip.

## Signal Rejections and flips

Every dropped signal (cooldown, existing position, insufficient capital, etc.) is recorded in `BacktestRun.signal_events`. `BacktestRun.get_rejection_summary()` aggregates these by reason:

```python
{"already_in_position": 42, "cooldown": 88, "insufficient_capital": 3}
```

`BacktestReport.pretty_print()` includes a "Signal rejections" section whenever the count is greater than zero, and the dashboard timeline plots suppressed signals as grey markers alongside fills — so a `HEDGE` (or `NETTING`) strategy that appears "not to be firing" can be diagnosed without inspecting `signal_events` by hand.

## Live trading

`HEDGE` is currently **backtest-only**. On startup, `App.initialize_services()` validates every live (non-backtest) portfolio: if its `position_mode` is `HEDGE`, both the resolved `OrderExecutor` and `PortfolioProvider` for that market must explicitly return `True` from `supports_position_mode(market, PositionMode.HEDGE)`, or startup raises an `OperationalException` naming the missing adapter and capability.

The bundled CCXT adapters do not opt in — `CCXTOrderExecutor` does not yet route venue-specific directional (`positionSide`) order parameters, and `CCXTPortfolioProvider` reconciles positions via `fetchBalance()`, which cannot represent two simultaneous derivative legs. A custom adapter can enable live `HEDGE` by implementing both:

```python
class MyHedgeCapableExecutor(OrderExecutor):
    def supports_position_mode(self, market, position_mode):
        if PositionMode(position_mode) == PositionMode.NETTING:
            return self.supports_market(market)
        return self.supports_market(market)  # after verifying directional routing
```

The same method exists on `PortfolioProvider`, and must only return `True` once the provider can fetch and reconcile independent long/short legs for that market.
