---
sidebar_position: 4
---

# Trading Strategies

Learn how to create and implement trading strategies using the Investing Algorithm Framework.

## Overview

Trading strategies are the core logic that determines when to buy, sell, or hold assets. The framework provides a flexible `TradingStrategy` class that allows you to implement various trading approaches using signal-based trading with built-in support for position sizing, stop losses, and take profits.

## TradingStrategy Attributes

The `TradingStrategy` class has the following key attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `algorithm_id` | `str` | Unique identifier for your combined strategy instances. Used for backtesting results, logging, and monitoring. |
| `strategy_id` | `str` | Optional identifier for the strategy. Defaults to the class name. |
| `time_unit` | `TimeUnit` | The time unit that defines when the strategy should run (e.g., `HOUR`, `DAY`, `WEEK`, `MONTH`). **Required**. |
| `interval` | `int` | How often the strategy runs within the time unit (e.g., every 5 hours). **Required**. |
| `symbols` | `List[str]` | List of symbols to trade (e.g., `["BTC", "ETH"]`). |
| `trading_symbol` | `str` | The quote currency for trading (e.g., `"EUR"`, `"USDT"`). |
| `data_sources` | `List[DataSource]` | Data sources that provide market data to the strategy. |
| `position_sizes` | `List[PositionSize]` | Position sizing rules for each symbol. |
| `stop_losses` | `List[StopLossRule]` | Stop loss rules for each symbol. |
| `take_profits` | `List[TakeProfitRule]` | Take profit rules for each symbol. |
| `metadata` | `Dict[str, Any]` | Dictionary for storing additional strategy information (author, version, params, etc.). |

## Creating Your First Strategy

### Basic Strategy Structure

There are two main approaches to creating strategies:

#### Approach 1: Signal-Based Strategy (Recommended)

Implement `generate_buy_signals` and `generate_sell_signals` methods that return pandas Series with boolean signals:

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, DataSource, PositionSize
import pandas as pd

class MySignalStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC", "ETH"]
    trading_symbol = "EUR"
    
    data_sources = [
        DataSource(
            identifier="btc_eur_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            window_size=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="eth_eur_1h", 
            symbol="ETH/EUR",
            time_frame="1h",
            window_size=100,
            market="BITVAVO"
        )
    ]
    
    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.5),  # 50% of portfolio
        PositionSize(symbol="ETH", percentage=0.3),  # 30% of portfolio
    ]
    
    def generate_buy_signals(self, data):
        """
        Generate buy signals for each symbol.
        
        Args:
            data: Dictionary with data source identifiers as keys
            
        Returns:
            Dict[str, pd.Series]: Boolean series for each symbol
        """
        signals = {}
        
        # BTC buy signal logic
        btc_data = data["btc_eur_1h"]
        btc_close = btc_data["Close"]
        btc_ma20 = btc_close.rolling(20).mean()
        signals["BTC"] = btc_close > btc_ma20  # Buy when price above MA20
        
        # ETH buy signal logic  
        eth_data = data["eth_eur_1h"]
        eth_close = eth_data["Close"]
        eth_ma20 = eth_close.rolling(20).mean()
        signals["ETH"] = eth_close > eth_ma20
        
        return signals
    
    def generate_sell_signals(self, data):
        """
        Generate sell signals for each symbol.
        
        Args:
            data: Dictionary with data source identifiers as keys
            
        Returns:
            Dict[str, pd.Series]: Boolean series for each symbol
        """
        signals = {}
        
        # BTC sell signal logic
        btc_data = data["btc_eur_1h"]
        btc_close = btc_data["Close"]
        btc_ma20 = btc_close.rolling(20).mean()
        signals["BTC"] = btc_close < btc_ma20  # Sell when price below MA20
        
        # ETH sell signal logic
        eth_data = data["eth_eur_1h"]
        eth_close = eth_data["Close"]
        eth_ma20 = eth_close.rolling(20).mean()
        signals["ETH"] = eth_close < eth_ma20
        
        return signals
```

#### Approach 2: Custom Strategy Logic

Override the `apply_strategy` method for full control over trading logic:

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, OrderSide

class MyCustomStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    
    def apply_strategy(self, context, data):
        """
        Custom strategy logic with full control.
        
        Args:
            context: Context object for portfolio operations
            data: Dictionary containing market data from data sources
        """
        symbol = "BTC"
        full_symbol = f"{symbol}/{context.get_trading_symbol()}"
        
        # Get current price
        price = context.get_latest_price(full_symbol)
        
        # Check if we have a position
        if not self.has_position(symbol):
            # Create a buy order
            self.create_limit_order(
                target_symbol=symbol,
                order_side=OrderSide.BUY,
                amount=0.01,
                price=price,
                execute=True
            )
        else:
            # Check for sell condition
            position = self.get_position(symbol)
            if price > position.cost * 1.05:  # 5% profit
                self.create_limit_order(
                    target_symbol=symbol,
                    order_side=OrderSide.SELL,
                    amount=position.amount,
                    price=price,
                    execute=True
                )
```

