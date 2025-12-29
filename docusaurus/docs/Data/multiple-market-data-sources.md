---
sidebar_position: 3
---

# Multiple Market Data Sources

Learn how to integrate and manage multiple data sources for comprehensive market analysis.

## Overview

Using multiple market data sources enhances the reliability, coverage, and quality of your trading system. This guide covers strategies for integrating different data providers, handling data conflicts, and creating robust data pipelines.

## Benefits of Multiple Data Sources

### 1. Increased Reliability
- **Redundancy**: Backup data sources when primary fails
- **Uptime**: Higher overall system availability
- **Risk Reduction**: Less dependence on single provider

### 2. Enhanced Coverage
- **Geographic Coverage**: Different exchanges for different regions
- **Asset Coverage**: Access to more trading pairs and assets
- **Time Coverage**: Fill gaps with alternative sources

### 3. Data Quality Improvements
- **Cross-Validation**: Compare data across sources
- **Anomaly Detection**: Identify outliers and errors
- **Data Enrichment**: Combine complementary data types

## Setting Up Multiple Data Sources

### Basic Multi-Source Configuration

```python
from investing_algorithm_framework import create_app, CCXTOHLCVDataProvider

app = create_app()

# Configure multiple cryptocurrency exchanges
binance_provider = CCXTOHLCVDataProvider(
    exchange_name="binance",
    symbols=["BTC/USDT", "ETH/USDT", "ADA/USDT"],
    timeframes=["1m", "1h", "1d"]
)

coinbase_provider = CCXTOHLCVDataProvider(
    exchange_name="coinbasepro", 
    symbols=["BTC-USD", "ETH-USD", "ADA-USD"],
    timeframes=["1m", "1h", "1d"]
)

kraken_provider = CCXTOHLCVDataProvider(
    exchange_name="kraken",
    symbols=["XBTUSD", "ETHUSD", "ADAUSD"], 
    timeframes=["1m", "1h", "1d"]
)

# Add all providers to the app
app.add_data_provider(binance_provider)
app.add_data_provider(coinbase_provider)
app.add_data_provider(kraken_provider)
```

### Mixed Asset Classes

```python
# Combine crypto and stock data
from investing_algorithm_framework import YahooFinanceDataProvider

# Cryptocurrency data
crypto_provider = CCXTOHLCVDataProvider(
    "binance", 
    ["BTC/USDT", "ETH/USDT"]
)

# Stock market data  
stock_provider = YahooFinanceDataProvider(
    symbols=["AAPL", "GOOGL", "TSLA", "MSFT"],
    timeframes=["1d"]
)

# Economic indicators (example custom provider)
economic_provider = CustomEconomicDataProvider(
    indicators=["GDP", "CPI", "UNEMPLOYMENT"]
)

app.add_data_provider(crypto_provider)
app.add_data_provider(stock_provider)
app.add_data_provider(economic_provider)
```

## Data Source Management

### Data Router

```python
class DataRouter:
    def __init__(self):
        self.providers = {}
        self.symbol_mappings = {}
        self.priority_order = []
    
    def add_provider(self, provider, priority=1):
        """Add data provider with priority"""
        self.providers[provider.name] = {
            'provider': provider,
            'priority': priority
        }
        self._update_priority_order()
    
    def map_symbol(self, standard_symbol, provider_symbols):
        """Map standard symbol to provider-specific symbols"""
        self.symbol_mappings[standard_symbol] = provider_symbols
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Get data using provider priority and symbol mapping"""
        
        # Get provider-specific symbol mappings
        provider_symbols = self.symbol_mappings.get(symbol, {})
        
        for provider_name in self.priority_order:
            provider_info = self.providers[provider_name]
            provider = provider_info['provider']
            
            # Get the correct symbol for this provider
            provider_symbol = provider_symbols.get(provider_name, symbol)
            
            try:
                data = provider.get_data(provider_symbol, timeframe, size)
                if data and len(data) > 0:
                    print(f"Retrieved {symbol} data from {provider_name}")
                    return data
            except Exception as e:
                print(f"Failed to get {symbol} from {provider_name}: {e}")
                continue
        
        raise Exception(f"No provider could retrieve data for {symbol}")
    
    def _update_priority_order(self):
        """Update provider order based on priority"""
        sorted_providers = sorted(
            self.providers.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        )
        self.priority_order = [name for name, _ in sorted_providers]

# Setup data router
router = DataRouter()

# Add providers with priorities
router.add_provider(binance_provider, priority=3)  # Highest priority
router.add_provider(coinbase_provider, priority=2)
router.add_provider(kraken_provider, priority=1)   # Lowest priority

# Map symbols across exchanges
router.map_symbol("BTC/USD", {
    "binance": "BTC/USDT",
    "coinbasepro": "BTC-USD", 
    "kraken": "XBTUSD"
})

router.map_symbol("ETH/USD", {
    "binance": "ETH/USDT",
    "coinbasepro": "ETH-USD",
    "kraken": "ETHUSD"
})

# Use router to get data
btc_data = router.get_data("BTC/USD", "1h", 100)
```

