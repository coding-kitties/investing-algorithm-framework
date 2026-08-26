---
sidebar_position: 4
---

# Trading Strategies

Learn how to create and implement trading strategies using the Investing Algorithm Framework.

## Overview

Trading strategies are the core logic that determines when to buy, sell, or hold assets. The framework provides a flexible `TradingStrategy` class that allows you to implement various trading approaches using signal-based trading with built-in support for position sizing, stop losses, and take profits.

## Position Modes

Markets use `PositionMode.NETTING` by default, where a symbol has one net
direction. Backtests can opt into `PositionMode.HEDGE` to hold independent long
and short legs for the same symbol:

```python
from investing_algorithm_framework import PositionMode

app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=10_000,
    position_mode=PositionMode.HEDGE,
)
```

Both event-driven and vector backtests support `OPEN_LONG`, `CLOSE_LONG`,
`OPEN_SHORT`, and `CLOSE_SHORT` independently in HEDGE mode. Stop-loss,
take-profit, and cooldown rules are evaluated per leg, and reports include net,
gross, long, and short exposure. Live HEDGE execution is intentionally rejected
until exchange position-mode verification and leg reconciliation are supported;
use NETTING for live trading.

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
| `scaling_rules` | `List[ScalingRule]` | Position scaling rules for pyramiding and partial closes. |
| `exposure_rule` | `ExposureRule` | Caps total invested value across the whole portfolio (all symbols combined), e.g. never more than 80% invested. Singular, not a list — see [Risk Rules: ExposureRule](../Risk%20Rules/exposure-rule.md). |
| `flip_on_opposite_signal` | `bool` | When `True`, an opposite open signal closes the current position and opens the new direction on the same bar or tick. Defaults to `False`. |
| `metadata` | `Dict[str, Any]` | Dictionary for storing additional strategy information (author, version, params, etc.). |

## Creating Your First Strategy

### Basic Strategy Structure

There are two main approaches to creating strategies:

#### Approach 1: Signal-Based Strategy (Recommended)

Override `generate_signals` and yield `Signal` objects using the `signals_from_column` helper, which inspects the latest row of a boolean column and emits at most one signal per call:

```python
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize,
    SignalSide, signals_from_column,
)
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
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="eth_eur_1h",
            symbol="ETH/EUR",
            time_frame="1h",
            warmup_window=100,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.5),  # 50% of portfolio
        PositionSize(symbol="ETH", percentage=0.3),  # 30% of portfolio
    ]

    def generate_signals(self, context, data):
        """
        Yield buy/sell signals for each symbol.

        Args:
            context: Strategy context (portfolio, positions, orders).
            data: Dictionary with data source identifiers as keys.

        Yields:
            Signal: Zero or more OPEN_LONG / CLOSE_LONG signals.
        """
        # BTC signal logic
        btc_data = data["btc_eur_1h"]
        btc_ma20 = btc_data["Close"].rolling(20).mean()
        btc_data["buy_signal"] = btc_data["Close"] > btc_ma20  # above MA20
        btc_data["sell_signal"] = btc_data["Close"] < btc_ma20  # below MA20
        yield from signals_from_column(
            btc_data, "buy_signal",
            side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            btc_data, "sell_signal",
            side=SignalSide.CLOSE_LONG, symbol="BTC",
        )

        # ETH signal logic
        eth_data = data["eth_eur_1h"]
        eth_ma20 = eth_data["Close"].rolling(20).mean()
        eth_data["buy_signal"] = eth_data["Close"] > eth_ma20
        eth_data["sell_signal"] = eth_data["Close"] < eth_ma20
        yield from signals_from_column(
            eth_data, "buy_signal",
            side=SignalSide.OPEN_LONG, symbol="ETH",
        )
        yield from signals_from_column(
            eth_data, "sell_signal",
            side=SignalSide.CLOSE_LONG, symbol="ETH",
        )
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
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize,
    SignalSide, signals_from_column,
)
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
            warmup_window=60,
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

    def generate_signals(self, context, data):
        df = data["btc_eur_1h"]
        close = df["Close"]

        short_ma = close.rolling(window=self.short_window).mean()
        long_ma = close.rolling(window=self.long_window).mean()

        # Golden cross: short MA crosses above long MA
        df["buy_signal"] = (
            (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
        )
        # Death cross: short MA crosses below long MA
        df["sell_signal"] = (
            (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))
        )

        yield from signals_from_column(
            df, "buy_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "sell_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
```

### RSI Strategy with Stop Loss and Take Profit

