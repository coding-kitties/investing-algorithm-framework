---
sidebar_position: 7
---

# Trades

Understand how the framework tracks trades and how to access trade data through the Context API.

## Overview

A **Trade** represents a round-trip position: it is opened by a buy order and closed by one or more sell orders. Unlike orders (instructions to buy/sell) or positions (current holdings), a trade tracks the full lifecycle from entry to exit, including net gain, stop losses, and take profits.

## Trade Lifecycle

1. **Created** — A buy order is placed, and a trade record is created with status `CREATED`.
2. **Open** — The buy order fills and the trade becomes `OPEN`. The trade has an `open_price`, `amount`, and `cost`.
3. **Closed** — A sell order fills against the trade, closing it. The `net_gain` is calculated, `closed_at` is set, and status becomes `CLOSED`.

A single sell order can close multiple trades, and a single trade can be closed by multiple partial sell orders.

## Trade Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Unique trade identifier. |
| `target_symbol` | `str` | The asset being traded (e.g., `"BTC"`). |
| `trading_symbol` | `str` | The quote currency (e.g., `"EUR"`). |
| `status` | `str` | One of `CREATED`, `OPEN`, or `CLOSED`. |
| `opened_at` | `datetime` | When the trade was opened. |
| `closed_at` | `datetime` | When the trade was closed (`None` if still open). |
| `open_price` | `float` | The price at which the trade was opened. |
| `amount` | `float` | The total amount of the trade. |
| `available_amount` | `float` | The amount still available (not yet sold). |
| `filled_amount` | `float` | The amount filled by the opening buy order. |
| `remaining` | `float` | The remaining unfilled amount from the buy order. |
| `cost` | `float` | The total cost of the trade (price × amount). |
| `net_gain` | `float` | Realized profit or loss. |
| `last_reported_price` | `float` | The most recent market price reported for this trade. |
| `orders` | `list` | Orders associated with this trade. |
| `stop_losses` | `list` | Stop loss rules attached to this trade. |
| `take_profits` | `list` | Take profit rules attached to this trade. |
| `metadata` | `dict` | Custom key-value data you can attach to a trade. |

## Accessing Trades

All trade access goes through the `Context` object, which is passed to your strategy's `run` method and to tasks.

### Get a Single Trade

```python
# Get a trade by target symbol
trade = context.get_trade(target_symbol="BTC")

# Get a trade by status
trade = context.get_trade(status="OPEN", target_symbol="ETH")

# Get a trade by order ID
trade = context.get_trade(order_id=some_order_id)
```

**Parameters:** `target_symbol`, `trading_symbol`, `market`, `portfolio`, `status`, `order_id` — all optional filters.

### Get Multiple Trades

```python
# All trades
trades = context.get_trades()

# Trades for a specific symbol
btc_trades = context.get_trades(target_symbol="BTC")

# Trades filtered by status
open_trades = context.get_trades(status="OPEN")
```

### Get Open Trades

```python
# All open trades
open_trades = context.get_open_trades()

# Open trades for a specific symbol
btc_open = context.get_open_trades(target_symbol="BTC")
```

### Get Closed Trades

```python
closed_trades = context.get_closed_trades()
```

### Get Pending Trades

Pending trades have status `CREATED` — the buy order hasn't filled yet:

```python
pending = context.get_pending_trades()
pending_btc = context.get_pending_trades(target_symbol="BTC")
```

### Count Trades

```python
total = context.count_trades()
btc_count = context.count_trades(target_symbol="BTC")
```

## Inspecting a Trade

```python
def log_trade(trade):
    print(f"Trade ID: {trade.id}")
    print(f"Symbol: {trade.target_symbol}/{trade.trading_symbol}")
    print(f"Status: {trade.status}")
    print(f"Opened at: {trade.opened_at}")
    print(f"Open price: {trade.open_price}")
    print(f"Amount: {trade.amount}")
    print(f"Available amount: {trade.available_amount}")
    print(f"Cost: {trade.cost}")
    print(f"Net gain: {trade.net_gain}")
    print(f"Last reported price: {trade.last_reported_price}")

    if trade.closed_at:
        print(f"Closed at: {trade.closed_at}")
```

## Stop Losses

