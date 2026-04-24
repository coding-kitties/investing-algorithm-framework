---
sidebar_position: 2
---

# Execution Logic

Understanding how the framework handles order execution is crucial for building reliable trading systems. The framework uses different execution logic for live trading and backtesting environments.

## Overview

The framework uses a **TradeOrderEvaluator** system to determine when orders are executed and how trades are updated. This system operates differently depending on whether you're running live trading or backtesting.

## Live Trading Execution

In live trading, the framework connects to real exchanges or brokers to execute orders and monitor their status.

### Order Status Checking

For live trading, the framework periodically checks the status of open orders by querying the exchange using the external order ID:

```python
class LiveTradeOrderEvaluator(TradeOrderEvaluator):

    def evaluate(self, open_trades, open_orders, market_data):
        """
        Evaluate orders and trades in live trading environment.
        """
        # Check status of open orders with exchange
        for order in open_orders:
            self._check_order_status_with_exchange(order)

        # Update trade prices with latest market data
        for trade in open_trades:
            self._update_trade_with_current_price(trade, market_data)

        # Check take profit and stop loss conditions
        self._check_take_profits()
        self._check_stop_losses()

    def _check_order_status_with_exchange(self, order):
        """
        Query the exchange for the current order status.
        """
        try:
            # Fetch order status from exchange using external_order_id
            exchange_order = self.exchange.fetch_order(order.external_order_id)

            # Update order status based on exchange response
            if exchange_order['status'] == 'closed':
                self.order_service.update(order.id, {
                    'status': OrderStatus.CLOSED.value,
                    'filled': exchange_order['filled'],
                    'remaining': exchange_order['remaining'],
                    'cost': exchange_order['cost'],
                    'fee': exchange_order['fee']
                })

        except Exception as e:
            logger.error(f"Failed to check order status: {e}")
```

### Key Features of Live Trading

- **Real-time Updates**: Orders are checked against actual exchange status
- **External Order IDs**: Framework tracks orders using exchange-provided IDs
- **Actual Fills**: Exact execution prices and fees from the exchange
- **Network Resilience**: Handles connection issues and API rate limits
- **Partial Fills**: Supports orders that fill in multiple transactions

### Exchange Integration

The framework uses CCXT for exchange connectivity:

```python
# Exchange connection is automatically managed
app.add_market(
    market="binance",
    trading_symbol="USDT",
    # API credentials loaded from environment
)

# Orders are automatically submitted to the exchange
algorithm.create_buy_order(
    target_symbol="BTC",
    amount=100,
    order_type="MARKET"
)
```

## Backtesting Execution

During backtesting, the framework simulates order execution using historical OHLCV data to determine when orders would have been filled.

### Default Backtesting Logic

The framework includes a default `BacktestTradeOrderEvaluator` that implements realistic order execution rules:

```python
from typing import List, Dict
import polars as pl
from investing_algorithm_framework.domain import OrderSide, OrderStatus, Trade, Order
from .trade_order_evaluator import TradeOrderEvaluator

class BacktestTradeOrderEvaluator(TradeOrderEvaluator):

    def evaluate(
        self,
        open_trades: List[Trade],
        open_orders: List[Order],
        ohlcv_data: Dict[str, pl.DataFrame]
    ):
        """
        Evaluate trades and orders based on OHLCV data.

        Args:
            open_orders (List[Order]): List of open Order objects.
            open_trades (List[Trade]): List of open Trade objects.
            ohlcv_data (dict[str, pl.DataFrame]): Mapping of
                symbol -> OHLCV Polars DataFrame.

        Returns:
            List[dict]: Updated trades with latest prices and execution status.
        """
        # First check pending orders
        for open_order in open_orders:
            data = ohlcv_data.get(open_order.symbol)
            self._check_has_executed(open_order, data)

        if len(open_trades) > 0:
            for open_trade in open_trades:
                data = ohlcv_data[open_trade.symbol]

                if data is None or data.is_empty():
                    continue

                # Get last row of data
                last_row = data.tail(1)
                update_data = {
                    "last_reported_price": last_row["Close"][0],
                    "last_reported_price_datetime": last_row["Datetime"][0],
                    "updated_at": last_row["Datetime"][0]
                }
                open_trade.update(update_data)

            self.trade_service.save_all(open_trades)
            self._check_take_profits()
            self._check_stop_losses()

    def _check_has_executed(self, order, ohlcv_df):
        """
        Check if the order has been executed based on OHLCV data.

        MARKET ORDER filled Rules:
        - Fills immediately on the first candle after the order's updated_at.
        - Uses the Open price of that candle as the fill price.
        - Applies slippage via TradingCost if configured.
        - Reconciles the portfolio: adjusts unallocated balance based on
          the difference between estimated and actual fill price.

        BUY ORDER filled Rules (Limit):
        - Only uses prices after the last update_at of the order.
        - If the lowest low price of the series is below or equal
            to the order price, e.g. if you buy asset at price 100
            and the low price of the series is 99, then the order is filled.

        SELL ORDER filled Rules (Limit):
        - Only uses prices after the last update_at of the order.
        - If the highest high price of the series is above or equal
            to the order price, e.g. if you sell asset at price 100
            and the high price of the series is 101, then the order is filled.

        Args:
            order (Order): Order.
            ohlcv_df (pl.DataFrame): OHLCV DataFrame for the symbol.

        Returns:
            None
        """

        if ohlcv_df.is_empty():
            return

        # Extract attributes from the order object
        updated_at = order.updated_at
        order_side = order.order_side
        order_price = order.price
        ohlcv_data_after_order = ohlcv_df.filter(
            pl.col('Datetime') >= updated_at
        )

        if ohlcv_data_after_order.is_empty():
            return

        if OrderSide.BUY.equals(order_side):
            # Check if the low price drops below or equals the order price
            if (ohlcv_data_after_order['Low'] <= order_price).any():
                self.order_service.update(
                    order.id, {
                        'status': OrderStatus.CLOSED.value,
                        'remaining': 0,
                        'filled': order.amount
                    }
                )

        elif OrderSide.SELL.equals(order_side):
            # Check if the high price goes above or equals the order price
            if (ohlcv_data_after_order['High'] >= order_price).any():
                self.order_service.update(
                    order.id, {
                        'status': OrderStatus.CLOSED.value,
                        'remaining': 0,
                        'filled': order.amount
                    }
                )
```

### Backtesting Execution Rules

The default backtesting logic implements the following rules:

#### Market Order Execution
- **Timing**: Fills on the first candle after the order was placed
- **Fill Price**: The **Open** price of that candle (simulating immediate execution at market open)
- **Slippage**: If a `TradingCost` with `slippage_percentage` is configured for the symbol, slippage is applied: `fill_price = open_price * (1 + slippage)` for buys, `open_price * (1 - slippage)` for sells
- **Reconciliation**: Since the order was created with an estimated price, the portfolio is automatically reconciled at fill time. The difference `(fill_price - estimated_price) * amount` is adjusted in the unallocated balance and position value

#### Buy Order Execution (Limit)
- **Timing**: Only considers price data after the order was placed
- **Fill Condition**: Order fills when the **Low** price touches or goes below the order price
- **Logic**: If you place a buy order at $100, it fills when the low price reaches $100 or lower

#### Sell Order Execution (Limit)
- **Timing**: Only considers price data after the order was placed
- **Fill Condition**: Order fills when the **High** price touches or goes above the order price
- **Logic**: If you place a sell order at $100, it fills when the high price reaches $100 or higher

#### Trade Updates
- **Price Tracking**: Open trades are updated with the latest **Close** price
- **Timestamp**: Trade updates use the timestamp from the OHLCV data
- **Risk Management**: Take profit and stop loss rules are checked after price updates

