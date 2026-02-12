---
sidebar_position: 3
---
sidebar_position: 3
---

# Backtest Data

Learn how to retrieve and work with backtest data for analysis, visualization, and strategy development.

## Overview

When developing trading strategies, you often need access to the raw market data used during backtesting. This is particularly important for:

- **Visualizing strategy signals** overlaid on price charts
- **Debugging indicator calculations** that depend on warmup periods
- **Creating custom analysis reports** with price data and indicators
- **Validating data quality** before running backtests

The `get_backtest_data` method provides a convenient way to retrieve all data sources with their corresponding data for a given strategy and backtest window.

## The `get_backtest_data` Method

### Method Signature

```python
def get_backtest_data(
    self,
    strategy: TradingStrategy,
    backtest_date_range: BacktestDateRange,
    show_progress: bool = True,
    fill_missing_data: bool = True,
) -> Dict[str, Any]
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | `TradingStrategy` | Required | The strategy containing the data sources to retrieve data for. |
| `backtest_date_range` | `BacktestDateRange` | Required | The date range for the backtest window. |
| `show_progress` | `bool` | `True` | Whether to show progress bars during data retrieval. |
| `fill_missing_data` | `bool` | `True` | If `True`, missing time series data entries will be filled automatically. |

### Returns

A dictionary where:
- **Keys** are data source identifiers (e.g., `"btc_data"`, `"eth_eur_1h"`)
- **Values** are the corresponding data (typically pandas DataFrames)

## Why This Matters for Quant Developers

### 1. Warmup Window Handling

Many technical indicators require historical data to "warm up" before producing valid signals. For example:
- A 200-period moving average needs 200 data points before it can be calculated
- RSI typically uses 14 periods of data
- MACD requires even more historical data for its components

When you define a `warmup_window` in your `DataSource`, the `get_backtest_data` method automatically includes this additional historical data. This means the data you retrieve for visualization will match exactly what your strategy sees during backtesting.

```python
DataSource(
    identifier="btc_data",
    symbol="BTC/EUR",
    time_frame="1h",
    warmup_window=200,  # Strategy needs 200 candles for indicators
    market="BITVAVO"
)
```

### 2. Consistent Data for Visualization

When creating charts that overlay indicators on price data, you need the exact same data your strategy used. The `get_backtest_data` method ensures consistency by:

- Using the same data providers as the backtest
- Applying the same warmup window calculations
- Handling missing data the same way

### 3. Debugging and Validation

Before running a full backtest, you can inspect the data to:
- Verify data quality and completeness
- Check that indicators calculate correctly
- Validate that signals appear at expected times

## Basic Usage

### Simple Example

```python
from investing_algorithm_framework import (
    create_app, TradingStrategy, BacktestDateRange, 
    DataSource, TimeUnit, PortfolioConfiguration
)
from datetime import datetime, timezone

# Define your strategy with data sources
class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    
    data_sources = [
        DataSource(
            identifier="btc_data",
            symbol="BTC/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        )
    ]
    
    def generate_buy_signals(self, data):
        # Strategy logic here
        pass
    
    def generate_sell_signals(self, data):
        # Strategy logic here
        pass

# Create and configure the app
app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        initial_balance=10000,
        market="BITVAVO",
        trading_symbol="EUR"
    )
)

# Define backtest range
backtest_range = BacktestDateRange(
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
)

# Get the backtest data
data = app.get_backtest_data(
    strategy=MyStrategy(),
    backtest_date_range=backtest_range
)

# Access the data by identifier
btc_df = data["btc_data"]
print(f"Data shape: {btc_df.shape}")
print(f"Date range: {btc_df.index.min()} to {btc_df.index.max()}")
print(btc_df.head())
```

### Multiple Data Sources

```python
class MultiAssetStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    
    data_sources = [
        DataSource(
            identifier="btc_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            warmup_window=200,
            market="BITVAVO"
        ),
        DataSource(
            identifier="eth_1h",
            symbol="ETH/EUR",
            time_frame="1h",
            warmup_window=200,
            market="BITVAVO"
        ),
        DataSource(
            identifier="btc_4h",
            symbol="BTC/EUR",
            time_frame="4h",
            warmup_window=50,
            market="BITVAVO"
        )
    ]

