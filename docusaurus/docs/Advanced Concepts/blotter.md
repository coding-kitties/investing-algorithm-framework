---
sidebar_position: 3
---

# Blotter

Learn how the Blotter system works and how to use slippage models, commission models, and custom order routing.

## Overview

The **Blotter** sits between your strategy and the order execution layer. Every order you create — whether via `create_limit_order()`, `create_market_order()`, or `batch_order()` — flows through the blotter before reaching the `OrderService`.

```
Strategy (Context)
       │
       ▼
   ┌────────┐
   │ Blotter │  ← slippage, commission, routing
   └────┬───┘
        │
        ▼
  OrderService  → OrderExecutor → Exchange / Simulation
```

The framework automatically selects a blotter if you don't set one:

| Mode         | Default Blotter       | Behavior                                   |
|-------------|----------------------|---------------------------------------------|
| Live trading | `DefaultBlotter`     | Pass-through — no slippage or commission     |
| Backtesting  | `SimulationBlotter`  | Configurable slippage and commission models  |

You can override the default by calling `app.set_blotter(...)` with any `Blotter` subclass.

## Slippage Models

Slippage models determine how the execution price deviates from the intended order price. They are used by the `SimulationBlotter` during backtesting.

### NoSlippage (default)

Orders fill at the exact intended price.

```python
from investing_algorithm_framework import SimulationBlotter, NoSlippage

app.set_blotter(SimulationBlotter(
    slippage_model=NoSlippage()
))
```

### PercentageSlippage

Buy orders fill at a slightly higher price, sell orders at a slightly lower price.

```python
from investing_algorithm_framework import SimulationBlotter, PercentageSlippage

# 0.1% slippage
app.set_blotter(SimulationBlotter(
    slippage_model=PercentageSlippage(percentage=0.001)
))
```

For a buy order at price `100.0` with `0.1%` slippage, the fill price becomes `100.10`. For a sell order, it becomes `99.90`.

### FixedSlippage

Adds or subtracts a fixed amount from the order price.

```python
from investing_algorithm_framework import SimulationBlotter, FixedSlippage

# $0.05 slippage per order
app.set_blotter(SimulationBlotter(
    slippage_model=FixedSlippage(amount=0.05)
))
```

### Custom Slippage Model

Create your own by extending `SlippageModel`:

```python
from investing_algorithm_framework import SlippageModel

class VolumeWeightedSlippage(SlippageModel):
    def __init__(self, base_pct=0.001, volume_factor=0.0001):
        self.base_pct = base_pct
        self.volume_factor = volume_factor

    def calculate_slippage(self, price, order_side, amount=None):
        pct = self.base_pct
        if amount is not None:
            pct += self.volume_factor * amount

        if order_side == "BUY":
            return price * (1 + pct)
        return price * (1 - pct)
```

## Commission Models

Commission models determine the fee charged for each trade. They are used by the `SimulationBlotter` during backtesting.

### NoCommission (default)

Zero fees on all trades.

```python
from investing_algorithm_framework import SimulationBlotter, NoCommission

app.set_blotter(SimulationBlotter(
    commission_model=NoCommission()
))
```

### PercentageCommission

Fee is a percentage of the total trade value (`price × amount`).

```python
from investing_algorithm_framework import SimulationBlotter, PercentageCommission

# 0.1% commission
app.set_blotter(SimulationBlotter(
    commission_model=PercentageCommission(percentage=0.001)
))
```

### FixedCommission

A fixed fee per trade, regardless of trade size.

```python
from investing_algorithm_framework import SimulationBlotter, FixedCommission

# $1.00 per trade
app.set_blotter(SimulationBlotter(
    commission_model=FixedCommission(amount=1.0)
))
```

### Custom Commission Model

Create your own by extending `CommissionModel`:

```python
from investing_algorithm_framework import CommissionModel

class TieredCommission(CommissionModel):
    def calculate_commission(self, price, amount, order_side):
        trade_value = price * amount
        if trade_value > 10000:
            return trade_value * 0.0005  # 0.05% for large trades
        return trade_value * 0.001       # 0.1% for small trades
```

## SimulationBlotter

The `SimulationBlotter` applies slippage and commission models to every order and records each fill as a `Transaction`.