### Data Aggregator

```python
import pandas as pd
from statistics import mean, median

class DataAggregator:
    def __init__(self, providers):
        self.providers = providers
    
    def get_aggregated_price(self, symbol, method="mean"):
        """Get aggregated price from multiple sources"""
        
        prices = []
        
        for provider in self.providers:
            try:
                data = provider.get_data(symbol, "1m", 1)
                if data:
                    current_price = data[0]["close"]
                    prices.append(current_price)
            except Exception as e:
                print(f"Failed to get price from {provider.name}: {e}")
        
        if not prices:
            raise Exception("No price data available from any provider")
        
        # Aggregate prices
        if method == "mean":
            return mean(prices)
        elif method == "median":
            return median(prices)
        elif method == "min":
            return min(prices)
        elif method == "max":
            return max(prices)
        else:
            raise ValueError(f"Unknown aggregation method: {method}")
    
    def get_consensus_data(self, symbol, timeframe="1d", size=100):
        """Get consensus OHLCV data from multiple sources"""
        
        all_data = []
        
        # Collect data from all providers
        for provider in self.providers:
            try:
                data = provider.get_data(symbol, timeframe, size)
                if data:
                    df = pd.DataFrame(data)
                    df['source'] = provider.name
                    all_data.append(df)
            except Exception as e:
                print(f"Failed to get data from {provider.name}: {e}")
        
        if not all_data:
            raise Exception("No data available from any provider")
        
        # Combine and aggregate data
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Group by timestamp and aggregate
        consensus_data = combined_df.groupby('timestamp').agg({
            'open': 'mean',
            'high': 'mean', 
            'low': 'mean',
            'close': 'mean',
            'volume': 'sum'  # Sum volumes across exchanges
        }).reset_index()
        
        return consensus_data.to_dict('records')

# Use data aggregator
aggregator = DataAggregator([binance_provider, coinbase_provider, kraken_provider])

# Get aggregated current price
current_btc_price = aggregator.get_aggregated_price("BTC/USDT", method="median")
print(f"Consensus BTC price: ${current_btc_price:.2f}")

# Get consensus historical data
consensus_data = aggregator.get_consensus_data("BTC/USDT", "1h", 24)
```

## Data Quality Management

### Cross-Validation

