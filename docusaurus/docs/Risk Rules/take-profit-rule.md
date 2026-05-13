---
sidebar_position: 4
---

# TakeProfitRule

`TakeProfitRule` exits a position when the price rises a configured percentage from a reference point — the **entry price** (fixed) or a **rolling peak that is only set after the first profit threshold is hit** (trailing).

```python
from investing_algorithm_framework import TakeProfitRule
```

## Signature

```python
TakeProfitRule(
    symbol: str,
    percentage_threshold: float,
    sell_percentage: float,
    trailing: bool = False,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` | — | Target symbol (e.g. `"BTC"`). |
| `percentage_threshold` | `float` | — | Percent gain over the reference that triggers the exit. |
| `sell_percentage` | `float` | — | Percent of the current position to liquidate (`100` = full close). |
| `trailing` | `bool` | `False` | `True` arms a trailing exit once the threshold is first reached; `False` exits immediately on the first touch. |

## Fixed vs Trailing

### Fixed (`trailing=False`)

Reference price = **entry price**. The first time the price touches `entry × (1 + threshold/100)`, the rule fires.

```text
Buy at 100, threshold=5
→ exit_price = 105
Price rises to 105 → exit at ~105
```

### Trailing (`trailing=True`)

The take-profit price is **not** set at entry. It is armed only when the threshold is first reached, then it ratchets with the rolling peak. This lets winners run while still locking in profit on the way back down.

```text
Buy at 100, threshold=5
take_profit_price = None until price hits 105

Price hits 105 → take_profit_price = 105 (armed, peak=105)
Price rises to 120 → peak=120, take_profit_price = 114
Price rises to 150 → peak=150, take_profit_price = 142.50
Price falls to 142.50 → exit at ~142.50
```

## Examples

### Fixed full exit at +10 %

```python
take_profits = [
    TakeProfitRule(
        symbol="BTC",
        percentage_threshold=10.0,
        sell_percentage=100,
        trailing=False,
    ),
]
```

### Trailing with partial trim

```python
take_profits = [
    TakeProfitRule(
        symbol="BTC",
        percentage_threshold=8.0,
        sell_percentage=50,   # trim half once trailing exit fires
        trailing=True,
    ),
]
```

### Laddered exits

```python
take_profits = [
    TakeProfitRule(
        symbol="BTC", percentage_threshold=5.0,
        sell_percentage=25, trailing=False,
    ),
    TakeProfitRule(
        symbol="BTC", percentage_threshold=15.0,
        sell_percentage=50, trailing=False,
    ),
    TakeProfitRule(
        symbol="BTC", percentage_threshold=10.0,
        sell_percentage=100, trailing=True,
    ),
]
```

This trims 25 % at +5 %, 50 % of the remainder at +15 %, and runs the rest with a 10 % trailing exit.

## Resolution Order

`TakeProfitRule` is evaluated **after** `StopLossRule` and **before** the strategy's own sell signals. See the [Risk Rules Overview](./overview.md#resolution-order).

## Interaction With Other Rules

- **`TradingCost`** — slippage is applied to the exit fill price (`sell` direction).
- **`CooldownRule`** — a take-profit fill counts as a `sell` event for cooldown bookkeeping.
- **`ScalingRule`** — `sell_percentage` is taken from the *current* position, including all scale-ins.

## See Also

- [`StopLossRule`](./stop-loss-rule.md)
- [`CooldownRule`](./cooldown-rule.md)
- [Risk Rules Overview](./overview.md)
