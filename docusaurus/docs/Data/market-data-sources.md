---
sidebar_position: 2
---

# Market Data Sources

Understand the different market data sources available and how to configure them.

## Overview

The Investing Algorithm Framework supports multiple market data sources, allowing you to access real-time and historical data from various exchanges and providers. This flexibility enables you to choose the best data source for your specific trading needs.

## Supported Data Sources

### Cryptocurrency Exchanges

#### Binance
```python
from investing_algorithm_framework import CCXTOHLCVDataProvider

# Binance data provider
binance_provider = CCXTOHLCVDataProvider(
    exchange_name="binance",
    symbols=["BTC/USDT", "ETH/USDT"],
    timeframes=["1m", "1h", "1d"]
)
```

#### Coinbase Pro
```python
coinbase_provider = CCXTOHLCVDataProvider(
    exchange_name="coinbasepro",
    symbols=["BTC-USD", "ETH-USD"],
    timeframes=["1m", "1h", "1d"]
)
```

#### Kraken
```python
kraken_provider = CCXTOHLCVDataProvider(
    exchange_name="kraken",
    symbols=["XBTUSD", "ETHUSD"],
    timeframes=["1m", "1h", "1d"]
)
```

### Stock Market Data

#### Yahoo Finance
```python
from investing_algorithm_framework import YahooFinanceDataProvider

yahoo_provider = YahooFinanceDataProvider(
    symbols=["AAPL", "GOOGL", "MSFT", "TSLA"],
    timeframes=["1d"]
)
```

#### Alpha Vantage
```python
from investing_algorithm_framework import AlphaVantageDataProvider

alpha_vantage_provider = AlphaVantageDataProvider(
    api_key="YOUR_API_KEY",
    symbols=["AAPL", "GOOGL"],
    timeframes=["1d", "1h"]
)
```

## Data Provider Configuration

### Basic Configuration

```python
from investing_algorithm_framework import create_app

app = create_app()

# Add a data provider
app.add_data_provider(binance_provider)

# Add multiple providers
app.add_data_provider(binance_provider)
app.add_data_provider(yahoo_provider)
```

### Advanced Configuration

```python
# Configure with custom settings
binance_provider = CCXTOHLCVDataProvider(
    exchange_name="binance",
    symbols=["BTC/USDT", "ETH/USDT"],
    timeframes=["1m", "5m", "1h", "1d"],
    # Advanced settings
    rate_limit=1200,  # requests per minute
    sandbox=False,    # use live data
    timeout=30000,    # 30 seconds timeout
    enable_rate_limit=True
)
```

### Environment-Based Configuration

```python
import os

# Configure based on environment
is_production = os.getenv("ENVIRONMENT") == "production"

if is_production:
    # Production configuration
    provider = CCXTOHLCVDataProvider(
        exchange_name="binance",
        symbols=["BTC/USDT", "ETH/USDT"],
        sandbox=False
    )
else:
    # Development/testing configuration
    provider = CCXTOHLCVDataProvider(
        exchange_name="binance",
        symbols=["BTC/USDT", "ETH/USDT"],
        sandbox=True  # Use testnet data
    )

app.add_data_provider(provider)
```

## Data Source Features

### Real-time Data

```python
# Access real-time market data
def get_current_prices(algorithm, market_data):
    symbols = ["BTC/USDT", "ETH/USDT"]
    
    for symbol in symbols:
        current_price = market_data.get_last_price(symbol)
        print(f"{symbol}: ${current_price:.2f}")
```

### Historical Data

```python
# Access historical data
def analyze_historical_data(algorithm, market_data):
    symbol = "BTC/USDT"
    
    # Get last 100 daily candles
    daily_data = market_data.get_data(symbol, timeframe="1d", size=100)
    
    # Get last 500 hourly candles
    hourly_data = market_data.get_data(symbol, timeframe="1h", size=500)
    
    print(f"Daily data points: {len(daily_data)}")
    print(f"Hourly data points: {len(hourly_data)}")
```

### Multiple Timeframes