### Advantages of This Approach

1. **Conservative Simulation**: Uses High/Low prices to ensure orders could realistically have been filled
2. **Temporal Accuracy**: Only considers price movements after order placement
3. **Realistic Execution**: Simulates how limit orders would execute in real markets
4. **Risk Management**: Properly handles stop losses and take profits

## Custom Trade Order Evaluators

You can implement your own execution logic by creating a custom `TradeOrderEvaluator`:

### Creating a Custom Evaluator

```python
from investing_algorithm_framework.services import TradeOrderEvaluator
from investing_algorithm_framework.domain import OrderStatus, OrderSide

class CustomTradeOrderEvaluator(TradeOrderEvaluator):

    def __init__(self, slippage_percentage=0.001):
        super().__init__()
        self.slippage_percentage = slippage_percentage

    def evaluate(self, open_trades, open_orders, ohlcv_data):
        """
        Custom evaluation logic with slippage simulation.
        """
        for order in open_orders:
            self._check_execution_with_slippage(order, ohlcv_data)

        # Update trades as usual
        for trade in open_trades:
            self._update_trade_price(trade, ohlcv_data)

        # Check risk management rules
        self._check_take_profits()
        self._check_stop_losses()

    def _check_execution_with_slippage(self, order, ohlcv_data):
        """
        Check order execution with slippage consideration.
        """
        data = ohlcv_data.get(order.symbol)
        if data is None or data.is_empty():
            return

        # Filter data after order placement
        recent_data = data.filter(
            pl.col('Datetime') >= order.updated_at
        )

        if recent_data.is_empty():
            return

        # Apply custom execution logic with slippage
        if OrderSide.BUY.equals(order.order_side):
            # For buy orders, check if low price + slippage >= order price
            adjusted_low = recent_data['Low'] * (1 + self.slippage_percentage)
            if (adjusted_low <= order.price).any():
                # Calculate execution price with slippage
                execution_price = order.price * (1 + self.slippage_percentage)

                self.order_service.update(order.id, {
                    'status': OrderStatus.CLOSED.value,
                    'price': execution_price,  # Update with slipped price
                    'remaining': 0,
                    'filled': order.amount
                })

        elif OrderSide.SELL.equals(order.order_side):
            # For sell orders, check if high price - slippage <= order price
            adjusted_high = recent_data['High'] * (1 - self.slippage_percentage)
            if (adjusted_high >= order.price).any():
                execution_price = order.price * (1 - self.slippage_percentage)

                self.order_service.update(order.id, {
                    'status': OrderStatus.CLOSED.value,
                    'price': execution_price,
                    'remaining': 0,
                    'filled': order.amount
                })
```

### Advanced Custom Evaluator Example

Here's a more sophisticated evaluator that simulates partial fills and market impact:

```python
class AdvancedBacktestEvaluator(TradeOrderEvaluator):

    def __init__(self,
                 volume_threshold=0.1,  # Max 10% of volume per order
                 market_impact_factor=0.0005):  # 0.05% market impact
        super().__init__()
        self.volume_threshold = volume_threshold
        self.market_impact_factor = market_impact_factor

    def _check_execution_with_volume_limits(self, order, ohlcv_data):
        """
        Check execution considering volume constraints and market impact.
        """
        data = ohlcv_data.get(order.symbol)
        if data is None or data.is_empty():
            return

        recent_data = data.filter(pl.col('Datetime') >= order.updated_at)
        if recent_data.is_empty():
            return

        for row in recent_data.iter_rows(named=True):
            candle_volume = row['Volume']

            # Check if order size exceeds volume threshold
            max_fill_amount = candle_volume * self.volume_threshold

            if order.remaining > max_fill_amount:
                # Partial fill
                fill_amount = max_fill_amount
                remaining = order.remaining - fill_amount

                # Calculate market impact
                impact = fill_amount / candle_volume * self.market_impact_factor

                if OrderSide.BUY.equals(order.order_side):
                    if row['Low'] <= order.price:
                        execution_price = order.price * (1 + impact)
                        self._process_partial_fill(order, fill_amount, remaining, execution_price)
                        return

                elif OrderSide.SELL.equals(order.order_side):
                    if row['High'] >= order.price:
                        execution_price = order.price * (1 - impact)
                        self._process_partial_fill(order, fill_amount, remaining, execution_price)
                        return
            else:
                # Full fill possible
                if self._can_execute_order(order, row):
                    execution_price = self._calculate_execution_price(order, row)
                    self.order_service.update(order.id, {
                        'status': OrderStatus.CLOSED.value,
                        'price': execution_price,
                        'remaining': 0,
                        'filled': order.amount
                    })
                    return

    def _process_partial_fill(self, order, fill_amount, remaining, price):
        """Process a partial order fill."""
        self.order_service.update(order.id, {
            'status': OrderStatus.PARTIALLY_FILLED.value,
            'filled': order.filled + fill_amount,
            'remaining': remaining,
            'price': price
        })
```

