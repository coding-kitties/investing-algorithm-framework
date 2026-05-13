---
sidebar_position: 3
---

# StopLossRule

`StopLossRule` exits a position when the price drops a configured percentage from a reference point. The reference is either the **entry price** (fixed stop) or the **rolling peak since entry** (trailing stop).

```python
from investing_algorithm_framework import StopLossRule
```

## Signature

```python
StopLossRule(
    symbol: str,
    percentage_threshold: float,
    sell_percentage: float,
    trailing: bool = False,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` | — | Target symbol the rule applies to (e.g. `"BTC"`). |
| `percentage_threshold` | `float` | — | Percent drop from the reference price that triggers the exit. |
| `sell_percentage` | `float` | — | Percent of the current position to liquidate when the stop fires (`100` = full close). |
| `trailing` | `bool` | `False` | `True` ratchets the reference up to the rolling peak; `False` pins it to entry. |

## Fixed vs Trailing

### Fixed (`trailing=False`)

Reference price = **entry price**. The stop never moves.

```text
Buy at 100, threshold=5
→ stop_price = 95
Price rises to 120 → stop unchanged at 95
Price falls to 95  → exit at ~95
```

### Trailing (`trailing=True`)

Reference price = **highest price since entry**. The stop ratchets up — never down.

```text
Buy at 100, threshold=5
→ stop_price = 95
Price rises to 120 → peak=120, stop_price = 114
Price rises to 150 → peak=150, stop_price = 142.50
Price falls to 142.50 → exit at ~142.50  (locked-in profit)
```

## Examples

### Hard stop, full exit

```python
stop_losses = [
    StopLossRule(
        symbol="BTC",
        percentage_threshold=5.0,
        sell_percentage=100,
        trailing=False,
    ),
]
```

### Trailing stop with partial trim

```python
stop_losses = [
    StopLossRule(
        symbol="BTC",
        percentage_threshold=8.0,
        sell_percentage=50,   # trim half on the first hit
        trailing=True,
    ),
]
```

### Layered stops (fast + slow)

```python
stop_losses = [
    StopLossRule(
        symbol="BTC", percentage_threshold=3.0,
        sell_percentage=33, trailing=True,
    ),
    StopLossRule(
        symbol="BTC", percentage_threshold=8.0,
        sell_percentage=100, trailing=False,
    ),
]
```

The first rule peels off a third of the position on tight pullbacks; the second is a hard catastrophic stop.

## Resolution Order

`StopLossRule` is evaluated **before** sell signals from `generate_sell_signals()`, so it always wins on the same bar — defensive exits cannot be drowned out by signal noise. See the table in the [Risk Rules Overview](./overview.md#resolution-order).

## Interaction With Other Rules

- **`TradingCost`** — slippage is applied to the stop fill price (`sell` direction).
- **`CooldownRule`** — a stop-out counts as a `sell` event and can therefore restart any cooldown configured with `trigger="sell"` or `trigger="any"`.
- **`ScalingRule`** — when the stop fires, the *entire* `sell_percentage` of the *current* position is liquidated, including everything added via scale-ins.

## See Also

- [`TakeProfitRule`](./take-profit-rule.md)
- [`CooldownRule`](./cooldown-rule.md)
- [Risk Rules Overview](./overview.md)