### Registering Your Strategy

```python
from investing_algorithm_framework import create_app, PortfolioConfiguration

# Create app
app = create_app()

# Add portfolio configuration
app.add_portfolio_configuration(
    PortfolioConfiguration(
        initial_balance=1000,
        market="BITVAVO",
        trading_symbol="EUR"
    )
)

# Add strategy
app.add_strategy(MySignalStrategy())

# Run the app
app.run()
```

## Strategy Examples

### Moving Average Crossover Strategy

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, DataSource, PositionSize
import pandas as pd

class MovingAverageCrossover(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]
    trading_symbol = "EUR"
    
    data_sources = [
        DataSource(
            identifier="btc_eur_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            window_size=60,
            market="BITVAVO"
        )
    ]
    
    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.9),
    ]
    
    def __init__(self, short_window=20, long_window=50, **kwargs):
        super().__init__(**kwargs)
        self.short_window = short_window
        self.long_window = long_window
    
    def generate_buy_signals(self, data):
        df = data["btc_eur_1h"]
        close = df["Close"]
        
        short_ma = close.rolling(window=self.short_window).mean()
        long_ma = close.rolling(window=self.long_window).mean()
        
        # Golden cross: short MA crosses above long MA
        buy_signal = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
        
        return {"BTC": buy_signal}
    
    def generate_sell_signals(self, data):
        df = data["btc_eur_1h"]
        close = df["Close"]
        
        short_ma = close.rolling(window=self.short_window).mean()
        long_ma = close.rolling(window=self.long_window).mean()
        
        # Death cross: short MA crosses below long MA
        sell_signal = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))
        
        return {"BTC": sell_signal}
```

### RSI Strategy with Stop Loss and Take Profit

```python
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, 
    PositionSize, StopLossRule, TakeProfitRule
)
import pandas as pd

class RSIStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC"]
    trading_symbol = "EUR"
    
    data_sources = [
        DataSource(
            identifier="btc_eur_4h",
            symbol="BTC/EUR",
            time_frame="4h",
            window_size=30,
            market="BITVAVO"
        )
    ]
    
    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.8),
    ]
    
    # Automatic stop loss at 5% loss
    stop_losses = [
        StopLossRule(symbol="BTC", percentage_threshold=0.05, sell_percentage=1.0),
    ]
    
    # Automatic take profit at 10% gain
    take_profits = [
        TakeProfitRule(symbol="BTC", percentage_threshold=0.10, sell_percentage=1.0),
    ]
    
    def __init__(self, rsi_period=14, oversold=30, overbought=70, **kwargs):
        super().__init__(**kwargs)
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
    
    def calculate_rsi(self, prices):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def generate_buy_signals(self, data):
        df = data["btc_eur_4h"]
        rsi = self.calculate_rsi(df["Close"])
        
        # Buy when RSI crosses above oversold level
        buy_signal = (rsi > self.oversold) & (rsi.shift(1) <= self.oversold)
        
        return {"BTC": buy_signal}
    
    def generate_sell_signals(self, data):
        df = data["btc_eur_4h"]
        rsi = self.calculate_rsi(df["Close"])
        
        # Sell when RSI crosses below overbought level
        sell_signal = (rsi < self.overbought) & (rsi.shift(1) >= self.overbought)
        
        return {"BTC": sell_signal}
```

## Key Methods

### Position and Order Management

```python
# Check if there are open orders for a symbol
has_orders = self.has_open_orders(target_symbol="BTC")

# Check if there is an open position
has_pos = self.has_position(symbol="BTC", amount_gt=0)

# Get a specific position
position = self.get_position(symbol="BTC")

# Get all positions
positions = self.get_positions(amount_gt=0)

# Create a limit order
order = self.create_limit_order(
    target_symbol="BTC",
    order_side=OrderSide.BUY,
    price=50000,
    amount=0.01,                    # Amount in target symbol
    # OR
    amount_trading_symbol=500,      # Amount in trading symbol (EUR)
    # OR  
    percentage_of_portfolio=0.1,    # 10% of portfolio
    execute=True,
    validate=True,
    sync=True
)

# Close a position entirely
self.close_position(symbol="BTC")
```

### Trade Management

```python
# Get all trades
trades = self.get_trades()