### Registering a Custom Evaluator

Register your custom evaluator with the app:

```python
from investing_algorithm_framework import create_app

app = create_app()

# For backtesting
custom_evaluator = CustomTradeOrderEvaluator(slippage_percentage=0.002)
app.set_trade_order_evaluator(custom_evaluator)

# For live trading (automatically uses live evaluator)
app.add_market(market="binance", trading_symbol="USDT")
```

### Configuration for Different Environments

```python
import os
from investing_algorithm_framework import create_app

app = create_app()

# Choose evaluator based on environment
if os.getenv('ENVIRONMENT') == 'backtest':
    # Use custom backtesting evaluator
    evaluator = AdvancedBacktestEvaluator(
        volume_threshold=0.05,  # More conservative
        market_impact_factor=0.001
    )
    app.set_trade_order_evaluator(evaluator)
else:
    # Live trading uses default exchange-based evaluator
    app.add_market(market="binance", trading_symbol="USDT")
```

## Best Practices

### For Backtesting
1. **Conservative Assumptions**: Use realistic execution rules that account for market realities
2. **Volume Constraints**: Consider whether your order size could realistically be filled
3. **Slippage Modeling**: Include slippage, especially for larger orders or less liquid markets. Use `TradingCost` on your strategy to configure slippage per symbol:
   ```python
   from investing_algorithm_framework import TradingCost

   class MyStrategy(TradingStrategy):
       trading_costs = [
           TradingCost(symbol="BTC", slippage_percentage=0.001, fee_percentage=0.001),
       ]
   ```
4. **Market vs Limit Orders**: Use market orders when you want immediate execution at the next candle's open price. Use limit orders when you want to target a specific price level
5. **Latency Simulation**: Account for the time between signal generation and order placement

### For Live Trading
1. **Error Handling**: Implement robust error handling for exchange connectivity issues
2. **Rate Limiting**: Respect exchange API rate limits when checking order status
3. **Order Monitoring**: Regularly check order status to catch fills quickly
4. **Partial Fills**: Handle partial fills appropriately in your strategy logic

### Custom Evaluators
1. **Test Thoroughly**: Backtest custom evaluators extensively before live trading
2. **Document Logic**: Clearly document your execution rules and assumptions
3. **Performance**: Ensure your evaluator doesn't slow down strategy execution
4. **Validation**: Compare results with simpler evaluators to validate behavior

## Conclusion

Understanding execution logic is crucial for building reliable trading systems. The framework provides sensible defaults for both live trading and backtesting, but allows you to implement custom logic when needed. Whether you're running simple backtests or complex live trading systems, the TradeOrderEvaluator system gives you the flexibility to model execution behavior accurately.

## Next Steps

- Explore [Logging Configuration](logging-configuration) to monitor your execution logic
- Learn about portfolio management and risk controls
- Study the framework's built-in risk management features
