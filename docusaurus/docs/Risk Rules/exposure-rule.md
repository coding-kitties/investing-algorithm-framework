---
sidebar_position: 5
---

# ExposureRule

`ExposureRule` caps the **total percentage of your portfolio that may be invested at once, across every symbol combined**. Where [`PositionSize`](./position-size.md) sizes one entry and [`ScalingRule.max_position_percentage`](./scaling-rule.md) caps one symbol's position, `ExposureRule` is the portfolio-wide backstop — e.g. "never have more than 80% invested, always keep at least 20% as a cash buffer."

```python
from investing_algorithm_framework import ExposureRule
```

## Signature

```python
ExposureRule(
    max_portfolio_percentage: float,
)
```

| Parameter | Type | Description |
|---|---|---|
| `max_portfolio_percentage` | `float` | Maximum percentage (0–100] of total portfolio value that may be invested at once, across all positions combined. |

Unlike `position_sizes`/`scaling_rules`, `exposure_rule` is **portfolio-wide**, so a strategy sets a single instance, not a per-symbol list:

```python
class MyStrategy(TradingStrategy):
    symbols = ["BTC", "ETH"]
    exposure_rule = ExposureRule(max_portfolio_percentage=80.0)
```

## How it's enforced

`ExposureRule` is enforced by `ApplyRiskBudgetPhase`, the same phase that already prevents overspending past unallocated cash. Every tick, it computes how much of the portfolio is already invested and tightens the cash available for **new** `OPEN_LONG`/`SCALE_IN` orders to whatever headroom remains under the cap:

```text
already_invested = portfolio_value - unallocated
headroom         = (portfolio_value * max_portfolio_percentage / 100) - already_invested
```

If the strategy's signals this tick would spend more than `headroom`, every cash-consuming order is scaled down proportionally (same mechanism used for the plain available-cash check), or dropped entirely if the cap is already reached. Closing orders (`CLOSE_LONG`, `CLOSE_SHORT`, `SCALE_OUT`) are never affected — you can always exit a position regardless of the exposure cap.

## Example

```python
from investing_algorithm_framework import (
    TradingStrategy, PositionSize, ExposureRule, Schedule, TimeUnit,
)


class ConservativeStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC", "ETH"]

    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=60.0),
        PositionSize(symbol="ETH", percentage_of_portfolio=60.0),
    ]
    # Even though each position size alone could reach 60%, and both
    # combined would be 120%, the exposure cap keeps total invested
    # value at 80% of the portfolio — orders are scaled down
    # proportionally to fit.
    exposure_rule = ExposureRule(max_portfolio_percentage=80.0)
```

## Interaction With Other Rules

- **`PositionSize`** — determines how much a *single* entry wants to spend; `ExposureRule` is the ceiling across all entries combined, applied after sizing.
- **`ScalingRule.max_position_percentage`** — caps one *symbol's* total position size; `ExposureRule` caps the *whole portfolio's* total invested value across every symbol.
- **Available-cash scaling** — `ExposureRule` tightens the same proportional-scaling mechanism that already prevents spending more than `unallocated` cash; it never loosens it.

## See Also

- [Risk Rules Overview](./overview.md)
- [`PositionSize`](./position-size.md)
- [`ScalingRule`](./scaling-rule.md)
