---
sidebar_position: 2
---

# PositionSize

`PositionSize` declares **how much capital** to allocate to a symbol when an entry signal fires. Each entry sized this way is the baseline that [`ScalingRule`](./scaling-rule.md) `scale_in_percentage` values multiply against.

```python
from investing_algorithm_framework import PositionSize
```

## Signature

```python
PositionSize(
    symbol: str,
    percentage_of_portfolio: float | None = None,
    fixed_amount: float | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` | — | Target symbol (e.g. `"BTC"`). |
| `percentage_of_portfolio` | `float \| None` | `None` | Percent (0–100) of *total portfolio value* (`unallocated + allocated`) to spend per entry. |
| `fixed_amount` | `float \| None` | `None` | Fixed amount in the trading currency to spend per entry. Overrides `percentage_of_portfolio` if both are given. |

Exactly one of `percentage_of_portfolio` or `fixed_amount` must be supplied — otherwise the framework raises `OperationalException`.

## How the size is computed

```text
fixed_amount             → returns fixed_amount
percentage_of_portfolio  → (unallocated + allocated) * pct / 100
```

Because the percentage is taken against *total* portfolio value (not just unallocated cash), the size is stable across the run as the portfolio grows. When several symbols all want capital at once and the request exceeds available funds, the framework **scales every order down by the same ratio** so allocation stays proportional.

## Examples

### Equal-weight portfolio

```python
class EqualWeightStrategy(TradingStrategy):
    symbols = ["BTC", "ETH", "SOL", "ADA", "XRP"]

    position_sizes = [
        PositionSize(symbol=s, percentage_of_portfolio=20.0)
        for s in symbols
    ]
```

### Fixed-amount per asset

```python
class FixedSizeStrategy(TradingStrategy):
    symbols = ["BTC", "ETH"]

    position_sizes = [
        PositionSize(symbol="BTC", fixed_amount=1_000.0),
        PositionSize(symbol="ETH", fixed_amount=500.0),
    ]
```

### Mixed sizing

```python
position_sizes = [
    PositionSize(symbol="BTC", percentage_of_portfolio=30.0),
    PositionSize(symbol="ETH", fixed_amount=750.0),
]
```

## Interaction With Other Rules

- **`ScalingRule`** — `scale_in_percentage` is expressed as a percentage of the *original* `PositionSize`, not of the current position value.
- **`TradingCost`** — `fee_percentage` and `slippage_percentage` are applied on top of the order created from the size; the framework does not pre-deduct fees from the size itself.
- **Proportional scaling** — when concurrent buys exceed available cash, every order is reduced by the same factor so no symbol is starved.

## See Also

- [Risk Rules Overview](./overview.md)
- [`ScalingRule`](./scaling-rule.md)
- [Positions](../Getting%20Started/positions.md)
