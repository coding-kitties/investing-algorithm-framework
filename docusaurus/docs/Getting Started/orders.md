---
sidebar_position: 5
---

# Orders
In this section we will discuss how to create, retrieve and list orders.
The orders of your trading bot are centrally managed by the algorithm component.
In your strategy you can create orders, retrieve orders and list orders through the algorithm component.
The following orders are supported by the framework:

* Limit buy orders
* Limit sell orders
* Close position orders
* Close trade orders


## Creating limit buy order
You can create orders by using the following methods of the framework

```python
from investing_algortihm_framework import OrderSide, Context

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(context: Context, market_data: Dict[str, Any]):
    context.create_limit_order(
        symbol="<symbol>", # E.g BTC
        order_side=OrderSide.BUY, # or "buy"
        amount=20,
        price=10
    )
```

### Creating a limit buy order based on a percentage of your portfolio
```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.create_limit_order(
        symbol="<symbol>", # E.g BTC 
        order_side=OrderSide.BUY, # or "buy"
        price=10,
        percentage_of_portfolio=20 # Invest 20% of your portfolio unallocated funds
    )
```

You can also set the precision of the order by using the `precision` parameter. The precision parameter is used to 
round the amount of the order to the given precision. E.g. if you set the precision to 2, the amount of the order 
will be rounded to 2 decimals.


```python
from investing_algortihm_framework import OrderSide
@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.create_limit_order(
        symbol="<symbol>", # E.g BTC 
        order_side=OrderSide.BUY, # or "buy"
        price=10,
        percentage_of_portfolio=20, # Invest 20% of your portfolio unallocated funds
        precision=4 # Round the amount of the order to 4 decimals
    )
```

## Creating a limit sell order

```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.create_limit_order(
        symbol="<symbol>", # E.g BTC
        order_side=OrderSide.SELL, # or "sell"
        price=10,
        amount=20
    )
```


### Creating a limit sell order based on a percentage of your position
```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.create_limit_order(
        symbol="<symbol>", # E.g BTC  
        order_side=OrderSide.SELL, # or "sell"
        price=10,
        percentage_of_position=20 # Sell 20% of your position of the given symbol
    )
```

You can also set the precision of the order by using the `precision` parameter. The precision parameter is used to
round the amount of the order to the given precision. E.g. if you set the precision to 2, the amount of the order
will be rounded to 2 decimals.

```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.create_limit_order(
        symbol="<symbol>", # E.g BTC  
        order_side=OrderSide.SELL, # or "sell"
        price=10,
        percentage_of_position=20, # Sell 20% of your position of the given symbol
        precision=4 # Round the amount of the order to 4 decimals
    )
```

### Closing a position with a limit sell order
Closing a position can easily be done by using the `close_position` method of your algorithm component.
This method will create a limit sell order for the given symbol and amount of the position.
```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.close_position(<symbol>) # E.g BTC close your BTC position
```


## Retrieving an order
You can retrieve an order by using the `get_order` method of your algorithm component. If you want to retrieve an order
by reference id (Order id set to the order from the broker or exchange), you can do this in the following way:

```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    order = algorithm.get_order(reference_id=<your broker/exchange order id>))
```

### Retrieving an order with other parameters

You can retrieve an order by symbol and market in the following way.


:::info Multiple orders mismatch
Keep in mind that when there exist multiple orders for a given symbol or market, you will
likely not retrieve the order you are looking for. It is probably better to retrieve the order by reference id or list all 
orders and filter the order you are looking for.
:::

```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
        order = algorithm.get_order(
            market=<market e.g. binance, bitvavo>,
            target_symbol=<target symbol e.g. btc, dot>,
            trading_symbol=<trading symbol e.g. eur>,
            order_side=<order side e.g. SELL, BUY>,
            order_type=<order type e.g. LIMIT, MARKET>,
        )
```

## Listing all orders
You can list all orders by using the `get_orders` method of your algorithm component.

```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    orders = algorithm.get_orders(
        market=<market e.g. binance, bitvavo>,
        target_symbol=<target symbol e.g. btc, dot>,
        status=<status of the order e.g. FILLED, OPEN>,
        order_side=<order side e.g. SELL, BUY>,
        order_type=<order type e.g. LIMIT, MARKET>,
    )
```

## Checking pending orders
You can check the status of your orders by using the `check_pending_orders` method of your algorithm component.
The framework will automatically update the status of your order if it has been changed by the broker or exchange. This
means that the filled, remaining, status and order fee attributes of your order will be updated.

:::info Pending orders are checked automatically
The framework will automatically check your pending orders every time your strategy runs. This means that you don't have to 
call the `check_pending_orders` method of your algorithm component in your strategy. This method is only useful if you want to
check the status of your orders in between strategy runs (e.g. in a recurring [task](/tasks) you define or when you 
you want to call the method again in your strategy).
:::

```python
from investing_algortihm_framework import OrderSide

@app.strategy(time_unit=TimeUnit.SECOND, interval=5)
def perform_strategy(algorithm: Algorithm, market_data: Dict[str, Any]):
    algorithm.check_pending_orders()
```