```python
from investing_algorithm_framework import (
    SimulationBlotter,
    PercentageSlippage,
    PercentageCommission,
)

app.set_blotter(SimulationBlotter(
    slippage_model=PercentageSlippage(0.001),    # 0.1% slippage
    commission_model=PercentageCommission(0.001), # 0.1% commission
))
```

:::info Automatic Setup
If you don't set a blotter and run a backtest, the framework automatically uses a `SimulationBlotter` with `NoSlippage` and `NoCommission`.
:::

## Transactions

Every order placed through the blotter is recorded as a `Transaction`. Transactions provide an audit trail of all fills, including the actual execution price, slippage, and commission.

```python
class MyStrategy(TradingStrategy):
    def run_strategy(self, algorithm, market_data):
        # Place some orders...
        self.create_limit_order(
            target_symbol="BTC", price=50000, amount=0.1
        )

        # Get all transactions recorded by the blotter
        transactions = self.get_transactions()

        for tx in transactions:
            print(f"{tx.symbol} {tx.order_side}: "
                  f"price={tx.price}, amount={tx.amount}, "
                  f"commission={tx.commission}, slippage={tx.slippage}")
```

Each `Transaction` contains:

| Field | Description |
|-------|-------------|
| `order_id` | ID of the order |
| `symbol` | Target symbol (e.g. `"BTC"`) |
| `order_side` | `"BUY"` or `"SELL"` |
| `price` | Actual fill price (after slippage) |
| `amount` | Fill amount |
| `cost` | Total cost (`price × amount`) |
| `commission` | Commission charged |
| `slippage` | Slippage amount (`abs(fill_price - intended_price)`) |
| `timestamp` | UTC timestamp of the fill |

You can serialize a transaction with `tx.to_dict()`.

## Batch Orders

The `batch_order()` method lets you place multiple orders at once through the blotter:

```python
class MyStrategy(TradingStrategy):
    def run_strategy(self, algorithm, market_data):
        orders = [
            {
                "target_symbol": "BTC",
                "order_side": "BUY",
                "price": 50000,
                "amount": 0.1,
            },
            {
                "target_symbol": "ETH",
                "order_side": "BUY",
                "price": 3000,
                "amount": 1.0,
            },
        ]
        created_orders = self.batch_order(orders)
```

The default implementation places orders sequentially. Override `batch_order()` in a custom blotter for atomic batch behavior or smart order routing.

## Custom Blotter

Create your own blotter by extending the `Blotter` class and implementing `place_order()` and `cancel_order()`:

```python
from investing_algorithm_framework import Blotter

class SmartOrderRouter(Blotter):
    def place_order(self, order_data, context):
        """
        Custom order routing logic.
        """
        symbol = order_data.get("target_symbol")

        # Example: route large orders differently
        amount = order_data.get("amount", 0)
        if amount > 100:
            # Split into smaller orders
            half = amount / 2
            order_data["amount"] = half
            order1 = context.order_service.create(order_data)
            order2 = context.order_service.create(order_data)
            return order1  # Return the first order
        
        return context.order_service.create(order_data)

    def cancel_order(self, order_id, context):
        """
        Cancel a specific order.
        """
        order = context.order_service.get(order_id)
        if order is None:
            raise Exception(f"Order {order_id} not found")
        
        context.order_service.update(
            order_id, {"status": "CANCELED"}
        )
        return context.order_service.get(order_id)

# Register the custom blotter
app.set_blotter(SmartOrderRouter())
```

### Blotter API

| Method | Required | Description |
|--------|----------|-------------|
| `place_order(order_data, context)` | Yes | Place a single order. Must be implemented. |
| `cancel_order(order_id, context)` | Yes | Cancel an order. Must be implemented. |
| `batch_order(orders_data, context)` | No | Place multiple orders. Default calls `place_order()` sequentially. |
| `get_open_orders(context, target_symbol)` | No | Get open orders. Default delegates to context. |
| `get_transactions()` | No | Get recorded transactions. |
| `record_transaction(transaction)` | No | Record a fill. |
| `clear_transactions()` | No | Clear all recorded transactions. |
| `prune_orders(context)` | No | Clean up stale orders. Default is a no-op. |