```python
class DataValidator:
    def __init__(self, providers, tolerance=0.05):
        self.providers = providers
        self.tolerance = tolerance  # 5% tolerance for price differences
    
    def validate_price_consensus(self, symbol):
        """Validate price consistency across providers"""
        
        prices = {}
        
        for provider in self.providers:
            try:
                data = provider.get_data(symbol, "1m", 1)
                if data:
                    prices[provider.name] = data[0]["close"]
            except Exception as e:
                print(f"Failed to get price from {provider.name}: {e}")
        
        if len(prices) < 2:
            return {"status": "insufficient_data", "prices": prices}
        
        # Calculate price deviation
        price_values = list(prices.values())
        avg_price = mean(price_values)
        max_deviation = max(abs(p - avg_price) / avg_price for p in price_values)
        
        status = "valid" if max_deviation <= self.tolerance else "invalid"
        
        return {
            "status": status,
            "prices": prices,
            "average_price": avg_price,
            "max_deviation": max_deviation,
            "tolerance": self.tolerance
        }
    
    def identify_outliers(self, symbol, timeframe="1d", size=100):
        """Identify outlier data points across providers"""
        
        all_data = {}
        
        # Collect data from all providers
        for provider in self.providers:
            try:
                data = provider.get_data(symbol, timeframe, size)
                if data:
                    all_data[provider.name] = pd.DataFrame(data)
            except Exception as e:
                print(f"Failed to get data from {provider.name}: {e}")
        
        outliers = {}
        
        # Compare each timestamp across providers
        if len(all_data) >= 2:
            timestamps = set()
            for df in all_data.values():
                timestamps.update(df['timestamp'])
            
            for timestamp in timestamps:
                prices = []
                for provider_name, df in all_data.items():
                    timestamp_data = df[df['timestamp'] == timestamp]
                    if not timestamp_data.empty:
                        prices.append({
                            'provider': provider_name,
                            'close': timestamp_data.iloc[0]['close']
                        })
                
                if len(prices) >= 2:
                    # Check for outliers
                    avg_price = mean([p['close'] for p in prices])
                    
                    for price_data in prices:
                        deviation = abs(price_data['close'] - avg_price) / avg_price
                        if deviation > self.tolerance:
                            if timestamp not in outliers:
                                outliers[timestamp] = []
                            outliers[timestamp].append({
                                'provider': price_data['provider'],
                                'price': price_data['close'],
                                'deviation': deviation
                            })
        
        return outliers

# Validate data quality
validator = DataValidator([binance_provider, coinbase_provider, kraken_provider])

# Check price consensus
consensus_result = validator.validate_price_consensus("BTC/USDT")
print(f"Price consensus: {consensus_result}")

# Identify outliers
outliers = validator.identify_outliers("BTC/USDT", "1h", 24)
if outliers:
    print(f"Found outliers at {len(outliers)} timestamps")
```

### Data Synchronization

```python
class DataSynchronizer:
    def __init__(self, providers):
        self.providers = providers
    
    def synchronize_data(self, symbol, timeframe="1d", size=100):
        """Synchronize data timestamps across providers"""
        
        all_data = {}
        
        # Get data from all providers
        for provider in self.providers:
            try:
                data = provider.get_data(symbol, timeframe, size)
                if data:
                    df = pd.DataFrame(data)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    all_data[provider.name] = df
            except Exception as e:
                print(f"Failed to get data from {provider.name}: {e}")
        
        if not all_data:
            return None
        
        # Find common timestamp range
        start_times = [df.index.min() for df in all_data.values()]
        end_times = [df.index.max() for df in all_data.values()]
        
        common_start = max(start_times)
        common_end = min(end_times)
        
        # Align data to common timestamps
        synchronized_data = {}
        
        for provider_name, df in all_data.items():
            # Filter to common time range
            mask = (df.index >= common_start) & (df.index <= common_end)
            synchronized_data[provider_name] = df.loc[mask]
        
        return synchronized_data
    
    def merge_synchronized_data(self, synchronized_data):
        """Merge synchronized data with provider labels"""
        
        merged_data = pd.DataFrame()
        
        for provider_name, df in synchronized_data.items():
            # Add provider suffix to columns
            provider_df = df.copy()
            provider_df.columns = [f"{col}_{provider_name}" for col in provider_df.columns]
            
            if merged_data.empty:
                merged_data = provider_df
            else:
                merged_data = merged_data.join(provider_df, how='outer')
        
        return merged_data

# Synchronize data across providers
synchronizer = DataSynchronizer([binance_provider, coinbase_provider])
sync_data = synchronizer.synchronize_data("BTC/USDT", "1h", 100)
merged_data = synchronizer.merge_synchronized_data(sync_data)

print(f"Synchronized data shape: {merged_data.shape}")
```

