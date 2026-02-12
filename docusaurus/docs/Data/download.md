---
sidebar_position: 1
---

# Download Data

Learn how to download and manage market data for backtesting and analysis.

## Overview

The framework provides built-in data downloading capabilities through the `download` function that allows you to fetch historical market data from various exchanges via the CCXT library. This data is essential for backtesting strategies and can also be used for analysis.

## Getting Started with Data Download

### Basic Data Download

```python
from investing_algorithm_framework import download

# Download Bitcoin price data from Bitvavo
data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01"
)

print(f"Downloaded {len(data)} data points")
print(data.head())
```

### Download Function Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | `str` | Required | The trading pair to download (e.g., `"BTC/EUR"`, `"ETH/USDT"`). |
| `market` | `str` | `None` | The exchange/market to download from (e.g., `"bitvavo"`, `"binance"`). |
| `time_frame` | `str` | `None` | The candlestick timeframe (e.g., `"1h"`, `"4h"`, `"1d"`). |
| `start_date` | `datetime` or `str` | `None` | Start date for the data range. |
| `end_date` | `datetime` or `str` | `None` | End date for the data range. |
| `warmup_window` | `int` | `200` | Number of additional data points to fetch before start_date. |
| `data_type` | `DataType` or `str` | `DataType.OHLCV` | Type of data to download. |
| `pandas` | `bool` | `True` | Return data as pandas DataFrame (vs polars). |
| `save` | `bool` | `True` | Whether to save downloaded data to disk. |
| `storage_path` | `str` or `Path` | `None` | Directory to save downloaded data. |

> ⚠️ **Deprecation Notice**: The `window_size` parameter is deprecated and will be removed in release 0.8.0. Please use `warmup_window` instead.

## Supported Exchanges

The framework uses CCXT under the hood, supporting many cryptocurrency exchanges:

### Bitvavo
```python
from investing_algorithm_framework import download

bitvavo_data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01"
)
```

### Binance
```python
binance_data = download(
    symbol="BTC/USDT",
    market="binance",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01"
)
```

### Coinbase
```python
coinbase_data = download(
    symbol="BTC/EUR",
    market="coinbase",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01"
)
```

### Kraken
```python
kraken_data = download(
    symbol="BTC/EUR",
    market="kraken",
    time_frame="1d",
    start_date="2024-01-01",
    end_date="2024-06-01"
)
```

## Timeframes

### Available Timeframes

The framework supports standard CCXT timeframes:

| Timeframe | Description |
|-----------|-------------|
| `"1m"` | 1 minute |
| `"5m"` | 5 minutes |
| `"15m"` | 15 minutes |
| `"30m"` | 30 minutes |
| `"1h"` | 1 hour |
| `"2h"` | 2 hours |
| `"4h"` | 4 hours |
| `"1d"` | 1 day |
| `"1w"` | 1 week |

```python
from investing_algorithm_framework import download

# Download different timeframes
for tf in ["1h", "4h", "1d"]:
    data = download(
        symbol="BTC/EUR",
        market="bitvavo",
        time_frame=tf,
        start_date="2024-01-01",
        end_date="2024-01-31"
    )
    print(f"Timeframe {tf}: {len(data)} candles")
```

## Data Storage

### Automatic Storage

When `save=True` (default), data is automatically saved to CSV files:

```python
from investing_algorithm_framework import download

# Download and save to default location
data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01",
    save=True
)
```

### Custom Storage Path

```python
# Download and save to custom directory
data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01",
    save=True,
    storage_path="./my_data/"
)
```

### Get Storage Path

Use `create_data_storage_path` to determine where data will be saved:

```python
from investing_algorithm_framework import create_data_storage_path
from datetime import datetime, timezone

path = create_data_storage_path(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    storage_path="./data/"
)

print(f"Data will be saved to: {path}")
# Output: ./data/OHLCV_BTC-EUR_BITVAVO_1h_2024-01-01-00-00_2024-06-01-00-00.csv
```

## Advanced Usage

### Download with Result Object

Use `download_v2` to get both data and file path:

```python
from investing_algorithm_framework import download_v2

result = download_v2(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01",
    storage_path="./data/"
)

print(f"Data shape: {result.data.shape}")
print(f"Saved to: {result.path}")
```

### Using Warmup Window

The `warmup_window` parameter fetches additional historical data before your start date, which is useful for indicator calculations:

```python
from investing_algorithm_framework import download

# Download with 100 extra candles for indicator warmup
data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01",
    warmup_window=100  # Fetch 100 extra candles before start_date
)
```

### Download Multiple Symbols

```python
from investing_algorithm_framework import download

symbols = ["BTC/EUR", "ETH/EUR", "ADA/EUR"]
market = "bitvavo"
time_frame = "4h"

data_dict = {}
for symbol in symbols:
    data_dict[symbol] = download(
        symbol=symbol,
        market=market,
        time_frame=time_frame,
        start_date="2024-01-01",
        end_date="2024-06-01"
    )
    print(f"Downloaded {symbol}: {len(data_dict[symbol])} candles")
```

### Progress Tracking with Multiple Downloads

```python
from investing_algorithm_framework import download
from tqdm import tqdm

symbols = ["BTC/EUR", "ETH/EUR", "ADA/EUR", "DOT/EUR", "LINK/EUR"]

data_dict = {}
for symbol in tqdm(symbols, desc="Downloading data"):
    try:
        data_dict[symbol] = download(
            symbol=symbol,
            market="bitvavo",
            time_frame="1h",
            start_date="2024-01-01",
            end_date="2024-06-01"
        )
    except Exception as e:
        print(f"Failed to download {symbol}: {e}")

print(f"Successfully downloaded {len(data_dict)} symbols")
```

