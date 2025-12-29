---
sidebar_position: 4
---

# Trading Strategies

Learn how to create and implement trading strategies using the Investing Algorithm Framework.

## Overview

Trading strategies are the core logic that determines when to buy, sell, or hold assets. The framework provides a flexible strategy system that allows you to implement various trading approaches, from simple moving average strategies to complex machine learning models.

## Creating Your First Strategy

### Basic Strategy Structure

```python
from investing_algorithm_framework import TradingStrategy

class MyFirstStrategy(TradingStrategy):
    
    def apply_strategy(self, algorithm, market_data):
        """
        Main strategy logic - called for each time interval
        """
        # Get current price data
        symbol = "BTC/USDT"
        current_price = market_data.get_last_price(symbol)
        
        # Simple buy logic
        if self.should_buy(current_price):
            algorithm.create_buy_order(
                target_symbol="BTC",
                amount=100,  # USDT amount to spend
                order_type="MARKET"
            )
        
        # Simple sell logic  
        elif self.should_sell(current_price):
            algorithm.create_sell_order(
                target_symbol="BTC",
                percentage=1.0,  # Sell 100% of holdings
                order_type="MARKET"
            )
    
    def should_buy(self, current_price):
        # Implement your buy logic
        return False
        
    def should_sell(self, current_price):
        # Implement your sell logic
        return False
```

### Registering Your Strategy

```python
from investing_algorithm_framework import create_app

# Create app and add strategy
app = create_app()
app.add_strategy(MyFirstStrategy())
```

## Strategy Examples

### Moving Average Crossover Strategy

```python
class MovingAverageStrategy(TradingStrategy):
    
    def __init__(self, short_window=20, long_window=50):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        
        # Get historical data
        df = market_data.get_data(symbol, size=self.long_window + 1)
        
        if len(df) < self.long_window:
            return  # Not enough data
            
        # Calculate moving averages
        short_ma = df['close'].rolling(window=self.short_window).mean().iloc[-1]
        long_ma = df['close'].rolling(window=self.long_window).mean().iloc[-1]
        prev_short_ma = df['close'].rolling(window=self.short_window).mean().iloc[-2]
        prev_long_ma = df['close'].rolling(window=self.long_window).mean().iloc[-2]
        
        # Check for crossover
        if (short_ma > long_ma and prev_short_ma <= prev_long_ma):
            # Golden cross - buy signal
            algorithm.create_buy_order(
                target_symbol="BTC",
                amount=100,
                order_type="MARKET"
            )
            
        elif (short_ma < long_ma and prev_short_ma >= prev_long_ma):
            # Death cross - sell signal
            algorithm.create_sell_order(
                target_symbol="BTC", 
                percentage=1.0,
                order_type="MARKET"
            )
```

### RSI Strategy

```python
import pandas as pd

class RSIStrategy(TradingStrategy):
    
    def __init__(self, rsi_period=14, oversold_threshold=30, overbought_threshold=70):
        super().__init__()
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        
    def calculate_rsi(self, prices):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
        
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        
        # Get historical data
        df = market_data.get_data(symbol, size=self.rsi_period + 10)
        
        if len(df) < self.rsi_period + 1:
            return
            
        # Calculate RSI
        rsi = self.calculate_rsi(df['close']).iloc[-1]
        
        # Trading logic
        if rsi < self.oversold_threshold:
            # Oversold - buy signal
            algorithm.create_buy_order(
                target_symbol="BTC",
                amount=100,
                order_type="MARKET"
            )
            
        elif rsi > self.overbought_threshold:
            # Overbought - sell signal
            positions = algorithm.get_positions()
            if any(pos.symbol == "BTC/USDT" for pos in positions):
                algorithm.create_sell_order(
                    target_symbol="BTC",
                    percentage=1.0,
                    order_type="MARKET"
                )
```

## Strategy Features

### State Management

Strategies can maintain state between executions:

```python
class StatefulStrategy(TradingStrategy):
    
    def __init__(self):
        super().__init__()
        self.trade_count = 0
        self.last_price = None
        
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        current_price = market_data.get_last_price(symbol)
        
        # Use state in strategy logic
        if self.last_price and current_price > self.last_price * 1.05:
            # Price increased by 5%
            self.trade_count += 1
            
        self.last_price = current_price
```

### Multiple Timeframes

Strategies can access data from different timeframes:

```python
class MultiTimeframeStrategy(TradingStrategy):
    
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        
        # Get data from different timeframes
        hourly_data = market_data.get_data(symbol, timeframe="1h", size=24)
        daily_data = market_data.get_data(symbol, timeframe="1d", size=30)
        
        # Combine signals from different timeframes
        hourly_trend = self.analyze_trend(hourly_data)
        daily_trend = self.analyze_trend(daily_data)
        
        # Only trade when both timeframes align
        if hourly_trend == "bullish" and daily_trend == "bullish":
            algorithm.create_buy_order(
                target_symbol="BTC",
                amount=100,
                order_type="MARKET"
            )
```

## Strategy Configuration

### Parameters and Settings

```python
class ConfigurableStrategy(TradingStrategy):
    
    def __init__(self, **kwargs):
        super().__init__()
        # Strategy parameters
        self.buy_threshold = kwargs.get('buy_threshold', 0.02)
        self.sell_threshold = kwargs.get('sell_threshold', 0.05)
        self.max_positions = kwargs.get('max_positions', 3)
        
    def apply_strategy(self, algorithm, market_data):
        # Use configurable parameters
        pass

# Create strategy with custom parameters
strategy = ConfigurableStrategy(
    buy_threshold=0.03,
    sell_threshold=0.04,
    max_positions=5
)
```

## Best Practices

### 1. Keep Strategies Simple
Start with simple logic and gradually add complexity.

### 2. Test Thoroughly
Always backtest your strategies before live trading:

```python
# Test strategy with backtesting
results = app.run_backtest(
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)
```

### 3. Handle Edge Cases
Consider market conditions like low volume, extreme volatility, or data gaps.

### 4. Risk Management
Always include proper risk management in your strategies:

```python
def apply_strategy(self, algorithm, market_data):
    # Check portfolio exposure before trading
    portfolio = algorithm.get_portfolio()
    if portfolio.get_total_exposure() > 0.8:
        return  # Skip trading if too much exposure
```

### 5. Logging and Monitoring

```python
import logging

class LoggedStrategy(TradingStrategy):
    
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        current_price = market_data.get_last_price(symbol)
        
        logging.info(f"Strategy executed - {symbol} price: {current_price}")
        
        # Strategy logic...
```

## Next Steps

Now that you understand how to create strategies, learn about [Orders](orders) to understand different order types and execution methods.