## Advanced Multi-Source Strategies

### Arbitrage Detection

```python
class ArbitrageDetector:
    def __init__(self, providers, min_profit_threshold=0.01):
        self.providers = providers
        self.min_profit_threshold = min_profit_threshold
    
    def detect_arbitrage_opportunities(self, symbol):
        """Detect price differences across exchanges"""
        
        prices = {}
        
        # Get current prices from all exchanges
        for provider in self.providers:
            try:
                data = provider.get_data(symbol, "1m", 1)
                if data:
                    prices[provider.name] = {
                        'price': data[0]["close"],
                        'timestamp': data[0]["timestamp"]
                    }
            except Exception as e:
                print(f"Failed to get price from {provider.name}: {e}")
        
        if len(prices) < 2:
            return []
        
        opportunities = []
        
        # Find arbitrage opportunities
        provider_names = list(prices.keys())
        
        for i in range(len(provider_names)):
            for j in range(i + 1, len(provider_names)):
                provider_a = provider_names[i]
                provider_b = provider_names[j]
                
                price_a = prices[provider_a]['price']
                price_b = prices[provider_b]['price']
                
                # Calculate profit potential
                if price_a < price_b:
                    profit_pct = (price_b - price_a) / price_a
                    buy_exchange = provider_a
                    sell_exchange = provider_b
                else:
                    profit_pct = (price_a - price_b) / price_b
                    buy_exchange = provider_b
                    sell_exchange = provider_a
                
                if profit_pct >= self.min_profit_threshold:
                    opportunities.append({
                        'symbol': symbol,
                        'buy_exchange': buy_exchange,
                        'sell_exchange': sell_exchange,
                        'buy_price': min(price_a, price_b),
                        'sell_price': max(price_a, price_b),
                        'profit_percentage': profit_pct * 100,
                        'timestamp': max(prices[provider_a]['timestamp'], 
                                       prices[provider_b]['timestamp'])
                    })
        
        return opportunities

# Detect arbitrage opportunities
arbitrage_detector = ArbitrageDetector([binance_provider, coinbase_provider, kraken_provider])
opportunities = arbitrage_detector.detect_arbitrage_opportunities("BTC/USDT")

for opp in opportunities:
    print(f"Arbitrage opportunity: Buy on {opp['buy_exchange']} at "
          f"${opp['buy_price']:.2f}, sell on {opp['sell_exchange']} at "
          f"${opp['sell_price']:.2f} ({opp['profit_percentage']:.2f}% profit)")
```

### Data Quality Scoring

```python
class DataQualityScorer:
    def __init__(self, providers):
        self.providers = providers
        self.scores = {}
    
    def calculate_quality_score(self, symbol, timeframe="1d", size=100):
        """Calculate quality score for each provider"""
        
        scores = {}
        
        for provider in self.providers:
            score = 0
            max_score = 100
            
            try:
                # Test data retrieval
                data = provider.get_data(symbol, timeframe, size)
                
                if not data:
                    scores[provider.name] = 0
                    continue
                
                df = pd.DataFrame(data)
                
                # Completeness score (40 points)
                completeness = len(df) / size
                score += completeness * 40
                
                # Data integrity score (30 points)
                # Check for null values
                null_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
                integrity_score = max(0, 1 - null_ratio) * 30
                score += integrity_score
                
                # Price consistency score (30 points)
                # Check OHLC relationships
                valid_ohlc = (
                    (df['high'] >= df['low']) &
                    (df['high'] >= df['open']) &
                    (df['high'] >= df['close']) &
                    (df['low'] <= df['open']) &
                    (df['low'] <= df['close'])
                ).mean()
                score += valid_ohlc * 30
                
                scores[provider.name] = min(score, max_score)
                
            except Exception as e:
                print(f"Error calculating score for {provider.name}: {e}")
                scores[provider.name] = 0
        
        self.scores[symbol] = scores
        return scores
    
    def get_best_provider(self, symbol):
        """Get the provider with the highest quality score"""
        if symbol not in self.scores:
            self.calculate_quality_score(symbol)
        
        scores = self.scores[symbol]
        if not scores:
            return None
        
        best_provider = max(scores, key=scores.get)
        return best_provider, scores[best_provider]

# Calculate data quality scores
quality_scorer = DataQualityScorer([binance_provider, coinbase_provider, kraken_provider])
scores = quality_scorer.calculate_quality_score("BTC/USDT")

print("Data quality scores:")
for provider, score in scores.items():
    print(f"{provider}: {score:.1f}/100")

best_provider, best_score = quality_scorer.get_best_provider("BTC/USDT")
print(f"Best provider: {best_provider} ({best_score:.1f}/100)")
```