Add a stop loss to an open trade using `context.add_stop_loss()`. When the price drops below the stop loss level, the framework automatically sells.

```python
# Fixed stop loss: sell if price drops 5% below open price
context.add_stop_loss(trade, percentage=5)

# Trailing stop loss: the stop level moves up as the price rises
context.add_stop_loss(trade, percentage=5, trailing=True)

# Partial stop loss: sell only 50% of the position
context.add_stop_loss(trade, percentage=5, sell_percentage=50)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `trade` | `Trade` | — | The trade to protect. |
| `percentage` | `float` | — | Percentage below open price (e.g., `5` for 5%). |
| `trailing` | `bool` | `False` | If `True`, the stop level trails the high water mark. |
| `sell_percentage` | `float` | `100` | Percentage of the trade to sell when triggered. |

### How Fixed Stop Loss Works

1. You buy BTC at $40,000.
2. You set a 5% stop loss → stop level at $38,000.
3. BTC rises to $42,000 → stop level stays at $38,000.
4. BTC drops to $38,000 → stop loss triggers, trade closes.

### How Trailing Stop Loss Works

1. You buy BTC at $40,000.
2. You set a 5% trailing stop loss → initial stop at $38,000.
3. BTC rises to $42,000 → stop level adjusts to $39,900 (5% below new high).
4. BTC drops to $39,900 → stop loss triggers, trade closes.

## Take Profits

Add a take profit to lock in gains when the price rises to a target level.

```python
# Fixed take profit: sell if price rises 10% above open price
context.add_take_profit(trade, percentage=10)

# Trailing take profit: locks in gains as price rises
context.add_take_profit(trade, percentage=10, trailing=True)

# Partial take profit: sell 50% of the position
context.add_take_profit(trade, percentage=10, sell_percentage=50)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `trade` | `Trade` | — | The trade to set a target on. |
| `percentage` | `float` | — | Percentage above open price (e.g., `10` for 10%). |
| `trailing` | `bool` | `False` | If `True`, the take profit level trails the price upward. |
| `sell_percentage` | `float` | `100` | Percentage of the trade to sell when triggered. |

### How Fixed Take Profit Works

1. You buy BTC at $40,000.
2. You set a 5% take profit → target at $42,000.
3. BTC rises to $42,000 → take profit triggers, trade closes.

### How Trailing Take Profit Works

1. You buy BTC at $40,000.
2. You set a 5% trailing take profit → target initially at $42,000.
3. BTC rises to $45,000 → take profit adjusts to $42,750 (5% below new high).
4. BTC drops to $42,750 → take profit triggers, trade closes with profit.

## Closing a Trade Manually

You can close a trade programmatically via `context.close_trade()`:

```python
open_trades = context.get_open_trades(target_symbol="BTC")

for trade in open_trades:
    context.close_trade(trade)
```

This creates a market sell order for the trade's available amount.

## Example: Strategy with Stop Loss and Take Profit

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit

class ManagedTradeStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1

    def run(self, context):
        # Check for new open trades and attach risk management
        open_trades = context.get_open_trades(target_symbol="BTC")

        for trade in open_trades:
            # Only add stop/take if none exist yet
            if not trade.stop_losses:
                context.add_stop_loss(trade, percentage=5, trailing=True)

            if not trade.take_profits:
                context.add_take_profit(trade, percentage=15)
```

## Trade Statistics

```python
def print_trade_summary(context):
    total = context.count_trades()
    open_trades = context.get_open_trades()
    closed_trades = context.get_closed_trades()

    total_net_gain = sum(t.net_gain for t in closed_trades)
    winners = [t for t in closed_trades if t.net_gain > 0]
    losers = [t for t in closed_trades if t.net_gain <= 0]

    print(f"Total trades: {total}")
    print(f"Open: {len(open_trades)}")
    print(f"Closed: {len(closed_trades)}")
    print(f"Winners: {len(winners)}")
    print(f"Losers: {len(losers)}")
    print(f"Total net gain: {total_net_gain:.2f}")

    if closed_trades:
        win_rate = len(winners) / len(closed_trades) * 100
        print(f"Win rate: {win_rate:.1f}%")
```

## Next Steps

Now that you understand trades, learn about [Tasks](tasks) to automate monitoring and reporting for your trading activity.