# Get all data sources at once
data = app.get_backtest_data(
    strategy=MultiAssetStrategy(),
    backtest_date_range=backtest_range
)

# Access each data source
btc_hourly = data["btc_1h"]
eth_hourly = data["eth_1h"]
btc_4hourly = data["btc_4h"]
```

## Visualization Examples

### Plotting Price with Moving Averages

```python
import matplotlib.pyplot as plt
import pandas as pd

# Get the data
data = app.get_backtest_data(
    strategy=MyStrategy(),
    backtest_date_range=backtest_range
)

df = data["btc_data"]

# Calculate indicators (same as your strategy would)
df["SMA_20"] = df["Close"].rolling(window=20).mean()
df["SMA_50"] = df["Close"].rolling(window=50).mean()
df["SMA_200"] = df["Close"].rolling(window=200).mean()

# Plot
fig, ax = plt.subplots(figsize=(14, 7))

ax.plot(df.index, df["Close"], label="BTC/EUR", alpha=0.7)
ax.plot(df.index, df["SMA_20"], label="SMA 20", linewidth=1)
ax.plot(df.index, df["SMA_50"], label="SMA 50", linewidth=1)
ax.plot(df.index, df["SMA_200"], label="SMA 200", linewidth=1)

ax.set_title("BTC/EUR with Moving Averages")
ax.set_xlabel("Date")
ax.set_ylabel("Price (EUR)")
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

### Visualizing Buy/Sell Signals

```python
import matplotlib.pyplot as plt

# Get backtest data
data = app.get_backtest_data(
    strategy=MyStrategy(),
    backtest_date_range=backtest_range
)

df = data["btc_data"]

# Calculate your indicators
short_ma = df["Close"].rolling(window=20).mean()
long_ma = df["Close"].rolling(window=50).mean()

# Generate signals (same logic as your strategy)
buy_signals = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
sell_signals = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))

# Plot
fig, ax = plt.subplots(figsize=(14, 7))

ax.plot(df.index, df["Close"], label="Price", alpha=0.7)
ax.plot(df.index, short_ma, label="MA 20", linewidth=1)
ax.plot(df.index, long_ma, label="MA 50", linewidth=1)

# Mark buy signals
buy_dates = df.index[buy_signals]
buy_prices = df.loc[buy_signals, "Close"]
ax.scatter(buy_dates, buy_prices, marker="^", color="green", 
           s=100, label="Buy Signal", zorder=5)

# Mark sell signals
sell_dates = df.index[sell_signals]
sell_prices = df.loc[sell_signals, "Close"]
ax.scatter(sell_dates, sell_prices, marker="v", color="red", 
           s=100, label="Sell Signal", zorder=5)

ax.set_title("Strategy Signals Visualization")
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

### Creating a Multi-Panel Chart

```python
import matplotlib.pyplot as plt
from pyindicators import rsi, ema

# Get data
data = app.get_backtest_data(
    strategy=MyStrategy(),
    backtest_date_range=backtest_range
)

df = data["btc_data"]

# Calculate indicators
df = ema(df, period=20, source_column="Close", result_column="EMA_20")
df = ema(df, period=50, source_column="Close", result_column="EMA_50")
df = rsi(df, period=14, source_column="Close", result_column="RSI")

# Create multi-panel figure
fig, axes = plt.subplots(3, 1, figsize=(14, 10), 
                          gridspec_kw={'height_ratios': [3, 1, 1]})

# Price panel
axes[0].plot(df.index, df["Close"], label="Price", alpha=0.7)
axes[0].plot(df.index, df["EMA_20"], label="EMA 20")
axes[0].plot(df.index, df["EMA_50"], label="EMA 50")
axes[0].set_title("BTC/EUR Price with EMAs")
axes[0].legend(loc="upper left")
axes[0].grid(True, alpha=0.3)

