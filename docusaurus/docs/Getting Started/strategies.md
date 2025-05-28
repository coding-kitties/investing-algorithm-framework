---
sidebar_position: 4
---
# Strategies

Strategies are the core of the framework. They are the main entry point for the framework. 
Strategies are used to define the trading logic of your algorithm. In your strategy you can use the algorithm object to
place orders, get orders, get the current balance and more.

When defining a strategy you need to define the following things:

- The time unit of the strategy (second, minute, hour, day, week, month)
- The interval of the strategy (how often the strategy should run within the time unit)

The framework comes with two ways to define a strategy.

- Class based strategies
- Decorator strategies

## Class based strategy


```python
from investing_algorithm_framework import TimeUnit, TradingStrategy, Algorithm

app = create_app()

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND # The time unit of the strategy
    interval = 5 # The interval of the strategy, runs every 5 seconds

    def apply_strategy(self, algorithm: Algorithm, market_data: Dict[str, Any]):
        pass
        
app.register_strategy(MyTradingStrategy)
```

## Decorator based strategy

```python
from investing_algorithm_framework import create_app, TimeUnit, Algorithm

# Runs every 5 seconds
@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    pass
```
