---
sidebar_position: 5
---

# ScalingRule

`ScalingRule` enables **pyramiding** (scaling into winners) and **partial exits** (scaling out) on a per-symbol basis. Without it, every entry is a single full-size buy and every exit is a single full close.

```python
from investing_algorithm_framework import ScalingRule
```

## Signature

```python
ScalingRule(
    symbol: str,
    max_entries: int = 1,
    scale_in_percentage: float | list[float] = 100,
    scale_out_percentage: float | list[float] = 50,
    max_position_percentage: float | None = None,
    cooldown_in_bars: int = 0,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` | — | Target symbol (e.g. `"BTC"`). |
| `max_entries` | `int` | `1` | Maximum total entries including the initial buy. `3` allows the initial entry plus 2 scale-ins. |
| `scale_in_percentage` | `float \| list[float]` | `100` | Size of each scale-in as a percent of the *original* `PositionSize`. Single value applies to all; list assigns per scale-in (last value reused if list is shorter). |
| `scale_out_percentage` | `float \| list[float]` | `50` | Percent of the *current* position to sell on each scale-out signal. Same single-vs-list semantics as `scale_in_percentage`. |
| `max_position_percentage` | `float \| None` | `None` | Hard cap on total position size as percent of portfolio. Scale-ins that would breach the cap are reduced or skipped. |
| `cooldown_in_bars` | `int` | `0` | Bars to wait after **any** buy/sell on this symbol before the next signal is acted on. Both-sides, symbol-scoped. For richer cooldowns use [`CooldownRule`](./cooldown-rule.md). |

## How Signals Map to Actions

When a `ScalingRule` is configured for a symbol, the engine treats incoming signals like this:

| State | Buy signal | Sell signal | Scale-in signal | Scale-out signal |
|---|---|---|---|---|
| No position | Open with full `PositionSize` | (ignored, no position) | (ignored) | (ignored) |
| Has position | Treated as scale-in | Full close, reset entry counter | Add `scale_in_percentage[n]` of original size | Sell `scale_out_percentage[n]` of current position |

The full-sell signal **always** takes priority over a scale-out on the same bar.

## Examples

### Two-stage pyramid

```python
scaling_rules = [
    ScalingRule(
        symbol="BTC",
        max_entries=3,                   # 1 initial + 2 scale-ins
        scale_in_percentage=[50, 25],    # 1st add 50%, 2nd add 25%
    ),
]
```

With `PositionSize(symbol="BTC", percentage_of_portfolio=20)`:

- Initial buy: 20 % of portfolio.
- 1st scale-in: 10 % (50 % of 20 %).
- 2nd scale-in: 5 % (25 % of 20 %).
- Total cap before `max_position_percentage`: 35 %.

### Laddered partial exits

```python
scaling_rules = [
    ScalingRule(
        symbol="ETH",
        scale_out_percentage=[33, 50, 100],
    ),
]
```

- 1st scale-out trims 33 % of the position.
- 2nd scale-out trims 50 % of what's left.
- 3rd scale-out (and any after) closes everything remaining.

### Capped position with cooldown

```python
scaling_rules = [
    ScalingRule(
        symbol="BTC",
        max_entries=5,
        scale_in_percentage=20,
        max_position_percentage=40,   # never exceed 40% of portfolio
        cooldown_in_bars=4,           # don't act on a new signal within 4 bars
    ),
]
```

## Generating Scale Signals

The strategy is responsible for producing scale-in / scale-out signals via:

```python
def generate_scale_in_signals(self, data) -> dict[str, pd.Series]: ...
def generate_scale_out_signals(self, data) -> dict[str, pd.Series]: ...
```

If `generate_scale_in_signals` is not implemented, an extra buy signal on a symbol with an open position is treated as a scale-in (subject to `max_entries`).

## Interaction With Other Rules

- **`PositionSize`** — `scale_in_percentage` is *relative to the original* `PositionSize`, so it does **not** drift as the portfolio grows.
- **`CooldownRule`** — `ScalingRule.cooldown_in_bars` is the legacy, both-sides, symbol-scoped cooldown. For side-aware or portfolio-wide throttling, use [`CooldownRule`](./cooldown-rule.md) — both can coexist; the more restrictive one wins.
- **`StopLossRule` / `TakeProfitRule`** — when they fire, `sell_percentage` is taken from the *full current* position, including all scaled-in lots.
- **`TradingCost`** — fees and slippage apply to every scale-in and scale-out fill.

## See Also

- [`CooldownRule`](./cooldown-rule.md)
- [`PositionSize`](./position-size.md)
- [Risk Rules Overview](./overview.md)