# Volume panel
axes[1].bar(df.index, df["Volume"], alpha=0.7, color="steelblue")
axes[1].set_title("Volume")
axes[1].grid(True, alpha=0.3)

# RSI panel
axes[2].plot(df.index, df["RSI"], color="purple")
axes[2].axhline(y=70, color="red", linestyle="--", alpha=0.5)
axes[2].axhline(y=30, color="green", linestyle="--", alpha=0.5)
axes[2].fill_between(df.index, 30, 70, alpha=0.1)
axes[2].set_title("RSI (14)")
axes[2].set_ylim(0, 100)
axes[2].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

## Integration with Jupyter Notebooks

The `get_backtest_data` method is particularly useful in Jupyter notebooks for interactive analysis:

```python
# In a Jupyter notebook cell
from investing_algorithm_framework import create_app, BacktestDateRange
from datetime import datetime, timezone

# Setup
app = create_app()
# ... configure app ...

# Get data for analysis
data = app.get_backtest_data(
    strategy=my_strategy,
    backtest_date_range=BacktestDateRange(
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 12, 31, tzinfo=timezone.utc)
    )
)

# Explore in notebook
df = data["btc_data"]
df.describe()
```

## Comparing Backtest Results with Raw Data

A powerful use case is comparing your backtest results with the underlying data:

```python
# Run backtest
backtest = app.run_vector_backtest(
    strategy=my_strategy,
    backtest_date_range=backtest_range,
    initial_amount=10000
)

# Get the same data used in backtest
data = app.get_backtest_data(
    strategy=my_strategy,
    backtest_date_range=backtest_range
)

# Get trades from backtest
trades = backtest.get_trades()

# Plot trades on price chart
df = data["btc_data"]

fig, ax = plt.subplots(figsize=(14, 7))
ax.plot(df.index, df["Close"], label="Price", alpha=0.7)

for trade in trades:
    # Mark entry
    ax.axvline(x=trade.opened_at, color="green", alpha=0.3, linestyle="--")
    # Mark exit
    if trade.closed_at:
        ax.axvline(x=trade.closed_at, color="red", alpha=0.3, linestyle="--")

ax.set_title("Backtest Trades on Price Chart")
ax.legend()
plt.show()
```

## Best Practices

### 1. Use Consistent Warmup Windows

Ensure your visualization uses the same `warmup_window` as your strategy:

```python
# In your strategy
data_sources = [
    DataSource(
        identifier="btc_data",
        warmup_window=200,  # Enough for 200-period indicators
        ...
    )
]
```

### 2. Handle Missing Data Appropriately

The `fill_missing_data` parameter controls whether gaps in the data are filled:

```python
# Fill missing data (default)
data = app.get_backtest_data(
    strategy=my_strategy,
    backtest_date_range=backtest_range,
    fill_missing_data=True
)

# Keep raw data with gaps (for data quality analysis)
data = app.get_backtest_data(
    strategy=my_strategy,
    backtest_date_range=backtest_range,
    fill_missing_data=False
)
```

### 3. Cache Data for Repeated Analysis

If you're doing multiple analyses on the same data:

```python
# Fetch once
data = app.get_backtest_data(
    strategy=my_strategy,
    backtest_date_range=backtest_range
)

# Save to disk for later use
data["btc_data"].to_csv("btc_backtest_data.csv")

# Or use pickle for faster loading
import pickle
with open("backtest_data.pkl", "wb") as f:
    pickle.dump(data, f)
```

## Error Handling

The method will raise an `OperationalException` if:
- No data sources are defined in the strategy
- Data cannot be retrieved for a data source

```python
from investing_algorithm_framework import OperationalException

try:
    data = app.get_backtest_data(
        strategy=my_strategy,
        backtest_date_range=backtest_range
    )
except OperationalException as e:
    print(f"Error retrieving data: {e}")
```

## Next Steps

- Learn about [Data Sources](data-sources) to configure your data inputs
- Explore [Backtesting](../Getting%20Started/backtesting) to run full strategy tests
- Check out [Trading Strategies](../Getting%20Started/strategies) to build your trading logic
