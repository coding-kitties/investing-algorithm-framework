---
sidebar_position: 5
---

# Orders

Learn how to create and manage trading orders with the Investing Algorithm Framework.

## Overview

Orders are instructions to open or close long and short positions. The framework
supports buy, sell, short, and cover sides across market, limit, stop, and
stop-limit order types.

## Order Types

### Market Orders

Execute at the best available price. The framework looks up the current price as an **estimated price** for sizing and cash reservation. The actual fill price is determined at execution time and the portfolio is automatically reconciled.

**Using the general method:**

```python
from investing_algorithm_framework import OrderSide

# Buy order - spend 100 EUR worth of BTC at market price
context.create_market_order(
    target_symbol="BTC",
    order_side=OrderSide.BUY,
    amount_trading_symbol=100,  # Amount in trading symbol (EUR)
)

# Sell order - sell 50% of BTC position at market price
context.create_market_order(
    target_symbol="BTC",
    order_side=OrderSide.SELL,
    percentage_of_position=50,  # Sell 50% of position
)
```

**Using convenience methods:**

```python
# Buy: spend 10% of portfolio on BTC
context.create_market_buy_order(
    target_symbol="BTC",
    percentage_of_portfolio=10,
)

# Sell: sell 0.5 BTC
context.create_market_sell_order(
    target_symbol="BTC",
    amount=0.5,
)
```

:::info How market orders work internally
1. The framework fetches the **latest price** as an estimated price.
2. The order is created with `price=estimated_price` for cash reservation and position sizing.
3. At fill time (next candle open in backtesting, exchange fill in live trading), the **actual fill price** replaces the estimate.
4. The portfolio is **reconciled**: any difference between the estimated and actual price is adjusted in your unallocated balance and position.
:::

#### Backtesting Behavior

In backtesting, market orders fill at the **Open price of the next candle** after the order is placed. If you have configured `TradingCost` with a `slippage_percentage`, slippage is applied on top of the open price:

```python
from investing_algorithm_framework import TradingCost, ExecutionConfig

study = Study(
    ...,
    execution_config=ExecutionConfig(
        trading_costs=[
            TradingCost(symbol="BTC", slippage_percentage=0.001),  # 0.1% slippage
        ],
    ),
)
```

### Limit Orders

Execute only at a specified price or better:

```python
from investing_algorithm_framework import OrderSide

# Buy limit order
context.create_limit_order(
    target_symbol="BTC",
    order_side=OrderSide.BUY,
    amount=0.01,
    price=50000,  # Only buy if BTC is 50,000 EUR or lower
)

# Sell limit order
context.create_limit_order(
    target_symbol="BTC",
    order_side=OrderSide.SELL,
    percentage_of_position=100,
    price=55000,  # Only sell if BTC is 55,000 EUR or higher
)
```

### Short and Cover Orders

Use a **short** order to open a position that benefits when the asset price
falls. Use a **cover** order to close all or part of that short position.

```python
from investing_algorithm_framework import OrderType

# Open a limit short using 10% of portfolio net size as collateral
context.create_short_order(
    target_symbol="BTC",
    price=50000,
    percentage_of_portfolio=10,
)

# Cover half of the open short with a limit order
context.create_cover_order(
    target_symbol="BTC",
    price=45000,
    percentage_of_position=50,
)

# Market short: price is the sizing and reservation reference
context.create_short_order(
    target_symbol="ETH",
    price=context.get_latest_price("ETH/EUR"),
    amount=0.5,
    order_type=OrderType.MARKET,
)
```

Short positions are fully collateralized; the framework does not apply
leverage. Pass either `amount` or `percentage_of_portfolio` when opening a
short, and either `amount` or `percentage_of_position` when covering one.
Market short and cover orders follow the same next-candle-open behavior as
other market orders in event-driven backtests.

### Stop Orders

A **stop order** rests in the book until the market trades through a configured `stop_price`. Once triggered, it becomes a market order and fills at the next available price.

- **SELL stop** triggers when the market drops to (or below) `stop_price` — used for stop-losses or trend-following exits.
- **BUY stop** triggers when the market rises to (or above) `stop_price` — used for breakout entries.

