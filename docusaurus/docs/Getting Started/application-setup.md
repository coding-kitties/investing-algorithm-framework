---
sidebar_position: 2
---

# Application Setup

Learn how to set up your first trading application using the Investing Algorithm Framework.

## Creating Your First App

The framework provides a simple `create_app()` function to initialize your trading application:

```python
from investing_algorithm_framework import create_app

app = create_app()
```

## Adding a Market

Before you can trade, you need to add a market configuration:

```python
app.add_market(
    market="bitvavo",
    trading_symbol="EUR",
)
```

## Adding a Strategy

Register your trading strategy with the application:

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit

class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    
    def run(self, algorithm):
        # Your trading logic here
        pass

app.add_strategy(MyStrategy())
```

## Running the Application

### Live Trading

To start live trading:

```python
app.run()
```

### Backtesting

To run a backtest:

```python
from datetime import datetime, timezone
from investing_algorithm_framework import BacktestDateRange

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)
```

## Complete Example

Here's a complete example bringing it all together:

```python
from investing_algorithm_framework import (
    create_app, 
    TradingStrategy, 
    TimeUnit,
    BacktestDateRange
)
from datetime import datetime, timezone

# Create the application
app = create_app()

# Define your strategy
class SimpleStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC", "ETH"]
    
    def run(self, algorithm):
        for symbol in self.symbols:
            # Your trading logic
            pass

# Add market and strategy
app.add_market(market="bitvavo", trading_symbol="EUR")
app.add_strategy(SimpleStrategy())

# Run backtest
backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

backtest = app.run_backtest(
    backtest_date_range=backtest_range,
    initial_amount=1000
)

print(f"Total return: {backtest.get_total_return()}%")
```

## Next Steps

- Learn about [Portfolio Configuration](./portfolio-configuration) to manage your assets
- Explore [Strategies](./strategies) for advanced strategy development
- Check out [Backtesting](./backtesting) for comprehensive testing

