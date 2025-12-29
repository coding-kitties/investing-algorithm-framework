---
sidebar_position: 6
---

# Positions

Understand how to manage and monitor asset positions in your trading portfolio.

## Overview

Positions represent your holdings of different assets. The framework automatically tracks positions as orders are executed, providing real-time visibility into your portfolio composition and performance.

## Understanding Positions

### What is a Position?

A position represents:
- **Symbol**: The trading pair (e.g., "BTC/USDT")
- **Amount**: Quantity of the asset held
- **Entry Price**: Average price at which the position was acquired
- **Current Value**: Current market value of the position
- **Unrealized P&L**: Profit/loss since opening the position

### Position Lifecycle

1. **Opening**: Position created when you first buy an asset
2. **Scaling**: Position size changes as you buy or sell more
3. **Closing**: Position removed when you sell all holdings

## Accessing Positions

### Get All Positions

```python
def apply_strategy(self, algorithm, market_data):
    # Get all current positions
    positions = algorithm.get_positions()
    
    for position in positions:
        print(f"Position: {position.symbol}")
        print(f"Amount: {position.amount}")
        print(f"Entry Price: {position.entry_price}")
        print(f"Current Value: {position.current_value}")
```

### Get Specific Position

```python
def apply_strategy(self, algorithm, market_data):
    # Get position for specific symbol
    btc_position = algorithm.get_position("BTC/USDT")
    
    if btc_position:
        print(f"BTC Position: {btc_position.amount} BTC")
    else:
        print("No BTC position")
```

### Position Properties

```python
def analyze_position(self, position, market_data):
    # Basic properties
    symbol = position.symbol
    amount = position.amount
    entry_price = position.entry_price
    
    # Current market data
    current_price = market_data.get_last_price(symbol)
    
    # Calculated metrics
    current_value = position.current_value
    unrealized_pnl = current_value - (amount * entry_price)
    pnl_percentage = (unrealized_pnl / (amount * entry_price)) * 100
    
    print(f"Symbol: {symbol}")
    print(f"Amount: {amount}")
    print(f"Entry: ${entry_price:.2f}")
    print(f"Current: ${current_price:.2f}")
    print(f"P&L: ${unrealized_pnl:.2f} ({pnl_percentage:.2f}%)")
```

## Position Management Strategies

### Profit Taking

```python
class ProfitTakingStrategy(TradingStrategy):
    
    def __init__(self, profit_target=0.10):
        super().__init__()
        self.profit_target = profit_target
        
    def apply_strategy(self, algorithm, market_data):
        positions = algorithm.get_positions()
        
        for position in positions:
            current_price = market_data.get_last_price(position.symbol)
            
            # Calculate profit percentage
            profit_pct = (current_price - position.entry_price) / position.entry_price
            
            if profit_pct >= self.profit_target:
                # Take profits - sell 50% of position
                target_symbol = position.symbol.split('/')[0]  # Extract base symbol
                algorithm.create_sell_order(
                    target_symbol=target_symbol,
                    percentage=0.5,
                    order_type="MARKET"
                )
                print(f"Taking profits on {position.symbol}")
```

### Stop Loss Management

```python
class StopLossStrategy(TradingStrategy):
    
    def __init__(self, stop_loss_pct=0.05):
        super().__init__()
        self.stop_loss_pct = stop_loss_pct
        
    def apply_strategy(self, algorithm, market_data):
        positions = algorithm.get_positions()
        
        for position in positions:
            current_price = market_data.get_last_price(position.symbol)
            
            # Calculate loss percentage
            loss_pct = (position.entry_price - current_price) / position.entry_price
            
            if loss_pct >= self.stop_loss_pct:
                # Stop loss triggered - sell entire position
                target_symbol = position.symbol.split('/')[0]
                algorithm.create_sell_order(
                    target_symbol=target_symbol,
                    percentage=1.0,
                    order_type="MARKET"
                )
                print(f"Stop loss triggered for {position.symbol}")
```

### Position Sizing

```python
class PositionSizingStrategy(TradingStrategy):
    
    def __init__(self, max_position_size=0.1):
        super().__init__()
        self.max_position_size = max_position_size
        
    def apply_strategy(self, algorithm, market_data):
        portfolio = algorithm.get_portfolio()
        positions = algorithm.get_positions()
        
        # Check if any position exceeds maximum size
        total_portfolio_value = portfolio.get_total_value()
        
        for position in positions:
            position_weight = position.current_value / total_portfolio_value
            
            if position_weight > self.max_position_size:
                # Position too large - reduce it
                target_weight = self.max_position_size * 0.9  # Reduce to 90% of max
                target_value = total_portfolio_value * target_weight
                excess_value = position.current_value - target_value
                
                # Calculate percentage to sell
                sell_percentage = excess_value / position.current_value
                
                target_symbol = position.symbol.split('/')[0]
                algorithm.create_sell_order(
                    target_symbol=target_symbol,
                    percentage=sell_percentage,
                    order_type="MARKET"
                )
                print(f"Reducing oversized position in {position.symbol}")
```

## Position Analytics

### Portfolio Composition

```python
def analyze_portfolio_composition(self, algorithm):
    positions = algorithm.get_positions()
    portfolio = algorithm.get_portfolio()
    total_value = portfolio.get_total_value()
    
    print("Portfolio Composition:")
    print("-" * 40)
    
    for position in positions:
        weight = (position.current_value / total_value) * 100
        print(f"{position.symbol}: {weight:.2f}%")
        
    # Check for cash position
    cash = portfolio.get_unallocated()
    cash_weight = (cash / total_value) * 100
    print(f"Cash: {cash_weight:.2f}%")
```