```python
from investing_algorithm_framework import OrderType, OrderSide

# SELL stop — exit if BTC drops to 45,000 EUR
context.create_order(
    target_symbol="BTC",
    order_side=OrderSide.SELL,
    amount=0.5,
    order_type=OrderType.STOP,
    stop_price=45000,
)

# BUY stop — enter on a breakout above 52,000 EUR
context.create_order(
    target_symbol="BTC",
    order_side=OrderSide.BUY,
    amount=0.1,
    order_type=OrderType.STOP,
    stop_price=52000,
    price=52000,  # used as the cash-reservation reference
)
```

### Stop-Limit Orders

A **stop-limit order** triggers like a stop, but instead of becoming a market order, it becomes a **limit order** at the configured `price`. This protects against bad fills during gaps but does not guarantee execution.

```python
# SELL stop-limit — trigger at 45,000, but only sell at 44,500 or better
context.create_order(
    target_symbol="BTC",
    order_side=OrderSide.SELL,
    amount=0.5,
    order_type=OrderType.STOP_LIMIT,
    stop_price=45000,   # trigger price
    price=44500,        # limit price after trigger
)
```

**Validation rules**

- `stop_price` is required for both `STOP` and `STOP_LIMIT` orders.
- For `STOP_LIMIT`, `price` is also required and must be:
  - `price <= stop_price` for SELL stop-limit orders
  - `price >= stop_price` for BUY stop-limit orders

:::note Where stop orders are evaluated
Stop and stop-limit orders are simulated in **event-driven backtests** and executed by supported exchanges in **live trading** (via the unified CCXT `stopPrice` parameter).

They are **not** evaluated in **vector backtests**. Vector backtesting models strategy *signals* only — it does not simulate the order book, intra-bar price paths, or stop triggers. Use vector backtests to filter parameter sets quickly, then promote promising strategies to event-driven backtests where stops, slippage, commissions, and partial fills are evaluated. See [Vector Backtesting](../Advanced%20Concepts/vector-backtesting) for the trade-offs.
:::

#### Backtest Trigger Semantics

In an event-driven backtest, the trigger condition is evaluated against each candle's High / Low after the order's `updated_at`:

| Order side | Triggers when |
|------------|---------------|
| SELL STOP / STOP_LIMIT | `Low <= stop_price` |
| BUY STOP / STOP_LIMIT | `High >= stop_price` |

- A **STOP** that triggers fills at `stop_price` on the triggering candle (then slippage and commission from the configured blotter / `TradingCost` are applied via the same fill path used for market orders).
- A **STOP_LIMIT** that triggers becomes a resting limit order at `price` from the triggering candle onwards, and fills under the normal limit-fill rules (`Low <= price` for BUY, `High >= price` for SELL).
- The triggering timestamp is stored on the order as `triggered_at` for auditability.

## Convenience Helpers

For common sizing patterns the framework exposes five high-level helpers on `Context` (also available as `self.*` from a `TradingStrategy`). They all produce **LIMIT** orders and require an explicit `price`, delegating internally to `create_limit_order`. The `order_target*` family looks up the current position and submits a BUY or SELL for the difference (no order is placed when the position already matches the target).

| Helper | Computes | Use case |
|--------|----------|----------|
| `order_value(symbol, value, side, price)` | `amount = value / price` | Fixed currency-amount orders (e.g. DCA) |
| `order_percent(symbol, percent, side, price)` | `(net_size * percent / 100) / price` | Allocate a % of portfolio net size |
| `order_target(symbol, target_amount, price)` | `target_amount - current_amount` | Reach an exact position size in units |
| `order_target_value(symbol, target_value, price)` | `(target_value / price) - current_amount` | Reach an exact position value |
| `order_target_percent(symbol, target_percent, price)` | `((net_size * target_percent / 100) / price) - current_amount` | Portfolio rebalancing |

```python
from investing_algorithm_framework import OrderSide, TradingStrategy

class RebalanceStrategy(TradingStrategy):

    def apply_strategy(self, context, data):
        price = data["BTC/EUR"]["close"].iloc[-1]

        # Spend exactly 500 EUR on BTC
        context.order_value(
            target_symbol="BTC",
            value=500,
            order_side=OrderSide.BUY,
            price=price,
        )

        # Allocate 25% of portfolio to ETH
        context.order_percent(
            target_symbol="ETH",
            percent=25,
            order_side=OrderSide.BUY,
            price=data["ETH/EUR"]["close"].iloc[-1],
        )

        # End up holding exactly 1.5 BTC (buys or sells the difference)
        context.order_target(
            target_symbol="BTC",
            target_amount=1.5,
            price=price,
        )

        # Rebalance BTC to 10% of portfolio
        context.order_target_percent(
            target_symbol="BTC",
            target_percent=10,
            price=price,
        )
```