```python
class MultiTimeframeStrategy(TradingStrategy):
    def apply_strategy(self, algorithm, market_data):
        symbol = "BTC/USDT"
        
        # Analyze different timeframes
        daily_trend = self.analyze_daily_trend(market_data, symbol)
        hourly_momentum = self.analyze_hourly_momentum(market_data, symbol)
        minute_entry = self.find_minute_entry(market_data, symbol)
        
        # Combine signals from different timeframes
        if daily_trend == "bullish" and hourly_momentum == "strong" and minute_entry:
            algorithm.create_buy_order(
                target_symbol="BTC",
                amount=100,
                order_type="MARKET"
            )
    
    def analyze_daily_trend(self, market_data, symbol):
        daily_data = market_data.get_data(symbol, timeframe="1d", size=20)
        # Trend analysis logic
        return "bullish"  # Example
    
    def analyze_hourly_momentum(self, market_data, symbol):
        hourly_data = market_data.get_data(symbol, timeframe="1h", size=50)
        # Momentum analysis logic
        return "strong"  # Example
    
    def find_minute_entry(self, market_data, symbol):
        minute_data = market_data.get_data(symbol, timeframe="1m", size=10)
        # Entry signal logic
        return True  # Example
```

## Custom Data Providers

### Creating Custom Data Provider

```python
from investing_algorithm_framework import DataProvider
import requests

class CustomDataProvider(DataProvider):
    def __init__(self, api_key, symbols):
        super().__init__()
        self.api_key = api_key
        self.symbols = symbols
        self.name = "custom_provider"
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Fetch data from custom API"""
        
        url = f"https://api.custom-provider.com/data"
        params = {
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": size,
            "api_key": self.api_key
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        # Convert to framework format
        return self.format_data(data)
    
    def format_data(self, raw_data):
        """Convert raw data to framework format"""
        
        formatted_data = []
        for item in raw_data:
            formatted_data.append({
                "timestamp": item["timestamp"],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item["volume"])
            })
        
        return formatted_data
    
    def is_connected(self):
        """Check if data provider is connected"""
        try:
            # Test API connection
            response = requests.get("https://api.custom-provider.com/status")
            return response.status_code == 200
        except:
            return False

# Use custom data provider
custom_provider = CustomDataProvider(
    api_key="your_api_key",
    symbols=["CUSTOM/SYMBOL"]
)

app.add_data_provider(custom_provider)
```

### Database Data Provider

```python
import sqlite3
import pandas as pd

class DatabaseDataProvider(DataProvider):
    def __init__(self, database_path):
        super().__init__()
        self.database_path = database_path
        self.name = "database_provider"
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Fetch data from local database"""
        
        conn = sqlite3.connect(self.database_path)
        
        query = """
        SELECT timestamp, open, high, low, close, volume
        FROM market_data
        WHERE symbol = ? AND timeframe = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=[symbol, timeframe, size])
        conn.close()
        
        # Convert to framework format
        return df.to_dict('records')
    
    def store_data(self, symbol, timeframe, data):
        """Store data in database"""
        
        conn = sqlite3.connect(self.database_path)
        
        for item in data:
            query = """
            INSERT OR REPLACE INTO market_data 
            (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            conn.execute(query, [
                symbol, timeframe, item["timestamp"],
                item["open"], item["high"], item["low"],
                item["close"], item["volume"]
            ])
        
        conn.commit()
        conn.close()

# Use database provider
db_provider = DatabaseDataProvider("./market_data.db")
app.add_data_provider(db_provider)
```

## Data Quality and Validation

### Data Validation

```python
class ValidatedDataProvider(DataProvider):
    def __init__(self, base_provider):
        super().__init__()
        self.base_provider = base_provider
        self.name = f"validated_{base_provider.name}"
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Get data with validation"""
        
        # Get data from base provider
        data = self.base_provider.get_data(symbol, timeframe, size)
        
        # Validate data
        validated_data = self.validate_data(data, symbol)
        
        return validated_data
    
    def validate_data(self, data, symbol):
        """Validate and clean data"""
        
        if not data:
            raise ValueError(f"No data received for {symbol}")
        
        df = pd.DataFrame(data)
        
        # Check for required columns
        required_cols = ["open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise ValueError(f"Missing columns: {missing_cols}")
        
        # Validate price relationships
        invalid_rows = (
            (df["high"] < df["low"]) |
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"])
        )
        
        if invalid_rows.any():
            print(f"Warning: Found {invalid_rows.sum()} invalid OHLC rows")
            # Remove invalid rows
            df = df[~invalid_rows]
        
        # Remove duplicates
        df = df.drop_duplicates(subset=["timestamp"])
        
        return df.to_dict('records')

# Wrap provider with validation
base_provider = CCXTOHLCVDataProvider("binance", ["BTC/USDT"])
validated_provider = ValidatedDataProvider(base_provider)
app.add_data_provider(validated_provider)
```

## Data Source Monitoring

### Health Monitoring

