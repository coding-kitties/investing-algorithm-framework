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

| Attribute | Class | Purpose |
|---|---|---|
| `position_sizes` | [`PositionSize`](./position-size.md) | How much capital to allocate per symbol — fixed amount or percentage of portfolio. |
| `stop_losses` | [`StopLossRule`](./stop-loss-rule.md) | Bar-end exit when price drops a fixed or trailing percentage from entry / peak. |
| `take_profits` | [`TakeProfitRule`](./take-profit-rule.md) | Bar-end exit when price rises a fixed or trailing percentage from entry / peak. |
| `scaling_rules` | [`ScalingRule`](./scaling-rule.md) | Pyramid into winners and partially close — `max_entries`, `scale_in_percentage`, `scale_out_percentage`, optional `max_position_percentage` cap. |
| `cooldowns` | [`CooldownRule`](./cooldown-rule.md) | Side-aware, per-symbol or portfolio-wide signal throttling after fills. |
| `trading_costs` | [`TradingCost`](./trading-cost.md) | Per-symbol fees and slippage applied during fill simulation. Supports [pluggable slippage models](./trading-cost.md#slippage-models) (volume-based, fixed spread, basis points). |

## Where Rules Are Enforced

| Rule | Vector backtest | Event-driven backtest | Live trading |
|---|---|---|---|
| `PositionSize` | ✅ | ✅ | ✅ |
| `StopLossRule` | ✅ | ✅ | ✅ |
| `TakeProfitRule` | ✅ | ✅ | ✅ |
| `ScalingRule` | ✅ | ✅ | ✅ |
| `CooldownRule` | ✅ | ✅ | ✅ |
| `TradingCost` (fees + slippage) | ✅ | ✅ | n/a — broker reports actual cost |

## Resolution Order

When more than one rule could fire at the same bar, the engine evaluates them in a deterministic order:

1. **Stop loss** (highest priority — defensive exit).
2. **Take profit**.
3. **Sell signal** from `generate_sell_signals()`.
4. **Scale-out signal** (only if no full sell fired).
5. **Buy signal** from `generate_buy_signals()` — gated by `CooldownRule` and `ScalingRule.cooldown_in_bars`.
6. **Scale-in signal** — gated by `ScalingRule.max_entries` and `max_position_percentage`.

Within each step, `TradingCost` is applied to the fill price, and `PositionSize` (or the relevant `scale_in_percentage`) determines the order amount.

## See Also

- [`PositionSize`](./position-size.md)
- [`StopLossRule`](./stop-loss-rule.md)
- [`TakeProfitRule`](./take-profit-rule.md)
- [`ScalingRule`](./scaling-rule.md)
- [`CooldownRule`](./cooldown-rule.md)
- [`TradingCost`](./trading-cost.md)
