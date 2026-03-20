---
sidebar_position: 8
---

# Tasks

Learn how to create and schedule automated tasks that run alongside your trading strategies.

## Overview

Tasks are automated functions that run on a fixed schedule, independently of your trading strategies. They are useful for maintenance, monitoring, reporting, and other periodic background work. Tasks receive a `Context` object, giving them access to portfolio data, trades, orders, and positions.

## Task Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `time_unit` | `TimeUnit` | The time unit for the schedule: `SECOND`, `MINUTE`, `HOUR`, or `DAY`. |
| `interval` | `int` | How many time units between each run (e.g., `10` with `MINUTE` = every 10 minutes). |
| `worker_id` | `str` | Optional identifier. Defaults to the class name (class-based) or function name (decorator-based). |

## Creating Tasks

### Class-Based Task

Subclass `Task` and implement the `run(self, context)` method:

```python
from investing_algorithm_framework import Task, TimeUnit

class PortfolioLoggerTask(Task):

    def __init__(self):
        super().__init__(
            time_unit=TimeUnit.HOUR,
            interval=1  # Run every hour
        )

    def run(self, context):
        """Receives a Context object with access to trades, orders, positions."""
        open_trades = context.get_open_trades()
        print(f"Currently {len(open_trades)} open trades")
```

### Decorator-Based Task

Use `@app.task()` to turn any function into a task:

```python
from investing_algorithm_framework import create_app, TimeUnit

app = create_app()

@app.task(time_unit=TimeUnit.MINUTE, interval=10)
def check_positions(context):
    """Runs every 10 minutes."""
    positions = context.get_positions()

    for position in positions:
        print(f"{position.symbol}: {position.get_amount()}")
```

## Registering Tasks

### With `add_task`

Register a class-based task (instance or class) using `app.add_task()`:

```python
from investing_algorithm_framework import create_app

app = create_app()

# Pass an instance
app.add_task(PortfolioLoggerTask())

# Or pass the class — the framework will instantiate it
app.add_task(PortfolioLoggerTask)
```

### With `add_tasks`

Register multiple tasks at once:

```python
app.add_tasks([PortfolioLoggerTask, AnotherTask()])
```

## Schedule Examples

```python
from investing_algorithm_framework import Task, TimeUnit

# Run every 30 seconds
class FrequentCheck(Task):
    def __init__(self):
        super().__init__(time_unit=TimeUnit.SECOND, interval=30)

    def run(self, context):
        pass

# Run every 5 minutes
class FiveMinuteTask(Task):
    def __init__(self):
        super().__init__(time_unit=TimeUnit.MINUTE, interval=5)

    def run(self, context):
        pass

# Run every 4 hours
class FourHourTask(Task):
    def __init__(self):
        super().__init__(time_unit=TimeUnit.HOUR, interval=4)

    def run(self, context):
        pass

# Run once per day
class DailyTask(Task):
    def __init__(self):
        super().__init__(time_unit=TimeUnit.DAY, interval=1)

    def run(self, context):
        pass
```

## Common Task Examples

### Trade Monitoring

```python
from investing_algorithm_framework import Task, TimeUnit

class TradeMonitorTask(Task):

    def __init__(self):
        super().__init__(time_unit=TimeUnit.MINUTE, interval=5)

    def run(self, context):
        open_trades = context.get_open_trades()

        for trade in open_trades:
            print(
                f"Trade {trade.id}: {trade.target_symbol} "
                f"opened at {trade.open_price}, "
                f"net gain: {trade.net_gain}"
            )
```

### Portfolio Snapshot

```python
from investing_algorithm_framework import Task, TimeUnit

class PortfolioSnapshotTask(Task):

    def __init__(self):
        super().__init__(time_unit=TimeUnit.HOUR, interval=1)

    def run(self, context):
        portfolio = context.get_portfolio()
        positions = context.get_positions()

        print(f"Portfolio net size: {portfolio.get_net_size()}")
        print(f"Number of positions: {len(positions)}")
        print(f"Open trades: {context.count_trades()}")
```

### Trade Count Summary

```python
from investing_algorithm_framework import create_app, TimeUnit

app = create_app()

@app.task(time_unit=TimeUnit.DAY, interval=1)
def daily_summary(context):
    """Logs a daily summary of trade counts."""
    total = context.count_trades()
    closed = len(context.get_closed_trades())
    open_trades = len(context.get_open_trades())
    pending = len(context.get_pending_trades())

    print(f"Total: {total}, Open: {open_trades}, Closed: {closed}, Pending: {pending}")
```

## Full Example

```python
from investing_algorithm_framework import create_app, Task, TimeUnit

app = create_app()

# Class-based task
class LogOpenTrades(Task):
    def __init__(self):
        super().__init__(time_unit=TimeUnit.MINUTE, interval=15)

    def run(self, context):
        for trade in context.get_open_trades():
            print(f"[{trade.target_symbol}] net_gain={trade.net_gain}")

# Decorator-based task
@app.task(time_unit=TimeUnit.HOUR, interval=1)
def log_portfolio(context):
    portfolio = context.get_portfolio()
    print(f"Portfolio size: {portfolio.get_net_size()}")

# Register class-based task
app.add_task(LogOpenTrades)
```

## Next Steps

Now that you understand tasks, learn about [Trades](trades) to see how the framework tracks your trading activity.
