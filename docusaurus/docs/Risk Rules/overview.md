---
sidebar_position: 1
---

# Risk Rules Overview

The framework lets you express risk and execution behaviour as **declarative rule lists** on a `TradingStrategy` rather than as ad-hoc code paths. The vector backtest engine, the event-driven backtest engine and the live trading runtime all read the same rule objects, so a strategy behaves identically across all three modes.

```python
from investing_algorithm_framework import (
    TradingStrategy,
    PositionSize,
    StopLossRule,
    TakeProfitRule,
    ScalingRule,
    ExposureRule,
    CooldownRule,
    TradingCost,
)


class MyStrategy(TradingStrategy):
    symbols = ["BTC", "ETH"]

    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20),
        PositionSize(symbol="ETH", percentage_of_portfolio=20),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=5,
            sell_percentage=100, trailing=True,
        ),
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC", percentage_threshold=10,
            sell_percentage=50, trailing=False,
        ),
    ]
    scaling_rules = [
        ScalingRule(
            symbol="BTC", max_entries=3,
            scale_in_percentage=[50, 25],
        ),
    ]
    # Portfolio-wide, unlike the per-symbol lists above: caps total
    # invested value across every symbol combined.
    exposure_rule = ExposureRule(max_portfolio_percentage=80)
    cooldowns = [
        CooldownRule(
            symbol="BTC", trigger="sell", blocks="buy", bars=12,
        ),
        CooldownRule(trigger="any", blocks="any", bars=2),
    ]
    trading_costs = [
        TradingCost(
            symbol="BTC", fee_percentage=0.1,
            slippage_percentage=0.05,
        ),
    ]
```

## The Rule Catalogue

| Attribute | Class | Scope | Purpose |
|---|---|---|---|
| `position_sizes` | [`PositionSize`](./position-size.md) | Per-symbol | How much capital to allocate per symbol — fixed amount or percentage of portfolio. |
| `stop_losses` | [`StopLossRule`](./stop-loss-rule.md) | Per-symbol | Bar-end exit when price drops a fixed or trailing percentage from entry / peak. |
| `take_profits` | [`TakeProfitRule`](./take-profit-rule.md) | Per-symbol | Bar-end exit when price rises a fixed or trailing percentage from entry / peak. |
| `scaling_rules` | [`ScalingRule`](./scaling-rule.md) | Per-symbol | Pyramid into winners and partially close — `max_entries`, `scale_in_percentage`, `scale_out_percentage`, optional `max_position_percentage` cap (caps *that symbol's* position size). |
| `exposure_rule` | [`ExposureRule`](./exposure-rule.md) | Portfolio-wide | Caps total invested value *across every symbol combined* — e.g. "never more than 80% invested." Singular, not a list. |
| `cooldowns` | [`CooldownRule`](./cooldown-rule.md) | Per-symbol or portfolio-wide | Side-aware signal throttling after fills. |
| `trading_costs` | [`TradingCost`](./trading-cost.md) | Per-symbol | Fees and slippage applied during fill simulation. Supports [pluggable slippage models](./trading-cost.md#slippage-models) (volume-based, fixed spread, basis points). |

### Position sizing vs. exposure: which one do I need?

- **"How much do I buy on each entry?"** → [`PositionSize`](./position-size.md).
- **"How big can *this one symbol's* position grow via pyramiding?"** → [`ScalingRule.max_position_percentage`](./scaling-rule.md).
- **"How much of my *whole portfolio* can be invested at once, across everything?"** → [`ExposureRule`](./exposure-rule.md).

All three can be combined: `PositionSize` sizes an entry, `ScalingRule` caps how far one symbol can grow, and `ExposureRule` is the final portfolio-wide backstop that scales every cash-consuming order down (or drops it) if the combined request would breach the cap.

## Where Rules Are Enforced

| Rule | Vector backtest | Event-driven backtest | Live trading |
|---|---|---|---|
| `PositionSize` | ✅ | ✅ | ✅ |
| `StopLossRule` | ✅ | ✅ | ✅ |
| `TakeProfitRule` | ✅ | ✅ | ✅ |
| `ScalingRule` | ✅ | ✅ | ✅ |
| `ExposureRule` | ✅ | ✅ | ✅ |
| `CooldownRule` | ✅ | ✅ | ✅ |
| `TradingCost` (fees + slippage) | ✅ | ✅ | n/a — broker reports actual cost |

## Resolution Order

When more than one rule could fire at the same bar, the engine evaluates them in a deterministic order:

1. **Stop loss** (highest priority — defensive exit).
2. **Take profit**.
3. **`CLOSE_LONG` signal** from `generate_signals()`.
4. **`SCALE_OUT` signal** (only if no full close fired).
5. **`OPEN_LONG` signal** from `generate_signals()` — gated by `CooldownRule` and `ScalingRule.cooldown_in_bars`.
6. **`SCALE_IN` signal** — gated by `ScalingRule.max_entries` and `max_position_percentage`.

Within each step, `TradingCost` is applied to the fill price, and `PositionSize` (or the relevant `scale_in_percentage`) determines the order amount. Finally, `ExposureRule` (if set) scales down or drops any remaining cash-consuming orders so total invested value never exceeds its cap — this runs after sizing, as a portfolio-wide backstop over every symbol's orders for the tick.

## See Also

- [`PositionSize`](./position-size.md)
- [`StopLossRule`](./stop-loss-rule.md)
- [`TakeProfitRule`](./take-profit-rule.md)
- [`ScalingRule`](./scaling-rule.md)
- [`ExposureRule`](./exposure-rule.md)
- [`CooldownRule`](./cooldown-rule.md)
- [`TradingCost`](./trading-cost.md)
