---
sidebar_position: 1
---

# Download Data

Learn how to download and manage market data for backtesting and live trading.

## Overview

The framework provides built-in data downloading capabilities that allow you to fetch historical market data from various sources. This data is essential for backtesting strategies and can also be used for live analysis.

## Getting Started with Data Download

### Basic Data Download

```python
from investing_algorithm_framework import download_data

# Download Bitcoin price data
data = download_data(
    symbols=["BTC/USDT"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1d"
)

print(f"Downloaded {len(data)} data points")
```

### Multiple Symbols

```python
# Download data for multiple cryptocurrencies
symbols = ["BTC/USDT", "ETH/USDT", "ADA/USDT", "DOT/USDT"]

data = download_data(
    symbols=symbols,
    start_date="2023-01-01", 
    end_date="2023-12-31",
    timeframe="1h",
    data_source="binance"
)

# Access data for each symbol
for symbol in symbols:
    symbol_data = data[symbol]
    print(f"{symbol}: {len(symbol_data)} records")
```

## Data Sources

### Supported Exchanges

The framework supports multiple cryptocurrency exchanges:

```python
# Binance (default)
binance_data = download_data(
    symbols=["BTC/USDT"],
    data_source="binance",
    timeframe="1d",
    start_date="2023-01-01"
)

# Coinbase Pro
coinbase_data = download_data(
    symbols=["BTC-USD"],
    data_source="coinbase",
    timeframe="1h", 
    start_date="2023-01-01"
)

# Kraken
kraken_data = download_data(
    symbols=["XBTUSD"],
    data_source="kraken",
    timeframe="1d",
    start_date="2023-01-01"
)
```

### Stock Market Data

```python
# Download stock data using yfinance
stock_data = download_data(
    symbols=["AAPL", "GOOGL", "MSFT"],
    data_source="yahoo",
    timeframe="1d",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

## Timeframes

### Available Timeframes

```python
timeframes = [
    "1m",   # 1 minute
    "5m",   # 5 minutes  
    "15m",  # 15 minutes
    "30m",  # 30 minutes
    "1h",   # 1 hour
    "4h",   # 4 hours
    "1d",   # 1 day
    "1w",   # 1 week
    "1M"    # 1 month
]

# Download different timeframes
for tf in ["1h", "4h", "1d"]:
    data = download_data(
        symbols=["BTC/USDT"],
        timeframe=tf,
        start_date="2023-01-01",
        end_date="2023-01-31"
    )
    print(f"Timeframe {tf}: {len(data['BTC/USDT'])} candles")
```

## Data Storage

### CSV Storage

```python
# Download and save to CSV
data = download_data(
    symbols=["BTC/USDT", "ETH/USDT"],
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-12-31",
    save_to_csv=True,
    csv_directory="./market_data/"
)

# Files will be saved as:
# ./market_data/BTC_USDT_1h_20230101_20231231.csv
# ./market_data/ETH_USDT_1h_20230101_20231231.csv
```

### Database Storage

```python
# Download and save to database
from investing_algorithm_framework import create_app

app = create_app()

# Download data directly to app database
app.download_data(
    symbols=["BTC/USDT"],
    timeframe="1d",
    start_date="2023-01-01",
    end_date="2023-12-31"
)

