---
sidebar_position: 6
---
# Positions
In this section we will discuss how to retrieve, list and close positions.
The position of your trading bot are centrally managed by the algorithm component.
In your strategy you can create positions, retrieve positions and list positions through the algorithm component.


## Trading symbol position
Your algorithm has one specific position that is called the trading symbol position.
The trading symbol position is the position of the quoted symbol that is used by the algorithm in its trades.
You specify the trading symbol in a `PortfolioConfiguration` object that you pass to the algorithm component.

```python
from investing_algorithm_framework import PortfolioConfiguration

portfolio_configuration = PortfolioConfiguration(
    initial_balance=1000,
    trading_symbol="EUR",
    market="BINANCE",
)
```

You can retrieve the trading symbol position by using the following method of the algorithm component:

```python
from investing_algorithm_framework import Algorithm

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    trading_symbol_position = algorithm.get_position("EUR")
```

### Checking if the trading symbol position amount is available
You can check if the trading symbol position amount is available by using the following method of the algorithm component:

```python
from investing_algorithm_framework import Algorithm

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
        
    if algorithm.has_trading_symbol_position_available(percentage_of_portfolio=20):
        # Do something
        
    if algorithm.has_trading_symbol_position_available(amount_gt=20):
        # Do something
        
    if algorithm.has_trading_symbol_position_available(amount_gte=20):
        # Do something  
```

## Retrieving a position
You can retrieve a position by using the following method of the algorithm component:

```python
from investing_algorithm_framework import Algorithm

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    position = algorithm.get_position("<symbol>")
```

## Listing positions
You can list all positions by using the following method of the algorithm component:

```python
from investing_algorithm_framework import Algorithm

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    positions = algorithm.get_positions()
    positions_with_amoint_greater_than_10 = algorithm.get_position(amount_gt=10)
    positions_with_amoint_greater_than_or_equal_to_10 = algorithm.get_position(amount_gte=10)
    positions_with_amoint_less_than_10 = algorithm.get_position(amount_lt=10)
    positions_with_amoint_less_than_or_equal_to_10 = algorithm.get_position(amount_lte=10) 
```

## Closing position
You can close a position by using the following method of the algorithm component:

> When closing a position, the algorithm will create a limit sell order for the given symbol 
> and amount of the position.

```python
from investing_algorithm_framework import Algorithm

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.close_position("<symbol>")
```