```python
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource,
    PositionSize, StopLossRule, TakeProfitRule,
    SignalSide, signals_from_column,
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
            warmup_window=30,
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

    def generate_signals(self, context, data):
        df = data["btc_eur_4h"]
        rsi = self.calculate_rsi(df["Close"])

        # Buy when RSI crosses above oversold level
        df["buy_signal"] = (
            (rsi > self.oversold) & (rsi.shift(1) <= self.oversold)
        )
        # Sell when RSI crosses below overbought level
        df["sell_signal"] = (
            (rsi < self.overbought) & (rsi.shift(1) >= self.overbought)
        )

        yield from signals_from_column(
            df, "buy_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "sell_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
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

# Create a market order (fills at best available price)
order = self.create_market_order(
    target_symbol="BTC",
    order_side=OrderSide.BUY,
    amount=0.01,                    # Amount in target symbol
    # OR
    amount_trading_symbol=500,      # Amount in trading symbol (EUR)
    # OR
    percentage_of_portfolio=10,     # 10% of portfolio
)

# Convenience methods for market orders
self.create_market_buy_order(
    target_symbol="BTC",
    percentage_of_portfolio=10,     # Buy 10% of portfolio
)

self.create_market_sell_order(
    target_symbol="BTC",
    percentage_of_position=50,      # Sell 50% of position
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

## Position Scaling (Pyramiding & Partial Closes)

Position scaling allows your strategy to **add to an existing position** (scale in / pyramid) or **partially close a position** (scale out) based on signals. This is useful for strategies that build positions gradually or take partial profits.

### ScalingRule Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | `str` | Required | The target symbol this rule applies to. |
| `max_entries` | `int` | `1` | Maximum number of entries (including initial buy). Set to `3` to allow the initial entry plus 2 scale-ins. |
| `scale_in_percentage` | `float \| List[float]` | `100` | Size of each scale-in as a percentage of the original `PositionSize`. A single float applies the same percentage to all scale-ins. A list lets you specify a different percentage per scale-in step (e.g. `[50, 25]` → 1st add 50%, 2nd add 25%). If the list is shorter than the number of scale-ins, the last value is reused. |
| `scale_out_percentage` | `float \| List[float]` | `50` | Percentage of the current position to sell on a scale-out signal. A single float applies the same percentage to all scale-outs. A list lets you specify a different percentage per scale-out step (e.g. `[25, 50]` → 1st trim 25%, 2nd trim 50%). If the list is shorter, the last value is reused. |
| `max_position_percentage` | `float \| None` | `None` | Maximum total position size as a percentage of the portfolio. Scale-in orders are capped to respect this limit. |
| `cooldown_in_bars` | `int` | `0` | Number of bars to wait after a buy, sell, scale-in, or scale-out before the next signal for this symbol is acted upon. Useful for filtering out noise from rapid signals. Works in both vector and event-based backtests. |

### How It Works

When a `ScalingRule` is defined for a symbol, the strategy flow becomes:

```
for each symbol:
    ├─ has open orders? → SKIP (safety guardrail)
    │
    ├─ in cooldown? → SKIP all signals for this symbol
    │
    ├─ sell signal AND has position?
    │   → full exit (bypasses scaling rules — always wins)
    │
    ├─ scale-out signal AND has position AND has ScalingRule?
    │   → partial close (sell scale_out_percentage% of position)
    │
    ├─ no position?
    │   └─ buy signal? → open with full PositionSize
    │
    ├─ has position AND has ScalingRule?
    │   └─ scale-in signal AND entries < max_entries?
    │       → add PositionSize × scale_in_percentage
    │
    └─ has position, no ScalingRule?
        └─ (no action — sell signal already handled above)
```

Without a `ScalingRule`, behavior is identical to the default: one entry, one full exit. **Fully backward compatible.**

:::tip Sell always wins
A **sell signal always takes priority** over scale-out. If both fire on the same bar/step, the position is fully closed. This ensures you can always exit a position completely, regardless of scaling rules.
:::

### Signals Drive Scaling — No Extra Methods Needed

`ScalingRule` doesn't add new methods to override. It's driven entirely by the `SignalSide` values your `generate_signals` method yields via `signals_from_column`:

- **`SignalSide.OPEN_LONG`** — first entry, opens with the full `PositionSize`
- **`SignalSide.SCALE_IN`** — adds `scale_in_percentage` of the original `PositionSize` (requires an existing position, capped by `max_entries`)
- **`SignalSide.SCALE_OUT`** — partially closes `scale_out_percentage` of the current position
- **`SignalSide.CLOSE_LONG`** — full exit, always wins over `SCALE_OUT` if both fire on the same bar

Each side must be emitted explicitly. Unlike the vector engine's legacy fallback, an event-driven strategy gets **no automatic reuse** of the open signal as a scale-in signal — a plain `OPEN_LONG` signal is simply dropped while a position is already open, so you must yield a `SCALE_IN` signal for every add.

```python
class MyStrategy(TradingStrategy):
    scaling_rules = [
        ScalingRule(symbol="BTC", max_entries=3, scale_in_percentage=50),
    ]

    def generate_signals(self, context, data):
        df = data["btc_eur_1h"]
        ma20 = df["Close"].rolling(20).mean()
        df["entry_signal"] = df["Close"] > ma20
        df["exit_signal"] = df["Close"] < ma20

        # Same condition drives both the initial entry and every scale-in
        yield from signals_from_column(
            df, "entry_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "entry_signal", side=SignalSide.SCALE_IN, symbol="BTC",
        )
        yield from signals_from_column(
            df, "exit_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
```

Only add a `SCALE_OUT` signal when the conditions to **trim** a position should differ from your full-exit logic. For example:
- Buy/scale-in on RSI oversold and new highs, but full-exit only on RSI overbought
- Trim 25% when volatility spikes, independent of the exit signal

### Basic Pyramiding Example

```python
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource,
    PositionSize, ScalingRule, SignalSide, signals_from_column,
)
import pandas as pd

class PyramidingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]

    data_sources = [
        DataSource(
            identifier="btc_eur_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            warmup_window=50,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20),
    ]

    scaling_rules = [
        ScalingRule(
            symbol="BTC",
            max_entries=3,                       # Up to 3 entries total
            scale_in_percentage=[50, 25],         # 1st add 50%, 2nd add 25%
            scale_out_percentage=[25, 50],        # 1st trim 25%, 2nd trim 50%
            max_position_percentage=40,           # Never exceed 40% of portfolio
            cooldown_in_bars=3,                   # Wait 3 bars between actions
        ),
    ]

    def generate_signals(self, context, data):
        df = data["btc_eur_1h"]
        ma20 = df["Close"].rolling(20).mean()
        df["entry_signal"] = df["Close"] > ma20
        df["exit_signal"] = df["Close"] < ma20

        # Same condition drives the initial entry and every scale-in
        yield from signals_from_column(
            df, "entry_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "entry_signal", side=SignalSide.SCALE_IN, symbol="BTC",
        )
        yield from signals_from_column(
            df, "exit_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
```

In this example:
- **Entry 1**: Opens at 20% of portfolio (full `PositionSize`)
- **Entry 2**: Adds 10% (50% of 20%) — after waiting 3 bars
- **Entry 3**: Adds 5% (25% of 20%) — after waiting 3 bars, now at 35%
- No further scale-ins allowed (max_entries=3)

The `cooldown_in_bars=3` prevents back-to-back signals from triggering on every bar, filtering out noise.

### Separate Scale-In and Scale-Out Signals

For more control, yield distinct `SignalSide.SCALE_IN` / `SignalSide.SCALE_OUT` signals from different conditions than your open/close signals:

```python
class AdvancedScalingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]

    data_sources = [
        DataSource(
            identifier="btc_eur_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            warmup_window=50,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20),
    ]

    scaling_rules = [
        ScalingRule(
            symbol="BTC",
            max_entries=3,
            scale_in_percentage=50,
            scale_out_percentage=25,  # Sell 25% on scale-out
        ),
    ]

    def generate_signals(self, context, data):
        df = data["btc_eur_1h"]
        close = df["Close"]
        rsi = self._calculate_rsi(close)

        # Initial entry / full exit: RSI crosses oversold / overbought
        df["entry_signal"] = (rsi > 30) & (rsi.shift(1) <= 30)
        df["exit_signal"] = (rsi < 70) & (rsi.shift(1) >= 70)

        # Scale-in: price makes a new high
        rolling_high = close.rolling(20).max()
        df["scale_in_signal"] = close >= rolling_high

        # Scale-out: volatility spikes
        vol = close.pct_change().rolling(20).std()
        avg_vol = vol.rolling(50).mean()
        df["scale_out_signal"] = vol > avg_vol * 2

        yield from signals_from_column(
            df, "entry_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "exit_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "scale_in_signal", side=SignalSide.SCALE_IN, symbol="BTC",
        )
        yield from signals_from_column(
            df, "scale_out_signal", side=SignalSide.SCALE_OUT, symbol="BTC",
        )

    def _calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
```

**Signal priority:**
- `SCALE_IN` requires an existing position and an available `ScalingRule` entry slot — there is no fallback to the `OPEN_LONG` condition, so emit it explicitly whenever it differs
- `SCALE_OUT` requires an existing position; emitting no `SCALE_OUT` signal means no partial trims ever happen
- **`CLOSE_LONG` always takes priority over `SCALE_OUT`**: if both fire on the same bar, the position is fully closed
- Cooldown applies after any action (open, close, scale-in, scale-out) — see `cooldown_in_bars`

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
def generate_signals(self, context, data):
    df = data["btc_eur_1h"]

    if len(df) < self.required_window:
        # Not enough data yet — yield no signals
        return

    # Generate signals...
```

## Next Steps

Now that you understand how to create strategies, learn about:
- [Orders](orders) - Different order types and execution methods
- [Backtesting](backtesting) - Test your strategies with historical data
- [Data Sources](data-sources) - Configure market data for your strategies
