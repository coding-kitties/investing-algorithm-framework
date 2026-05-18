---
sidebar_position: 6
---

# CooldownRule

`CooldownRule` is a declarative, side-aware signal-throttling primitive. After a triggering order fills, the rule suppresses certain *new* signals for a configured number of bars — per symbol, or across the whole portfolio.

It is the symmetric, side-aware sibling of [`ScalingRule.cooldown_in_bars`](./scaling-rule.md), which only models a single both-sides, symbol-scoped cooldown that is restarted by *any* order. `CooldownRule` lets you say things like *"after a stop-out on BTC, don't re-enter BTC for 12 bars"* or *"after any order anywhere, throttle the whole portfolio for 2 bars"*.

```python
from investing_algorithm_framework import CooldownRule
```

## Signature

```python
CooldownRule(
    *,
    symbol: str | None = None,
    trigger: str = "any",   # "buy" | "sell" | "any"
    blocks:  str = "any",   # "buy" | "sell" | "any"
    bars:    int = 0,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str \| None` | `None` | Target symbol the rule applies to. `None` makes the rule **portfolio-scoped**: any qualifying order on any symbol restarts it, and any qualifying signal on any symbol is suppressed. |
| `trigger` | `str` | `"any"` | Order side that **starts** the cooldown timer. One of `"buy"`, `"sell"`, `"any"`. |
| `blocks` | `str` | `"any"` | Signal side this cooldown **suppresses**. One of `"buy"`, `"sell"`, `"any"`. |
| `bars` | `int` | `0` | Number of bars the cooldown lasts. `0` is a valid no-op (handy for tests / disabled rules). Must be `>= 0`. |

All arguments are keyword-only. Both `trigger` and `blocks` accept the strings shown above as well as `CooldownTrigger` / `CooldownBlocks` enum members.

## Window Semantics

The bar on which the order fills is treated as bar 0 of the cooldown. A rule with `bars=N` therefore **blocks the next `N` bars** and **allows the `(N+1)`th bar**:

```text
bar  …  fill    +1   +2   +3   +4
                ┃    ┃    ┃    ┃
bars=3:    block block block allow
```

Formally, the rule blocks signals when `bar_index − last_event < bars`.

## Examples

### Re-entry breather

Don't re-buy `BTC` for 12 bars after a sell:

```python
cooldowns = [
    CooldownRule(
        symbol="BTC", trigger="sell", blocks="buy", bars=12,
    ),
]
```

### Both-sides freeze

Freeze all trading on `ETH` for 4 bars after any order:

```python
cooldowns = [
    CooldownRule(
        symbol="ETH", trigger="any", blocks="any", bars=4,
    ),
]
```

### Portfolio-wide throttle

After any order on any symbol, suppress every signal across the portfolio for 2 bars (kills same-bar pile-ups):

```python
cooldowns = [
    CooldownRule(trigger="any", blocks="any", bars=2),
]
```

### Stacking rules

Multiple rules can coexist — the engine evaluates them all and the **most restrictive** active rule wins:

```python
cooldowns = [
    # Symbol-specific re-entry guard.
    CooldownRule(symbol="BTC", trigger="sell", blocks="buy", bars=12),
    # Short global breather after any order.
    CooldownRule(trigger="any", blocks="any", bars=2),
]
```

## Where It's Enforced

Identical semantics in both backtest engines and live trading:

- **Vector backtest engine** — a single `CooldownTracker` is shared across symbols (so portfolio-scoped rules work). Suppressed signals are recorded in `signal_events` with `reason="in_cooldown_rule"` for inspection.
- **Event-driven backtest engine** and **live runtime** — the `TradingStrategy` increments an internal bar counter every `run_strategy()` call, gates buy / sell / scale-out at the relevant phase, and records every fill in the tracker.

## Interaction With Other Rules

- **`ScalingRule.cooldown_in_bars`** — both can coexist. `cooldown_in_bars` remains a fast both-sides per-symbol shortcut; `CooldownRule` is the way to express side- or portfolio-aware throttling. The more restrictive active rule wins.
- **`StopLossRule` / `TakeProfitRule`** — their fills count as `sell` events for cooldown bookkeeping. A typical pattern is `trigger="sell", blocks="buy"` so a stop-out doesn't immediately invite a re-entry on the next bar.
- **Scale-ins and scale-outs** — count as `buy` and `sell` events respectively for cooldown bookkeeping.

## See Also

- [`ScalingRule`](./scaling-rule.md)
- [`StopLossRule`](./stop-loss-rule.md)
- [Risk Rules Overview](./overview.md)