## Data Format

Downloaded data is returned as a pandas DataFrame with the following columns:

| Column | Description |
|--------|-------------|
| `Datetime` | Timestamp (index) in UTC |
| `Open` | Opening price |
| `High` | Highest price |
| `Low` | Lowest price |
| `Close` | Closing price |
| `Volume` | Trading volume |

```python
from investing_algorithm_framework import download

data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-01-02"
)

print(data.columns.tolist())
# ['Open', 'High', 'Low', 'Close', 'Volume']

print(data.index.name)
# 'Datetime'
```

## Data Validation

### Basic Validation

```python
import pandas as pd

def validate_ohlcv_data(data, symbol):
    """Validate downloaded OHLCV data quality"""
    
    if data is None or len(data) == 0:
        raise ValueError(f"No data downloaded for {symbol}")
    
    # Check for required columns
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_cols if col not in data.columns]
    
    if missing_cols:
        raise ValueError(f"Missing columns: {missing_cols}")
    
    # Check for null values
    null_counts = data[required_cols].isnull().sum()
    if null_counts.sum() > 0:
        print(f"Warning: {symbol} has null values: {null_counts.to_dict()}")
    
    # Validate price relationships (High >= Low, etc.)
    invalid_rows = (
        (data['High'] < data['Low']) |
        (data['High'] < data['Open']) |
        (data['High'] < data['Close']) |
        (data['Low'] > data['Open']) |
        (data['Low'] > data['Close'])
    )
    
    if invalid_rows.any():
        print(f"Warning: {symbol} has {invalid_rows.sum()} invalid OHLC rows")
    
    print(f"✓ {symbol} data validation passed")
    return True

# Download and validate
from investing_algorithm_framework import download

data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-01-31"
)

validate_ohlcv_data(data, "BTC/EUR")
```

## Using Downloaded Data for Backtesting

Downloaded data can be used with `PandasOHLCVDataProvider` for backtesting:

```python
from investing_algorithm_framework import (
    create_app, download, TradingStrategy, DataSource,
    BacktestDateRange, PortfolioConfiguration, TimeUnit
)
from investing_algorithm_framework.infrastructure import PandasOHLCVDataProvider
from datetime import datetime, timezone

# Download data
data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="4h",
    start_date="2024-01-01",
    end_date="2024-06-01",
    warmup_window=100
)

# Create data provider from downloaded data
data_provider = PandasOHLCVDataProvider(
    dataframe=data,
    symbol="BTC/EUR",
    time_frame="4h",
    market="bitvavo"
)

# Define strategy
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
        df = data["btc_data"]
        ma20 = df["Close"].rolling(20).mean()
        return {"BTC": df["Close"] > ma20}
    
    def generate_sell_signals(self, data):
        df = data["btc_data"]
        ma20 = df["Close"].rolling(20).mean()
        return {"BTC": df["Close"] < ma20}

# Setup app with custom data provider
app = create_app()
app.add_data_provider(data_provider, priority=1)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        initial_balance=10000,
        market="BITVAVO",
        trading_symbol="EUR"
    )
)

# Run backtest
backtest = app.run_vector_backtest(
    strategy=MyStrategy(),
    backtest_date_range=BacktestDateRange(
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
    ),
    initial_amount=10000
)
```

## Best Practices

### 1. Use Appropriate Warmup Windows

Always include enough historical data for your indicators:

```python
# If using 200-period moving average, use warmup_window >= 200
data = download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01",
    warmup_window=250  # Extra buffer
)
```

### 2. Handle Download Errors

```python
from investing_algorithm_framework import download

def safe_download(symbol, market, **kwargs):
    """Download data with error handling"""
    try:
        return download(symbol=symbol, market=market, **kwargs)
    except Exception as e:
        print(f"Failed to download {symbol} from {market}: {e}")
        return None

data = safe_download(
    symbol="BTC/EUR",
    market="bitvavo",
    time_frame="1h",
    start_date="2024-01-01",
    end_date="2024-06-01"
)
```

### 3. Cache Downloaded Data

Save data locally to avoid repeated downloads:

```python
import os
from investing_algorithm_framework import download, create_data_storage_path
from datetime import datetime, timezone
import pandas as pd

def get_or_download_data(symbol, market, time_frame, start_date, end_date, storage_path="./data/"):
    """Get data from cache or download if not available"""
    
    # Create expected file path
    file_path = create_data_storage_path(
        symbol=symbol,
        market=market,
        time_frame=time_frame,
        start_date=start_date,
        end_date=end_date,
        storage_path=storage_path
    )
    
    # Check if file exists
    if os.path.exists(file_path):
        print(f"Loading cached data from {file_path}")
        return pd.read_csv(file_path, index_col=0, parse_dates=True)
    
    # Download and save
    print(f"Downloading data for {symbol}...")
    data = download(
        symbol=symbol,
        market=market,
        time_frame=time_frame,
        start_date=start_date,
        end_date=end_date,
        save=True,
        storage_path=storage_path
    )
    
    return data
```

## Next Steps

- Learn about [Data Sources](data-sources) for strategy development
- Explore [Backtest Data](backtest_data) to retrieve data for visualization
- Check out [Trading Strategies](../Getting%20Started/strategies) for strategy implementation