**Validation**

- `value`, `percent`, `price` must be positive.
- `target_amount`, `target_value`, `target_percent` must be non-negative.
- `order_target*` returns `None` (no order placed) when the current position already matches the target.

All helpers accept the same optional `market`, `precision` and `metadata` parameters as `create_limit_order`.

:::tip MARKET variant & auto-price
The helpers currently require an explicit `price` and always produce LIMIT orders. A future enhancement (tracked as a follow-up to #440) will add `order_type=OrderType.MARKET` support and fall back to `context.get_latest_price()` when `price` is omitted.
:::

## Order Parameters

### Market Order Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `target_symbol` | `str` | The asset to trade (e.g., `"BTC"`, `"ETH"`) |
| `order_side` | `OrderSide` | `OrderSide.BUY` or `OrderSide.SELL` |
| `amount` | `float` | Amount of the target asset |
| `amount_trading_symbol` | `float` | Amount in trading symbol (e.g., EUR) to spend |
| `percentage_of_portfolio` | `float` | % of portfolio to buy (BUY only) |
| `percentage_of_position` | `float` | % of position to sell (SELL only) |
| `percentage` | `float` | % of portfolio net size to allocate |
| `precision` | `int` | Decimal precision for rounding the amount |

### Short and Cover Parameters

| Parameter | Short order | Cover order |
|-----------|-------------|-------------|
| `target_symbol` | Asset to short | Asset whose short position is closed |
| `price` | Limit price or market-order reference price | Limit price or market-order reference price |
| `amount` | Units to short | Units to cover |
| `percentage_of_portfolio` | Percentage of net size used as collateral | Not supported |
| `percentage_of_position` | Not supported | Percentage of the open short to cover |
| `order_type` | `LIMIT` by default; also supports `MARKET` | `LIMIT` by default; also supports `MARKET` |
| `metadata` | `dict` | Additional metadata for the order |

### Limit Order Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `target_symbol` | `str` | The asset to trade (e.g., `"BTC"`, `"ETH"`) |
| `order_side` | `OrderSide` | `OrderSide.BUY` or `OrderSide.SELL` |
| `price` | `float` | Limit price for the order |
| `amount` | `float` | Amount of the target asset |
| `amount_trading_symbol` | `float` | Amount in trading symbol to spend |
| `percentage_of_portfolio` | `float` | % of portfolio to buy (BUY only) |
| `percentage_of_position` | `float` | % of position to sell (SELL only) |
| `percentage` | `float` | % of portfolio net size to allocate |
| `precision` | `int` | Decimal precision for rounding the amount |

### Common Parameters

All order creation methods support these additional parameters:

- **execute** (default `True`): Whether to execute the order immediately
- **validate** (default `True`): Whether to validate the order (balance/position checks)
- **sync** (default `True`): Whether to sync the order with the portfolio

## Order Management

### Checking Order Status

```python
from investing_algorithm_framework import OrderSide, OrderStatus

def apply_strategy(self, context, data):
    pending_orders = context.get_orders(status=OrderStatus.OPEN.value)
    short_orders = context.get_orders(order_side=OrderSide.SHORT.value)

    for order in pending_orders:
        print(f"Order {order.id}: {order.order_type} {order.target_symbol} - {order.status}")
```

`context.get_orders()` can also filter by `target_symbol`, `order_type`,
`order_side`, and `market`. The current strategy API does not expose public
order cancellation or in-place modification helpers. Submit a replacement
order when your strategy needs different order parameters.

## Order Execution Examples

### Dollar-Cost Averaging

```python
class DCAStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["BTC"]

    def apply_strategy(self, context, data):
        # Buy fixed amount regardless of price
        context.create_market_order(
            target_symbol="BTC",
            order_side=OrderSide.BUY,
            amount_trading_symbol=100,  # Buy 100 EUR worth of BTC
        )
```

### Grid Trading

```python
class GridStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]

    def __init__(self, grid_levels=5, grid_spacing=0.02, **kwargs):
        super().__init__(**kwargs)
        self.grid_levels = grid_levels
        self.grid_spacing = grid_spacing

    def apply_strategy(self, context, data):
        current_price = context.get_latest_price("BTC/EUR")

        # Place buy limit orders below current price
        for i in range(1, self.grid_levels + 1):
            buy_price = current_price * (1 - self.grid_spacing * i)
            self.create_limit_order(
                target_symbol="BTC",
                order_side=OrderSide.BUY,
                amount_trading_symbol=100,
                price=buy_price,
            )

        # Place sell limit orders above current price
        position = self.get_position(symbol="BTC")

        if position and position.get_amount() > 0:
            sell_amount = position.get_amount() / self.grid_levels

            for i in range(1, self.grid_levels + 1):
                sell_price = current_price * (1 + self.grid_spacing * i)
                self.create_limit_order(
                    target_symbol="BTC",
                    order_side=OrderSide.SELL,
                    amount=sell_amount,
                    price=sell_price,
                )
```

### Trailing Stop

```python
class TrailingStopStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]

    def __init__(self, trailing_percent=0.05, **kwargs):
        super().__init__(**kwargs)
        self.trailing_percent = trailing_percent
        self.highest_price = None

    def apply_strategy(self, context, data):
        current_price = context.get_latest_price("BTC/EUR")

        # Update highest price
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price

        # Check if we have a position
        if self.has_position(symbol="BTC", amount_gt=0):
            # Calculate trailing stop price
            stop_price = self.highest_price * (1 - self.trailing_percent)

            if current_price <= stop_price:
                # Trigger trailing stop - sell entire position at market
                context.create_market_sell_order(
                    target_symbol="BTC",
                    percentage_of_position=100,
                )
                self.highest_price = None  # Reset for next position
```

## Order Validation

The framework includes built-in order validation for both limit and market orders:

### Balance Checks

For **buy orders**, the framework validates that you have sufficient unallocated balance. For market orders, this check uses the estimated price:

```python
# Framework automatically checks if you have sufficient balance
# This will raise an OperationalException if balance is insufficient
context.create_market_buy_order(
    target_symbol="BTC",
    amount_trading_symbol=10000,  # This might exceed available balance
)
```

### Position Checks

For **sell orders**, the framework checks that you have enough holdings:

```python
# Framework checks if you have enough holdings to sell
# This will raise an OperationalException if position is insufficient
context.create_market_sell_order(
    target_symbol="BTC",
    percentage_of_position=150,  # Cannot sell more than 100%
)
```

## Best Practices

### 1. Use Appropriate Order Types

- **Market orders**: For immediate execution when timing is critical
- **Limit orders**: For better price control and reduced slippage
- **Stop orders**: For risk management and breakout strategies

### 2. Monitor Order Status

Always check if your orders are being filled as expected:

```python
from datetime import datetime, timezone
from investing_algorithm_framework import OrderStatus

def check_order_health(context):
    orders = context.get_orders(status=OrderStatus.OPEN.value)

    # Check for old unfilled orders
    current_time = datetime.now(tz=timezone.utc)
    for order in orders:
        age = current_time - order.created_at
        if age.total_seconds() > 3600:  # 1 hour
            print(f"Warning: Order {order.id} has been open for {age}")
```

### 3. Handle Partial Fills

```python
def report_fill_progress(context):
    orders = context.get_orders()

    for order in orders:
        if order.filled and order.remaining:
            fill_ratio = order.filled / order.amount
            print(f"Order {order.id} is {fill_ratio:.1%} filled")
```

### 4. Risk Management

Always include risk controls in your order logic:

```python
from investing_algorithm_framework import OrderSide

def apply_strategy(self, context, data):
    portfolio = context.get_portfolio()
    allocation = 1 - (portfolio.get_unallocated() / portfolio.get_net_size())

    if allocation < 0.9:  # Less than 90% allocated
        context.create_market_order(
            target_symbol="BTC",
            order_side=OrderSide.BUY,
            amount_trading_symbol=100,
        )
```

## Next Steps

Learn about [Positions](positions) to understand how orders create and modify your asset holdings.