### Performance Tracking

```python
def track_position_performance(self, positions, market_data):
    total_unrealized_pnl = 0
    
    print("Position Performance:")
    print("-" * 60)
    
    for position in positions:
        current_price = market_data.get_last_price(position.symbol)
        
        # Calculate metrics
        cost_basis = position.amount * position.entry_price
        current_value = position.amount * current_price
        unrealized_pnl = current_value - cost_basis
        pnl_percentage = (unrealized_pnl / cost_basis) * 100
        
        total_unrealized_pnl += unrealized_pnl
        
        print(f"{position.symbol:10} | "
              f"Amount: {position.amount:8.4f} | "
              f"P&L: ${unrealized_pnl:8.2f} ({pnl_percentage:6.2f}%)")
    
    print("-" * 60)
    print(f"Total Unrealized P&L: ${total_unrealized_pnl:.2f}")
```

## Risk Management

### Position Limits

```python
class PositionLimitStrategy(TradingStrategy):
    
    def __init__(self, max_positions=5):
        super().__init__()
        self.max_positions = max_positions
        
    def apply_strategy(self, algorithm, market_data):
        positions = algorithm.get_positions()
        
        # Check if we can open new positions
        if len(positions) >= self.max_positions:
            print(f"Maximum positions ({self.max_positions}) reached")
            return
            
        # Strategy logic for opening new positions
        self.look_for_entry_signals(algorithm, market_data)
```

### Correlation Management

```python
class CorrelationStrategy(TradingStrategy):
    
    def check_position_correlation(self, algorithm, new_symbol):
        """Check if new position would create too much correlation"""
        positions = algorithm.get_positions()
        
        # Define highly correlated pairs
        correlations = {
            "BTC/USDT": ["ETH/USDT", "LTC/USDT"],
            "ETH/USDT": ["BTC/USDT", "ADA/USDT"],
            # Add more correlations
        }
        
        correlated_symbols = correlations.get(new_symbol, [])
        
        # Check if we already hold correlated assets
        existing_symbols = [pos.symbol for pos in positions]
        
        for existing in existing_symbols:
            if existing in correlated_symbols:
                print(f"Warning: {new_symbol} is correlated with existing position {existing}")
                return False
                
        return True
```

## Advanced Position Features

### Position Averaging

```python
class AveragingStrategy(TradingStrategy):
    
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        position = algorithm.get_position(symbol)
        current_price = market_data.get_last_price(symbol)
        
        if position:
            # Calculate if we should average down
            if current_price < position.entry_price * 0.95:  # 5% below entry
                # Buy more to average down
                algorithm.create_buy_order(
                    target_symbol="BTC",
                    amount=100,
                    order_type="MARKET"
                )
                print(f"Averaging down BTC position")
```

### Position Scaling

```python
class ScalingStrategy(TradingStrategy):
    
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        position = algorithm.get_position(symbol)
        current_price = market_data.get_last_price(symbol)
        
        if position:
            profit_pct = (current_price - position.entry_price) / position.entry_price
            
            # Scale out profits at different levels
            if profit_pct >= 0.20:  # 20% profit
                algorithm.create_sell_order(
                    target_symbol="BTC",
                    percentage=0.25,  # Sell 25%
                    order_type="MARKET"
                )
            elif profit_pct >= 0.10:  # 10% profit
                algorithm.create_sell_order(
                    target_symbol="BTC", 
                    percentage=0.15,  # Sell 15%
                    order_type="MARKET"
                )
```

## Best Practices

### 1. Regular Position Review

```python
def review_positions_daily(self, algorithm, market_data):
    """Daily position review routine"""
    positions = algorithm.get_positions()
    
    for position in positions:
        # Check for stale positions
        if position.days_held > 30:
            print(f"Long-term position: {position.symbol}")
            
        # Check performance
        current_price = market_data.get_last_price(position.symbol)
        pnl_pct = (current_price - position.entry_price) / position.entry_price
        
        if pnl_pct < -0.10:  # More than 10% loss
            print(f"Underperforming position: {position.symbol} ({pnl_pct:.2%})")
```

### 2. Position Documentation

```python
class DocumentedStrategy(TradingStrategy):
    
    def __init__(self):
        super().__init__()
        self.position_notes = {}
        
    def open_position_with_reason(self, algorithm, symbol, amount, reason):
        """Document why we're opening a position"""
        algorithm.create_buy_order(
            target_symbol=symbol,
            amount=amount,
            order_type="MARKET"
        )
        
        self.position_notes[symbol] = {
            'reason': reason,
            'date': datetime.now(),
            'entry_price': market_data.get_last_price(f"{symbol}/USDT")
        }
```

### 3. Position Monitoring

Set up alerts and monitoring for your positions:

```python
def monitor_positions(self, algorithm, market_data):
    """Monitor positions for alerts"""
    positions = algorithm.get_positions()
    
    for position in positions:
        current_price = market_data.get_last_price(position.symbol)
        pnl_pct = (current_price - position.entry_price) / position.entry_price
        
        # Alert conditions
        if pnl_pct > 0.50:  # 50% profit
            print(f"🎉 Big winner! {position.symbol} up {pnl_pct:.1%}")
            
        elif pnl_pct < -0.15:  # 15% loss
            print(f"⚠️  Large loss! {position.symbol} down {pnl_pct:.1%}")
```

## Next Steps

Learn about [Trades](trades) to understand how individual transactions create and modify positions over time.
