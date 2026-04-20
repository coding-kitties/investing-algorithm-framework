---
sidebar_position: 5
---

# Orders

Learn how to create and manage trading orders with the Investing Algorithm Framework.

## Overview

Orders are instructions to buy or sell assets in the market. The framework provides a comprehensive order management system that supports various order types, execution strategies, and order lifecycle management.

## Order Types

### Market Orders

Execute at the best available price. The framework looks up the current price as an **estimated price** for sizing and cash reservation. The actual fill price is determined at execution time and the portfolio is automatically reconciled.

**Using the general method:**

```python
from investing_algorithm_framework import OrderSide

# Buy order - spend 100 EUR worth of BTC at market price
self.create_market_order(
    target_symbol="BTC",
    order_side=OrderSide.BUY,
    amount_trading_symbol=100,  # Amount in trading symbol (EUR)
)

# Sell order - sell 50% of BTC position at market price
self.create_market_order(
    target_symbol="BTC",
    order_side=OrderSide.SELL,
    percentage_of_position=50,  # Sell 50% of position
)
```

**Using convenience methods:**

```python
# Buy: spend 10% of portfolio on BTC
self.create_market_buy_order(
    target_symbol="BTC",
    percentage_of_portfolio=10,
)

# Sell: sell 0.5 BTC
self.create_market_sell_order(
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
from investing_algorithm_framework import TradingCost

class MyStrategy(TradingStrategy):
    trading_costs = [
        TradingCost(symbol="BTC", slippage_percentage=0.001),  # 0.1% slippage
    ]
```

### Limit Orders

Execute only at a specified price or better:

```python
# Buy limit order
algorithm.create_buy_order(
    target_symbol="BTC",
    amount=100,
    order_type="LIMIT",
    price=50000  # Only buy if BTC price is 50,000 USDT or lower
)

# Sell limit order
algorithm.create_sell_order(
    target_symbol="BTC",
    percentage=1.0,
    order_type="LIMIT",
    price=55000  # Only sell if BTC price is 55,000 USDT or higher
)
```

### Stop Orders

Trigger market orders when price reaches a specified level:

```python
# Stop loss - sell if price drops to 45,000
algorithm.create_sell_order(
    target_symbol="BTC",
    percentage=1.0,
    order_type="STOP",
    stop_price=45000
)

# Buy stop - buy if price rises to 52,000 (breakout strategy)
algorithm.create_buy_order(
    target_symbol="BTC",
    amount=100,
    order_type="STOP",
    stop_price=52000
)
```

### Stop-Limit Orders

Combine stop and limit order features:

```python
# Stop-limit sell order
algorithm.create_sell_order(
    target_symbol="BTC",
    percentage=1.0,
    order_type="STOP_LIMIT",
    stop_price=45000,  # Trigger when price hits 45,000
    price=44500        # But only sell at 44,500 or better
)
```

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
def apply_strategy(self, algorithm, market_data):
    # Get all orders
    orders = algorithm.get_orders()

    # Filter by status
    pending_orders = [order for order in orders if order.status == "OPEN"]
    filled_orders = [order for order in orders if order.status == "FILLED"]

    # Check specific order
    for order in pending_orders:
        print(f"Order {order.id}: {order.order_type} {order.target_symbol} - {order.status}")
```

### Canceling Orders

```python
def apply_strategy(self, algorithm, market_data):
    # Cancel specific order
    orders = algorithm.get_orders()
    for order in orders:
        if order.status == "OPEN" and order.created_at < some_time_threshold:
            algorithm.cancel_order(order.id)

    # Cancel all open orders for a symbol
    algorithm.cancel_all_orders(symbol="BTC/USDT")
```

### Modifying Orders

```python
def apply_strategy(self, algorithm, market_data):
    orders = algorithm.get_orders()

    for order in orders:
        if order.status == "OPEN" and order.order_type == "LIMIT":
            # Update order price
            algorithm.update_order(
                order_id=order.id,
                price=new_price,
                amount=new_amount
            )
```

## Order Execution Examples

### Dollar-Cost Averaging

```python
class DCAStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["BTC"]
    trading_symbol = "EUR"

    def apply_strategy(self, context, data):
        # Buy fixed amount regardless of price
        self.create_market_buy_order(
            target_symbol="BTC",
            amount_trading_symbol=100,  # Buy 100 EUR worth of BTC
        )
```

### Grid Trading

```python
class GridStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]
    trading_symbol = "EUR"

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
    trading_symbol = "EUR"

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
                self.create_market_sell_order(
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
self.create_market_buy_order(
    target_symbol="BTC",
    amount_trading_symbol=10000,  # This might exceed available balance
)
```

### Position Checks

For **sell orders**, the framework checks that you have enough holdings:

```python
# Framework checks if you have enough holdings to sell
# This will raise an OperationalException if position is insufficient
self.create_market_sell_order(
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
def check_order_health(self, algorithm):
    orders = algorithm.get_orders()

    # Check for old unfilled orders
    current_time = datetime.now()
    for order in orders:
        if order.status == "OPEN":
            age = current_time - order.created_at
            if age.total_seconds() > 3600:  # 1 hour
                print(f"Warning: Order {order.id} has been open for {age}")
```

### 3. Handle Partial Fills

```python
def handle_partial_fills(self, algorithm):
    orders = algorithm.get_orders()

    for order in orders:
        if order.status == "PARTIALLY_FILLED":
            fill_ratio = order.filled_amount / order.amount
            print(f"Order {order.id} is {fill_ratio:.1%} filled")

            # Decide whether to cancel or wait
            if fill_ratio < 0.1:  # Less than 10% filled
                algorithm.cancel_order(order.id)
```

### 4. Risk Management

Always include risk controls in your order logic:

```python
def apply_strategy(self, algorithm, market_data):
    # Check portfolio exposure before placing orders
    portfolio = algorithm.get_portfolio()

    if portfolio.get_total_exposure() < 0.9:  # Less than 90% invested
        # Safe to place buy orders
        algorithm.create_buy_order(
            target_symbol="BTC",
            amount=100,
            order_type="MARKET"
        )
```

## Next Steps

Learn about [Positions](positions) to understand how orders create and modify your asset holdings.
