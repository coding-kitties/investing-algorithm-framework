---
sidebar_position: 6
---

# Broker-Native Mirror Stop-Loss / Take-Profit

By default, `StopLossRule` and `TakeProfitRule` are enforced **client-side**: the bot's own event loop watches the last reported price on every tick and creates a close order the moment a rule triggers. That means protection only works while the bot is actually running — if the process crashes, loses its network connection, or is redeployed at the wrong moment, an open position can blow through its stop with nobody watching.

`mirror_on_exchange=True` closes that gap by *also* placing a real, resting `STOP` order directly on the exchange when a trade opens. The exchange enforces the trigger itself, independent of whether the bot is up. The client-side check keeps running as the primary mechanism; the mirror order is a safety net underneath it.

```python
from investing_algorithm_framework import StopLossRule, TakeProfitRule

stop_losses = [
    StopLossRule(
        symbol="BTC",
        percentage_threshold=5.0,
        sell_percentage=100,
        mirror_on_exchange=True,
    ),
]
take_profits = [
    TakeProfitRule(
        symbol="BTC",
        percentage_threshold=10.0,
        sell_percentage=100,
    ),
]
```

`mirror_on_exchange` defaults to `False` and is available on both `StopLossRule` and `TakeProfitRule`, independent of `trailing`/`sell_percentage`.

## What actually happens

1. **Trade opens** — once a BUY order fills and the trade is created, any attached rule with `mirror_on_exchange=True` gets a resting `STOP` order placed on the exchange for its trigger price and `sell_percentage` amount.
2. **Client-side check keeps running** — the rule is still evaluated every tick exactly as before. Whichever side fires first wins.
3. **If the mirror order fires first** (bot was down, or the exchange simply reacted faster), the next time the bot polls pending orders it detects the fill, closes the trade, and records the rule as triggered.
4. **If the client-side check fires first**, the bot cancels the resting mirror order before creating its own close order, so the two can never both execute for the same trade.
5. **If the trade closes some other way** (a sibling rule triggers, or you call `context.close_trade()` manually), any still-resting mirror order for that trade is cancelled too.

None of this changes the trade/position API you already use — `TradeStopLoss`/`TradeTakeProfit` still expose `triggered`/`triggered_at` the same way. Two extra fields let you tell mirror-driven closes apart from client-side ones:

| Field | Meaning |
|---|---|
| `mirror_order_id` | Id of the currently-resting broker-native order backing this rule, if any. |
| `mirror_triggered` / `mirror_triggered_at` | Set when the mirror order (not the client-side check) is what actually closed the trade. |

## Failure handling

Placing or cancelling a mirror order never blocks the trade it's attached to. If the exchange call fails for any reason, the failure is logged as a warning and the client-side check remains fully in effect — you lose the safety net for that one rule, not the rule itself.

## Scope and limitations

- **Long trades only.** Short trades close via `COVER` orders, which use a different accounting path than the `TradeAllocation`/`SELL` mechanism mirror orders rely on; short-side mirroring isn't implemented yet.
- **Requires an executor that supports it.** Each `OrderExecutor` exposes a `supports_mirror_orders` capability flag (`True` by default). The built-in `PaperTradingOrderExecutor` (local simulation) overrides it to `False`, since there's no real venue to rest an order on — mirroring is silently skipped for `PaperTradingMode.LOCAL` markets, no error raised.
- **Skipped in backtests.** There is no exchange to mirror against, so `mirror_on_exchange` is a no-op during `run_backtest()`.
- **A stop-loss and a take-profit on the same trade never both rest for the same shares.** Neither reserves the position at placement time (it isn't a decided close yet), so the framework tracks how much is already committed to a still-live mirror order on the trade and skips placing a second one that would double-commit those shares (logged, not raised). Whichever rule's mirror order fires first also cancels any other still-resting mirror order on that trade, so a stale sibling never lingers. True one-cancels-other (OCO) placement on the exchange itself is not used — this is enforced by the bot, with the same small window of dual exposure that exists for any bracket-order strategy that isn't natively OCO.

## When to use it

Mirroring is most valuable for the trade-ending-in-catastrophe scenario: a stop-loss on a leveraged or otherwise high-conviction position, where a few minutes of bot downtime at the wrong moment is unacceptable. It adds one extra resting order per mirrored rule, so it isn't free — most strategies are well served by the default client-side-only behavior, with mirroring reserved for the positions where downside protection matters most.

## See Also

- [`StopLossRule`](../Risk%20Rules/stop-loss-rule.md)
- [`TakeProfitRule`](../Risk%20Rules/take-profit-rule.md)
- [Paper Trading](./paper-trading.md)