# Data is now available for backtesting
results = app.run_backtest(
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### Custom Storage

```python
import pandas as pd

class CustomDataStorage:
    def __init__(self, storage_path):
        self.storage_path = storage_path
    
    def save_data(self, symbol, data):
        """Save data with custom format"""
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data)
        
        # Add metadata
        df.attrs['symbol'] = symbol
        df.attrs['downloaded_at'] = pd.Timestamp.now()
        
        # Save with compression
        filename = f"{symbol.replace('/', '_')}.parquet"
        filepath = os.path.join(self.storage_path, filename)
        df.to_parquet(filepath, compression='snappy')
        
        print(f"Saved {symbol} data to {filepath}")

# Use custom storage
storage = CustomDataStorage("./custom_data/")

data = download_data(
    symbols=["BTC/USDT"],
    timeframe="1h",
    start_date="2023-01-01"
)

storage.save_data("BTC/USDT", data["BTC/USDT"])
```

## Advanced Data Download

### Progress Tracking

```python
from tqdm import tqdm

def download_with_progress(symbols, **kwargs):
    """Download data with progress bar"""
    
    results = {}
    
    for symbol in tqdm(symbols, desc="Downloading data"):
        try:
            data = download_data(
                symbols=[symbol],
                **kwargs
            )
            results[symbol] = data[symbol]
            
        except Exception as e:
            print(f"Failed to download {symbol}: {e}")
            results[symbol] = None
    
    return results

# Download large number of symbols with progress
crypto_symbols = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT", 
    "DOT/USDT", "LINK/USDT", "XRP/USDT", "LTC/USDT"
]

data = download_with_progress(
    crypto_symbols,
    timeframe="1d",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### Retry Logic

```python
import time
from typing import Optional

def robust_download(symbols, max_retries=3, retry_delay=5, **kwargs):
    """Download data with retry logic"""
    
    results = {}
    
    for symbol in symbols:
        for attempt in range(max_retries):
            try:
                data = download_data(symbols=[symbol], **kwargs)
                results[symbol] = data[symbol]
                break
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {symbol}: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to download {symbol} after {max_retries} attempts")
                    results[symbol] = None
    
    return results
```

### Data Validation

```python
def validate_data(data, symbol):
    """Validate downloaded data quality"""
    
    if not data or len(data) == 0:
        raise ValueError(f"No data downloaded for {symbol}")
    
    df = pd.DataFrame(data)
    
    # Check for required columns
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing columns in {symbol} data: {missing_columns}")
    
    # Check for null values
    null_counts = df[required_columns].isnull().sum()
    if null_counts.sum() > 0:
        print(f"Warning: {symbol} has null values: {null_counts.to_dict()}")
    
    # Check for duplicate timestamps
    if df.index.duplicated().any():
        print(f"Warning: {symbol} has duplicate timestamps")
    
    # Validate price relationships
    invalid_ohlc = (
        (df['high'] < df['low']) |
        (df['high'] < df['open']) |
        (df['high'] < df['close']) |
        (df['low'] > df['open']) |
        (df['low'] > df['close'])
    )
    
    if invalid_ohlc.any():
        print(f"Warning: {symbol} has invalid OHLC relationships")
    
    print(f"✓ {symbol} data validation passed")
    return True

# Download and validate
data = download_data(
    symbols=["BTC/USDT"],
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-01-31"
)

for symbol, symbol_data in data.items():
    validate_data(symbol_data, symbol)
```

## Data Management

### Data Updates

```python
class DataManager:
    def __init__(self, data_directory):
        self.data_directory = data_directory
    
    def update_data(self, symbols, timeframe="1d"):
        """Update existing data with latest records"""
        
        for symbol in symbols:
            # Check existing data
            existing_data = self.load_existing_data(symbol, timeframe)
            
            if existing_data is not None:
                last_date = existing_data.index[-1]
                start_date = last_date + pd.Timedelta(days=1)
            else:
                start_date = "2020-01-01"  # Default start date
            
            # Download new data
            new_data = download_data(
                symbols=[symbol],
                timeframe=timeframe,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=pd.Timestamp.now().strftime('%Y-%m-%d')
            )
            
            if existing_data is not None:
                # Merge with existing data
                combined_data = pd.concat([existing_data, new_data[symbol]])
                combined_data = combined_data[~combined_data.index.duplicated(keep='last')]
            else:
                combined_data = pd.DataFrame(new_data[symbol])
            
            # Save updated data
            self.save_data(symbol, timeframe, combined_data)
            print(f"Updated {symbol} data")
    
    def load_existing_data(self, symbol, timeframe):
        """Load existing data from storage"""
        filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"
        filepath = os.path.join(self.data_directory, filename)
        
        if os.path.exists(filepath):
            return pd.read_csv(filepath, index_col=0, parse_dates=True)
        return None
    
    def save_data(self, symbol, timeframe, data):
        """Save data to storage"""
        filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"
        filepath = os.path.join(self.data_directory, filename)
        data.to_csv(filepath)

# Usage
data_manager = DataManager("./market_data/")
data_manager.update_data(["BTC/USDT", "ETH/USDT"], timeframe="1d")
```

### Data Cleanup

```python
def cleanup_data(data):
    """Clean and prepare market data"""
    
    df = pd.DataFrame(data)
    
    # Remove duplicates
    df = df[~df.index.duplicated(keep='last')]
    
    # Forward fill missing values
    df = df.fillna(method='ffill')
    
    # Remove outliers (prices that differ more than 20% from previous candle)
    for col in ['open', 'high', 'low', 'close']:
        price_change = df[col].pct_change().abs()
        outliers = price_change > 0.2
        
        if outliers.any():
            print(f"Removing {outliers.sum()} outliers from {col}")
            df.loc[outliers, col] = df.loc[outliers, col].shift(1)
    
    # Ensure volume is positive
    df['volume'] = df['volume'].abs()
    
    return df.to_dict('records')

# Download and clean data
raw_data = download_data(
    symbols=["BTC/USDT"],
    timeframe="1h",
    start_date="2023-01-01"
)

clean_data = {}
for symbol, data in raw_data.items():
    clean_data[symbol] = cleanup_data(data)
```

## Command Line Interface

### CLI Download Tool

```bash
# Download data via command line
python -m investing_algorithm_framework download \
    --symbols BTC/USDT ETH/USDT \
    --timeframe 1d \
    --start-date 2023-01-01 \
    --end-date 2023-12-31 \
    --output ./data/
```

### Scheduled Downloads

```python
# Create a task for regular data downloads
from investing_algorithm_framework import Task

class DataDownloadTask(Task):
    def __init__(self):
        super().__init__(
            name="data_download",
            interval="daily",
            time="01:00"  # Run at 1 AM daily
        )
        self.symbols = ["BTC/USDT", "ETH/USDT", "ADA/USDT"]
    
    def run(self, algorithm):
        """Download latest data daily"""
        
        # Get yesterday's date
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Download data for yesterday
        data = download_data(
            symbols=self.symbols,
            timeframe="1h",
            start_date=yesterday,
            end_date=yesterday,
            save_to_csv=True,
            csv_directory="./daily_data/"
        )
        
        print(f"Downloaded data for {len(self.symbols)} symbols")

# Register the task
app = create_app()
app.add_task(DataDownloadTask())
```

## Best Practices

### 1. Rate Limiting

```python
import time

def download_with_rate_limit(symbols, rate_limit=0.5, **kwargs):
    """Download data with rate limiting to avoid API limits"""
    
    results = {}
    
    for i, symbol in enumerate(symbols):
        if i > 0:
            time.sleep(rate_limit)  # Wait between requests
        
        data = download_data(symbols=[symbol], **kwargs)
        results[symbol] = data[symbol]
        
        print(f"Downloaded {symbol} ({i+1}/{len(symbols)})")
    
    return results
```

### 2. Error Handling

```python
def safe_download(symbols, **kwargs):
    """Download data with comprehensive error handling"""
    
    successful = {}
    failed = {}
    
    for symbol in symbols:
        try:
            data = download_data(symbols=[symbol], **kwargs)
            successful[symbol] = data[symbol]
            
        except Exception as e:
            failed[symbol] = str(e)
            print(f"Failed to download {symbol}: {e}")
    
    print(f"Successfully downloaded: {len(successful)} symbols")
    print(f"Failed downloads: {len(failed)} symbols")
    
    return successful, failed
```

### 3. Data Backup

```python
def backup_data(data_directory, backup_directory):
    """Backup downloaded data"""
    
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_directory, f"data_backup_{timestamp}")
    
    shutil.copytree(data_directory, backup_path)
    print(f"Data backed up to {backup_path}")
```

## Next Steps

With market data downloaded, you can now:

1. **Explore [Market Data Sources](market-data-sources)** to understand different data providers
2. **Learn about [Multiple Data Sources](multiple-market-data-sources)** for comprehensive analysis
3. **Start backtesting** your strategies with the downloaded data

Remember to regularly update your data to ensure your backtests and live trading use the most current market information!
