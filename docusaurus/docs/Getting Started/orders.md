---
sidebar_position: 5
---

# Orders

Learn how to create and manage trading orders with the Investing Algorithm Framework.

## Overview

Orders are instructions to buy or sell assets in the market. The framework provides a comprehensive order management system that supports various order types, execution strategies, and order lifecycle management.

## Order Types

### Market Orders

Execute immediately at the current market price:

```python
# Buy order - spend 100 USDT to buy BTC
algorithm.create_buy_order(
    target_symbol="BTC",
    amount=100,  # Amount in trading symbol (USDT)
    order_type="MARKET"
)

# Sell order - sell 50% of BTC holdings  
algorithm.create_sell_order(
    target_symbol="BTC",
    percentage=0.5,  # Sell 50% of holdings
    order_type="MARKET"
)
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

### Common Parameters

- **target_symbol**: The asset to buy/sell (e.g., "BTC", "ETH")
- **amount**: Amount to spend (for buy orders) in trading symbol
- **percentage**: Percentage of holdings to sell (for sell orders)
- **order_type**: Type of order ("MARKET", "LIMIT", "STOP", "STOP_LIMIT")
- **price**: Limit price (for limit and stop-limit orders)
- **stop_price**: Stop price (for stop and stop-limit orders)

### Advanced Parameters

```python
# Order with advanced parameters
algorithm.create_buy_order(
    target_symbol="BTC",
    amount=100,
    order_type="LIMIT",
    price=50000,
    # Advanced parameters
    time_in_force="GTC",  # Good Till Cancelled
    reduce_only=False,    # Allow position increase
    post_only=True       # Only maker orders (some exchanges)
)
```

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
    
    def __init__(self, buy_amount=100):
        super().__init__()
        self.buy_amount = buy_amount
        
    def apply_strategy(self, algorithm, market_data):
        # Buy fixed amount regardless of price
        algorithm.create_buy_order(
            target_symbol="BTC",
            amount=self.buy_amount,
            order_type="MARKET"
        )
```

### Grid Trading

```python
class GridStrategy(TradingStrategy):
    
    def __init__(self, grid_levels=5, grid_spacing=0.02):
        super().__init__()
        self.grid_levels = grid_levels
        self.grid_spacing = grid_spacing
        
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        current_price = market_data.get_last_price(symbol)
        
        # Cancel existing orders
        algorithm.cancel_all_orders(symbol)
        
        # Place buy orders below current price
        for i in range(1, self.grid_levels + 1):
            buy_price = current_price * (1 - self.grid_spacing * i)
            algorithm.create_buy_order(
                target_symbol="BTC",
                amount=100,
                order_type="LIMIT",
                price=buy_price
            )
            
        # Place sell orders above current price  
        positions = algorithm.get_positions()
        btc_position = next((p for p in positions if p.symbol == "BTC/USDT"), None)
        
        if btc_position and btc_position.amount > 0:
            sell_amount_per_level = btc_position.amount / self.grid_levels
            
            for i in range(1, self.grid_levels + 1):
                sell_price = current_price * (1 + self.grid_spacing * i)
                algorithm.create_sell_order(
                    target_symbol="BTC",
                    amount=sell_amount_per_level,
                    order_type="LIMIT", 
                    price=sell_price
                )
```

### Trailing Stop

```python
class TrailingStopStrategy(TradingStrategy):
    
    def __init__(self, trailing_percent=0.05):
        super().__init__()
        self.trailing_percent = trailing_percent
        self.highest_price = None
        
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        current_price = market_data.get_last_price(symbol)
        
        # Update highest price
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price
            
        # Check if we have a position
        positions = algorithm.get_positions()
        btc_position = next((p for p in positions if p.symbol == symbol), None)
        
        if btc_position and btc_position.amount > 0:
            # Calculate trailing stop price
            stop_price = self.highest_price * (1 - self.trailing_percent)
            
            if current_price <= stop_price:
                # Trigger trailing stop
                algorithm.create_sell_order(
                    target_symbol="BTC",
                    percentage=1.0,
                    order_type="MARKET"
                )
                self.highest_price = None  # Reset for next position
```

## Order Validation

The framework includes built-in order validation:

### Balance Checks

```python
# Framework automatically checks if you have sufficient balance
try:
    algorithm.create_buy_order(
        target_symbol="BTC",
        amount=10000,  # This might exceed available balance
        order_type="MARKET"
    )
except InsufficientBalanceError as e:
    print(f"Order failed: {e}")
```

### Position Checks

```python
# Framework checks if you have enough holdings to sell
try:
    algorithm.create_sell_order(
        target_symbol="BTC", 
        percentage=1.5,  # Cannot sell more than 100%
        order_type="MARKET"
    )
except InsufficientHoldingsError as e:
    print(f"Order failed: {e}")
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