```python
class DataSourceMonitor:
    def __init__(self, providers):
        self.providers = providers
        self.health_status = {}
    
    def check_provider_health(self):
        """Check health of all data providers"""
        
        for provider in self.providers:
            try:
                # Test data retrieval
                test_data = provider.get_data("BTC/USDT", "1d", 1)
                
                if test_data and len(test_data) > 0:
                    self.health_status[provider.name] = "healthy"
                else:
                    self.health_status[provider.name] = "no_data"
                    
            except Exception as e:
                self.health_status[provider.name] = f"error: {e}"
        
        return self.health_status
    
    def get_healthy_providers(self):
        """Get list of healthy providers"""
        self.check_provider_health()
        
        healthy = [
            provider for provider in self.providers
            if self.health_status.get(provider.name) == "healthy"
        ]
        
        return healthy

# Monitor data sources
monitor = DataSourceMonitor([binance_provider, coinbase_provider])
healthy_providers = monitor.get_healthy_providers()

print(f"Healthy providers: {len(healthy_providers)}")
```

### Fallback Strategy

```python
class FallbackDataProvider(DataProvider):
    def __init__(self, primary_provider, fallback_providers):
        super().__init__()
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers
        self.name = "fallback_provider"
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Get data with fallback logic"""
        
        # Try primary provider first
        try:
            data = self.primary_provider.get_data(symbol, timeframe, size)
            if data and len(data) > 0:
                return data
        except Exception as e:
            print(f"Primary provider failed: {e}")
        
        # Try fallback providers
        for i, provider in enumerate(self.fallback_providers):
            try:
                data = provider.get_data(symbol, timeframe, size)
                if data and len(data) > 0:
                    print(f"Using fallback provider {i+1}")
                    return data
            except Exception as e:
                print(f"Fallback provider {i+1} failed: {e}")
        
        raise Exception("All data providers failed")

# Create fallback strategy
primary = CCXTOHLCVDataProvider("binance", ["BTC/USDT"])
fallbacks = [
    CCXTOHLCVDataProvider("coinbasepro", ["BTC-USD"]),
    CCXTOHLCVDataProvider("kraken", ["XBTUSD"])
]

fallback_provider = FallbackDataProvider(primary, fallbacks)
app.add_data_provider(fallback_provider)
```

## Best Practices

### 1. Data Source Diversification

Use multiple data sources to ensure reliability:

```python
# Configure multiple exchanges
providers = [
    CCXTOHLCVDataProvider("binance", ["BTC/USDT"]),
    CCXTOHLCVDataProvider("coinbasepro", ["BTC-USD"]),
    CCXTOHLCVDataProvider("kraken", ["XBTUSD"])
]

for provider in providers:
    app.add_data_provider(provider)
```

### 2. Rate Limit Management

Respect exchange rate limits:

```python
# Configure appropriate rate limits
provider = CCXTOHLCVDataProvider(
    "binance",
    ["BTC/USDT"],
    rate_limit=1000,  # requests per minute
    enable_rate_limit=True
)
```

### 3. Error Handling

Implement robust error handling:

```python
def safe_data_access(market_data, symbol, timeframe="1d"):
    try:
        data = market_data.get_data(symbol, timeframe, 100)
        return data
    except Exception as e:
        print(f"Failed to get data for {symbol}: {e}")
        return None
```

### 4. Data Caching

Cache frequently accessed data:

```python
class CachedDataProvider(DataProvider):
    def __init__(self, base_provider, cache_ttl=60):
        self.base_provider = base_provider
        self.cache_ttl = cache_ttl
        self.cache = {}
        self.cache_timestamps = {}
    
    def get_data(self, symbol, timeframe="1d", size=100):
        cache_key = f"{symbol}_{timeframe}_{size}"
        now = datetime.now().timestamp()
        
        # Check cache
        if (cache_key in self.cache and 
            now - self.cache_timestamps[cache_key] < self.cache_ttl):
            return self.cache[cache_key]
        
        # Fetch fresh data
        data = self.base_provider.get_data(symbol, timeframe, size)
        
        # Update cache
        self.cache[cache_key] = data
        self.cache_timestamps[cache_key] = now
        
        return data
```

## Next Steps

Now that you understand market data sources, explore:

1. **[Multiple Market Data Sources](multiple-market-data-sources)** to learn about combining data from different providers
2. **Data validation and quality assurance techniques**
3. **Performance optimization for data access**

Understanding your data sources is crucial for building reliable trading algorithms!
