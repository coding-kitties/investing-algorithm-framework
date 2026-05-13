---
sidebar_position: 7
---

# TradingCost

`TradingCost` describes the **fees and slippage** that apply when an order fills. It can be attached per symbol on a `TradingStrategy`, or set as a market-level default on the `PortfolioConfiguration`. Both backtest engines apply it to fill prices and trade values; in live mode, the broker reports actual costs.

```python
from investing_algorithm_framework import TradingCost
```

## Signature

```python
TradingCost(
    symbol: str | None = None,
    fee_percentage: float = 0.0,
    slippage_percentage: float = 0.0,
    fee_fixed: float = 0.0,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str \| None` | `None` | Target symbol (e.g. `"BTC"`). `None` means "market default" when used at the portfolio level. Symbol matching is case-insensitive. |
| `fee_percentage` | `float` | `0.0` | Variable fee in **percent of trade value** (e.g. `0.1` = 0.1 %). |
| `slippage_percentage` | `float` | `0.0` | Slippage in **percent of price**. Buys fill higher, sells fill lower. |
| `fee_fixed` | `float` | `0.0` | Flat fee per trade in the trading currency, added on top of `fee_percentage`. |

## How Costs Are Applied

For each fill the engine computes:

```text
buy_fill_price  = price * (1 + slippage_percentage / 100)
sell_fill_price = price * (1 - slippage_percentage / 100)

fee = trade_value * fee_percentage / 100 + fee_fixed
```

`trade_value` is computed at the slippage-adjusted price, so fees compound on top of slippage — matching how real exchanges quote post-trade cost.

## Resolution Order

When the engine needs a `TradingCost` for a symbol it walks this fallback chain:

1. **Strategy-level** — first matching `TradingCost` in `TradingStrategy.trading_costs` whose `symbol` matches.
2. **Portfolio defaults** — `fee_percentage` / `slippage_percentage` on `PortfolioConfiguration` (or `app.add_market(...)`), used when the strategy doesn't override the symbol.
3. **Zero cost** — singleton fallback so every code path always gets a `TradingCost`.

This means market-level defaults set on the portfolio quietly apply to every symbol unless a strategy explicitly overrides them.

## Examples

### Per-symbol fees and slippage

```python
class MyStrategy(TradingStrategy):
    symbols = ["BTC", "ETH"]
    trading_costs = [
        TradingCost(
            symbol="BTC",
            fee_percentage=0.10,
            slippage_percentage=0.05,
        ),
        TradingCost(
            symbol="ETH",
            fee_percentage=0.10,
            slippage_percentage=0.10,   # ETH less liquid here
        ),
    ]
```

### Realistic broker model

```python
trading_costs = [
    TradingCost(
        symbol="BTC",
        fee_percentage=0.06,    # 6 bps maker/taker blend
        fee_fixed=0.50,         # flat per-order ticket
        slippage_percentage=0.02,
    ),
]
```

### Stress-testing a strategy

Bump fees to see how robust your edge is:

```python
trading_costs = [
    TradingCost(symbol="BTC", fee_percentage=0.5),   # 50 bps
    TradingCost(symbol="ETH", fee_percentage=0.5),
]
```

If your strategy still has positive expectancy at 50 bps round-trip, real-world fee variance is unlikely to kill it.

### Market-level defaults

Set defaults once on the portfolio, override per symbol on the strategy:

```python
PortfolioConfiguration(
    market="BITVAVO",
    initial_balance=10_000,
    trading_symbol="EUR",
    fee_percentage=0.10,        # default for every symbol on this market
    slippage_percentage=0.05,
)
```

## Interaction With Other Rules

- **`PositionSize`** — costs are applied to the order produced from the size; the size itself is not pre-deducted.
- **`StopLossRule` / `TakeProfitRule`** — slippage is applied to the exit fill (`sell` direction), so reported PnL already reflects realistic exits.
- **`ScalingRule`** — every scale-in and scale-out is a separate fill and pays fees independently.

## See Also

- [Execution Logic](../Advanced%20Concepts/execution-logic.md)
- [Orders](../Getting%20Started/orders.md)
- [Risk Rules Overview](./overview.md)