## Performance Optimization

### Connection Pooling

```python
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

class AsyncDataProvider:
    def __init__(self, providers):
        self.providers = providers
        self.executor = ThreadPoolExecutor(max_workers=len(providers))
    
    async def get_data_async(self, symbol, timeframe="1d", size=100):
        """Fetch data from multiple providers asynchronously"""
        
        async def fetch_from_provider(provider):
            try:
                # Run synchronous provider call in thread pool
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    self.executor,
                    provider.get_data,
                    symbol, timeframe, size
                )
                return provider.name, data
            except Exception as e:
                return provider.name, None
        
        # Fetch from all providers concurrently
        tasks = [fetch_from_provider(provider) for provider in self.providers]
        results = await asyncio.gather(*tasks)
        
        # Return successful results
        successful_results = {}
        for provider_name, data in results:
            if data:
                successful_results[provider_name] = data
        
        return successful_results

# Use async data fetching
async def main():
    async_provider = AsyncDataProvider([binance_provider, coinbase_provider, kraken_provider])
    results = await async_provider.get_data_async("BTC/USDT", "1h", 100)
    
    print(f"Retrieved data from {len(results)} providers")
    for provider_name, data in results.items():
        print(f"{provider_name}: {len(data)} data points")

# Run async example
# asyncio.run(main())
```

### Caching Strategy

```python
import redis
import json
import hashlib
from datetime import datetime, timedelta

class MultiSourceCache:
    def __init__(self, redis_client, default_ttl=300):
        self.redis_client = redis_client
        self.default_ttl = default_ttl
    
    def get_cache_key(self, provider_name, symbol, timeframe, size):
        """Generate cache key"""
        key_data = f"{provider_name}:{symbol}:{timeframe}:{size}"
        return f"data_cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def get_cached_data(self, provider_name, symbol, timeframe, size):
        """Get data from cache"""
        cache_key = self.get_cache_key(provider_name, symbol, timeframe, size)
        cached_data = self.redis_client.get(cache_key)
        
        if cached_data:
            return json.loads(cached_data)
        return None
    
    def cache_data(self, provider_name, symbol, timeframe, size, data, ttl=None):
        """Cache data with TTL"""
        cache_key = self.get_cache_key(provider_name, symbol, timeframe, size)
        ttl = ttl or self.default_ttl
        
        self.redis_client.setex(
            cache_key,
            ttl,
            json.dumps(data, default=str)
        )

class CachedMultiSourceProvider:
    def __init__(self, providers, cache):
        self.providers = providers
        self.cache = cache
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Get data with caching"""
        
        for provider in self.providers:
            # Try cache first
            cached_data = self.cache.get_cached_data(
                provider.name, symbol, timeframe, size
            )
            
            if cached_data:
                print(f"Cache hit for {provider.name}")
                return cached_data
            
            # Fetch fresh data
            try:
                data = provider.get_data(symbol, timeframe, size)
                if data:
                    # Cache the data
                    self.cache.cache_data(
                        provider.name, symbol, timeframe, size, data
                    )
                    return data
            except Exception as e:
                print(f"Failed to get data from {provider.name}: {e}")
        
        raise Exception("No provider could retrieve data")

# Setup caching (assuming Redis is available)
# redis_client = redis.Redis(host='localhost', port=6379, db=0)
# cache = MultiSourceCache(redis_client)
# cached_provider = CachedMultiSourceProvider([binance_provider, coinbase_provider], cache)
```

