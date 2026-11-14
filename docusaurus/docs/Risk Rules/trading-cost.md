---
sidebar_position: 7
---

# TradingCost

`TradingCost` describes the **fees and slippage** that apply when an order fills. Per-symbol overrides are configured on `PortfolioConfiguration.trading_costs` (live/paper trading, via `app.add_market(trading_costs=[...])`) or on `Study.execution_config` (backtests, via `ExecutionConfig(trading_costs=[...])`). Market-wide defaults (one flat fee/slippage pair for every symbol) are set directly on `PortfolioConfiguration` via `fee_percentage`/`slippage_percentage`. Both backtest engines apply costs to fill prices and trade values; in live mode, the broker reports actual costs (paper trading falls back to the exchange's real, publicly advertised taker fee when no cost is configured).

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
    slippage_model: SlippageModel | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str \| None` | `None` | Target symbol (e.g. `"BTC"`). `None` means "applies to any symbol without its own entry" when placed in `PortfolioConfiguration.trading_costs`/`ExecutionConfig.trading_costs`. Symbol matching is case-insensitive. |
| `fee_percentage` | `float` | `0.0` | Variable fee in **percent of trade value** (e.g. `0.1` = 0.1 %). |
| `slippage_percentage` | `float` | `0.0` | Slippage in **percent of price**. Buys fill higher, sells fill lower. Ignored when `slippage_model` is set. |
| `fee_fixed` | `float` | `0.0` | Flat fee per trade in the trading currency, added on top of `fee_percentage`. |
| `slippage_model` | `SlippageModel \| None` | `None` | Pluggable slippage model. When set, **overrides** `slippage_percentage`. See [Slippage Models](#slippage-models) below. |

## How Costs Are Applied

For each fill the engine computes:

```text
buy_fill_price  = price * (1 + slippage_percentage / 100)
sell_fill_price = price * (1 - slippage_percentage / 100)

fee = trade_value * fee_percentage / 100 + fee_fixed
```

When a `slippage_model` is set, the model's `calculate_slippage()` method replaces the percentage formula above. The fee calculation stays the same.

`trade_value` is computed at the slippage-adjusted price, so fees compound on top of slippage — matching how real exchanges quote post-trade cost.

## Resolution Order

When the engine needs a `TradingCost` for a symbol it walks this fallback chain:

1. **Symbol-specific override** — first matching `TradingCost` in `PortfolioConfiguration.trading_costs` (live/paper) or `Study.execution_config.trading_costs` (backtests) whose `symbol` matches.
2. **Configured default** — a `TradingCost(symbol=None, ...)` entry in that same list, if any.
3. **Portfolio defaults** — `fee_percentage` / `slippage_percentage` on `PortfolioConfiguration` (or `app.add_market(...)`).
4. **Zero cost** — singleton fallback so every code path always gets a `TradingCost`. In paper trading, this step instead resolves the exchange's real, publicly advertised taker fee via ccxt before falling back to zero.

This means market-level defaults set on the portfolio quietly apply to every symbol unless a more specific `TradingCost` entry overrides them.

## Examples

### Per-symbol fees and slippage (live / paper trading)

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    trading_costs=[
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
    ],
)
```

### Per-symbol fees and slippage (backtests)

```python
from investing_algorithm_framework import ExecutionConfig, Study

study = Study(
    universe=Universe(market="BITVAVO", trading_symbol="EUR"),
    backtest_windows=[...],
    execution_config=ExecutionConfig(
        trading_costs=[
            TradingCost(
                symbol="BTC", fee_percentage=0.10,
                slippage_percentage=0.05,
            ),
            TradingCost(
                symbol="ETH", fee_percentage=0.10,
                slippage_percentage=0.10,
            ),
        ],
    ),
)
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

Bump fees to see how robust your edge is — pass a higher-fee list via `ExecutionConfig(trading_costs=[...])` on a second `Study` and compare:

```python
trading_costs = [
    TradingCost(symbol="BTC", fee_percentage=0.5),   # 50 bps
    TradingCost(symbol="ETH", fee_percentage=0.5),
]
```

If your strategy still has positive expectancy at 50 bps round-trip, real-world fee variance is unlikely to kill it.

### Market-level defaults

Set defaults once on the portfolio, override per symbol via `trading_costs=`:

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

## Slippage Models

The `slippage_model` parameter lets you plug in sophisticated slippage behavior that goes beyond a flat percentage. When set, it **overrides** the `slippage_percentage` field.

```python
from investing_algorithm_framework import (
    TradingCost,
    VolumeShareSlippage,
    FixedSlippage,
    FixedBasisPointsSlippage,
)
```

### VolumeShareSlippage

Models slippage as a function of the order's share of bar volume with a **quadratic** price impact. Also enforces a volume limit — at most `volume_limit` fraction of a bar's volume can be filled per bar. Orders exceeding this limit are partially filled and re-evaluated on subsequent bars.

```python
TradingCost(
    symbol="BTC",
    fee_percentage=0.1,
    slippage_model=VolumeShareSlippage(
        volume_limit=0.025,    # max 2.5% of bar volume
        price_impact=0.1,      # price impact coefficient
    ),
)
```

| Parameter | Default | Description |
|---|---|---|
| `volume_limit` | `0.025` | Max fraction of bar volume that can fill per bar (0.025 = 2.5 %). |
| `price_impact` | `0.1` | Coefficient for quadratic impact: `impact = price_impact × (amount / volume)²`. |

**Impact formula:**

```text
participation = amount / volume
impact        = price_impact * participation²

buy_fill_price  = price * (1 + impact)
sell_fill_price = price * (1 - impact)
```

This is the most realistic built-in model — strategies that trade illiquid assets or large positions relative to volume will see significant market impact, and orders larger than the volume limit will be partially filled.

### FixedSlippage

Adds or subtracts a fixed amount from the order price. Useful for markets with a known, relatively stable spread.

```python
TradingCost(
    symbol="ETH",
    fee_percentage=0.1,
    slippage_model=FixedSlippage(amount=0.50),  # fixed $0.50 spread
)
```

| Parameter | Default | Description |
|---|---|---|
| `amount` | `0.01` | Fixed slippage in price units. |

### FixedBasisPointsSlippage

Slippage expressed in basis points (1 bp = 0.01 % of price). Convenient when you want a proportional slippage without thinking in decimals.

```python
TradingCost(
    symbol="BTC",
    fee_percentage=0.1,
    slippage_model=FixedBasisPointsSlippage(basis_points=5),  # 5 bps = 0.05%
)
```

| Parameter | Default | Description |
|---|---|---|
| `basis_points` | `5` | Slippage in basis points. |

### Custom Slippage Model

Create your own by extending `SlippageModel`:

```python
from investing_algorithm_framework import SlippageModel

class MySlippageModel(SlippageModel):
    def __init__(self, price_impact=0.1, volume_limit=0.025):
        self.price_impact = price_impact
        self.volume_limit = volume_limit

    def calculate_slippage(self, price, order_side, amount=None, volume=None):
        """Return adjusted fill price."""
        if amount and volume and volume > 0:
            impact = self.price_impact * (amount / volume) ** 2
        else:
            impact = 0.0

        if order_side == "BUY":
            return price * (1 + impact)
        return price * (1 - impact)

    def max_fill_amount(self, order_amount, volume=None):
        """Return maximum fillable amount for this bar."""
        if volume and volume > 0:
            return min(order_amount, volume * self.volume_limit)
        return order_amount
```

The two methods you can override:

| Method | Required | Description |
|---|---|---|
| `calculate_slippage(price, order_side, amount, volume)` | Yes | Return the adjusted fill price after slippage. |
| `max_fill_amount(order_amount, volume)` | No | Return the maximum fillable amount per bar. Default returns the full `order_amount` (no volume limit). |

### Choosing a Slippage Approach

| Approach | When to use |
|---|---|
| `slippage_percentage` | Quick approximation, don't need volume awareness. |
| `FixedSlippage` | Known fixed spread (e.g. a specific venue). |
| `FixedBasisPointsSlippage` | Proportional slippage in familiar units (basis points). |
| `VolumeShareSlippage` | Realistic simulation — large orders impact price, fills are volume-limited. |
| Custom `SlippageModel` | Any other behavior (e.g. time-of-day effects, asymmetric slippage). |

:::tip Backward Compatibility
Setting `slippage_model` is fully optional. Existing strategies using `slippage_percentage` continue to work unchanged.
:::

## See Also

- [Execution Logic](../Advanced%20Concepts/execution-logic.md)
- [Blotter](../Advanced%20Concepts/blotter.md)
- [Orders](../Getting%20Started/orders.md)
- [Risk Rules Overview](./overview.md)