# Get open trades
open_trades = self.get_open_trades(target_symbol="BTC")

# Get closed trades
closed_trades = self.get_closed_trades()

# Close a specific trade
self.close_trade(trade=trade)
```

### Trade Event Callbacks

Override these methods to respond to trade events:

```python
class MyStrategy(TradingStrategy):
    # ... strategy config ...
    
    def on_trade_created(self, context, trade):
        """Called when a new trade is created"""
        print(f"Trade created: {trade}")
    
    def on_trade_opened(self, context, trade):
        """Called when a trade is opened"""
        pass
    
    def on_trade_closed(self, context, trade):
        """Called when a trade is closed"""
        print(f"Trade closed with P/L: {trade.net_gain}")
    
    def on_trade_updated(self, context, trade):
        """Called when a trade is updated"""
        pass
    
    def on_trade_stop_loss_triggered(self, context, trade):
        """Called when stop loss is triggered"""
        print(f"Stop loss triggered for {trade.target_symbol}")
    
    def on_trade_take_profit_triggered(self, context, trade):
        """Called when take profit is triggered"""
        print(f"Take profit triggered for {trade.target_symbol}")
    
    def on_trade_trailing_stop_loss_triggered(self, context, trade):
        """Called when trailing stop loss is triggered"""
        pass
```

## Position Sizing

Define how much of your portfolio to allocate per trade:

```python
from investing_algorithm_framework import PositionSize

class MyStrategy(TradingStrategy):
    position_sizes = [
        # Allocate 50% of portfolio to BTC trades
        PositionSize(symbol="BTC", percentage=0.5),
        # Allocate 30% of portfolio to ETH trades  
        PositionSize(symbol="ETH", percentage=0.3),
    ]
```

The framework automatically scales orders proportionally if total allocation exceeds available funds.

## Stop Loss and Take Profit Rules

### Stop Loss

```python
from investing_algorithm_framework import StopLossRule

class MyStrategy(TradingStrategy):
    stop_losses = [
        StopLossRule(
            symbol="BTC",
            percentage_threshold=0.05,  # Trigger at 5% loss
            sell_percentage=1.0,        # Sell 100% of position
            trailing=False              # Set True for trailing stop loss
        ),
    ]
```

### Take Profit

```python
from investing_algorithm_framework import TakeProfitRule

class MyStrategy(TradingStrategy):
    take_profits = [
        TakeProfitRule(
            symbol="BTC",
            percentage_threshold=0.10,  # Trigger at 10% profit
            sell_percentage=0.5,        # Sell 50% of position
            trailing=True               # Trailing take profit
        ),
    ]
```

## Metadata

Store strategy parameters and information:

```python
class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    
    metadata = {
        "author": "Your Name",
        "version": "1.0.0",
        "description": "Moving average crossover strategy",
        "params": {
            "short_window": 20,
            "long_window": 50
        }
    }
```

Or set via constructor:

```python
strategy = MyStrategy(
    metadata={
        "id": "strategy_001",
        "params": {"threshold": 0.05}
    }
)
```

## Best Practices

### 1. Always Define Required Attributes

Every strategy must have `time_unit` and `interval` defined:

```python
class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR  # Required
    interval = 1               # Required
```

### 2. Use Position Sizing

Always define position sizes to control risk:

```python
position_sizes = [
    PositionSize(symbol="BTC", percentage=0.3),
]
```

### 3. Implement Risk Management

Use stop losses and take profits:

```python
stop_losses = [
    StopLossRule(symbol="BTC", percentage_threshold=0.05, sell_percentage=1.0),
]

take_profits = [
    TakeProfitRule(symbol="BTC", percentage_threshold=0.15, sell_percentage=0.5),
]
```

### 4. Backtest Before Live Trading

```python
from datetime import datetime
from investing_algorithm_framework import BacktestDateRange

# Run backtest
results = app.run_backtest(
    backtest_date_range=BacktestDateRange(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31)
    ),
    initial_amount=1000
)

# Check results
print(f"Total return: {results.total_return}%")
print(f"Number of trades: {results.number_of_trades}")
```

### 5. Handle Edge Cases

Check for sufficient data before generating signals:

```python
def generate_buy_signals(self, data):
    df = data["btc_eur_1h"]
    
    if len(df) < self.required_window:
        # Return empty signals if not enough data
        return {"BTC": pd.Series([False] * len(df), index=df.index)}
    
    # Generate signals...
```

## Next Steps

Now that you understand how to create strategies, learn about:
- [Orders](orders) - Different order types and execution methods
- [Backtesting](backtesting) - Test your strategies with historical data
- [Data Sources](data-sources) - Configure market data for your strategies