## Best Practices

### 1. Provider Health Monitoring

```python
class ProviderHealthMonitor:
    def __init__(self, providers):
        self.providers = providers
        self.health_history = {}
    
    def monitor_providers(self):
        """Monitor provider health continuously"""
        
        for provider in self.providers:
            try:
                # Test data retrieval
                test_data = provider.get_data("BTC/USDT", "1m", 1)
                success = test_data is not None and len(test_data) > 0
                
                # Update health history
                if provider.name not in self.health_history:
                    self.health_history[provider.name] = []
                
                self.health_history[provider.name].append({
                    'timestamp': datetime.now(),
                    'success': success
                })
                
                # Keep only last 100 health checks
                self.health_history[provider.name] = self.health_history[provider.name][-100:]
                
            except Exception as e:
                print(f"Health check failed for {provider.name}: {e}")
    
    def get_provider_reliability(self, provider_name):
        """Get provider reliability percentage"""
        
        if provider_name not in self.health_history:
            return 0
        
        history = self.health_history[provider_name]
        if not history:
            return 0
        
        successes = sum(1 for check in history if check['success'])
        return (successes / len(history)) * 100

# Monitor provider health
monitor = ProviderHealthMonitor([binance_provider, coinbase_provider, kraken_provider])
monitor.monitor_providers()

for provider in [binance_provider, coinbase_provider, kraken_provider]:
    reliability = monitor.get_provider_reliability(provider.name)
    print(f"{provider.name} reliability: {reliability:.1f}%")
```

### 2. Graceful Degradation

```python
class GracefulDataProvider:
    def __init__(self, providers, min_providers=1):
        self.providers = providers
        self.min_providers = min_providers
        self.failed_providers = set()
    
    def get_data(self, symbol, timeframe="1d", size=100):
        """Get data with graceful degradation"""
        
        available_providers = [
            p for p in self.providers 
            if p.name not in self.failed_providers
        ]
        
        if len(available_providers) < self.min_providers:
            # Reset failed providers if too many failed
            self.failed_providers.clear()
            available_providers = self.providers
        
        for provider in available_providers:
            try:
                data = provider.get_data(symbol, timeframe, size)
                if data:
                    # Remove from failed list if successful
                    self.failed_providers.discard(provider.name)
                    return data
            except Exception as e:
                print(f"Provider {provider.name} failed: {e}")
                self.failed_providers.add(provider.name)
        
        raise Exception("All providers failed")

# Use graceful degradation
graceful_provider = GracefulDataProvider([binance_provider, coinbase_provider, kraken_provider])
```

### 3. Data Consistency Checks

```python
def validate_multi_source_data(data_sources):
    """Validate consistency across multiple data sources"""
    
    if len(data_sources) < 2:
        return {"status": "insufficient_sources"}
    
    # Compare latest prices
    latest_prices = []
    for source_name, data in data_sources.items():
        if data and len(data) > 0:
            latest_prices.append({
                'source': source_name,
                'price': data[0]['close'],
                'timestamp': data[0]['timestamp']
            })
    
    if len(latest_prices) < 2:
        return {"status": "insufficient_data"}
    
    # Calculate price deviation
    prices = [p['price'] for p in latest_prices]
    avg_price = mean(prices)
    max_deviation = max(abs(p - avg_price) / avg_price for p in prices)
    
    return {
        "status": "valid" if max_deviation < 0.05 else "inconsistent",
        "prices": latest_prices,
        "average_price": avg_price,
        "max_deviation": max_deviation
    }
```

## Next Steps

With multiple data sources configured, you can:

1. **Implement advanced trading strategies** that leverage data from multiple markets
2. **Build robust monitoring systems** to track data quality and provider performance  
3. **Develop arbitrage detection** and cross-market analysis capabilities
4. **Create data backup and recovery** procedures for production systems

Multiple data sources provide the foundation for sophisticated, reliable trading systems that can adapt to changing market conditions and provider availability.
