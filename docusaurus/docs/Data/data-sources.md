---
sidebar_position: 2
---

# Data Sources

Learn how to configure and use data sources for market data in your trading strategies.

## Overview

The Investing Algorithm Framework uses `DataSource` objects to define what market data your strategies need. Data sources are configured with symbols, timeframes, and warmup windows, and the framework automatically handles data retrieval from the appropriate data providers.

## DataSource Configuration

### Basic DataSource

A `DataSource` defines the market data requirements for your strategy:

```python
from investing_algorithm_framework import DataSource

data_source = DataSource(
    identifier="btc_hourly",
    symbol="BTC/EUR",
    time_frame="1h",
    warmup_window=100,
    market="BITVAVO"
)
```

### DataSource Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `identifier` | `str` | Unique identifier to reference this data source in your strategy. |
| `symbol` | `str` | Trading pair (e.g., `"BTC/EUR"`, `"ETH/USDT"`). |
| `time_frame` | `str` | Candlestick timeframe (e.g., `"1h"`, `"4h"`, `"1d"`). |
| `warmup_window` | `int` | Number of historical data points needed for indicator warmup. |
| `market` | `str` | Exchange/market identifier (e.g., `"BITVAVO"`, `"BINANCE"`). |
| `data_type` | `DataType` | Type of data (default: `DataType.OHLCV`). |
| `pandas` | `bool` | Return data as pandas DataFrame (default: `False`). |

> ⚠️ **Deprecation Notice**: The `window_size` parameter is deprecated and will be removed in release 0.8.0. Please use `warmup_window` instead.

## Using Data Sources in Strategies

### Single Data Source

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, DataSource, PositionSize

class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]
    trading_symbol = "EUR"

    data_sources = [
        DataSource(
            identifier="btc_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            warmup_window=200,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.5),
    ]

    def generate_buy_signals(self, data):
        df = data["btc_1h"]  # Access by identifier
        close = df["Close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        # Golden cross signal
        buy_signal = (ma50 > ma200) & (ma50.shift(1) <= ma200.shift(1))
        return {"BTC": buy_signal}

    def generate_sell_signals(self, data):
        df = data["btc_1h"]
        close = df["Close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        # Death cross signal
        sell_signal = (ma50 < ma200) & (ma50.shift(1) >= ma200.shift(1))
        return {"BTC": sell_signal}
```

### Multiple Assets

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, DataSource, PositionSize

class MultiAssetStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC", "ETH", "ADA", "DOT"]
    trading_symbol = "EUR"

    data_sources = [
        DataSource(
            identifier="btc_4h",
            symbol="BTC/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="eth_4h",
            symbol="ETH/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="ada_4h",
            symbol="ADA/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="dot_4h",
            symbol="DOT/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.25),
        PositionSize(symbol="ETH", percentage=0.25),
        PositionSize(symbol="ADA", percentage=0.25),
        PositionSize(symbol="DOT", percentage=0.25),
    ]

    def generate_buy_signals(self, data):
        signals = {}

        for symbol in self.symbols:
            identifier = f"{symbol.lower()}_4h"
            df = data[identifier]
            ma50 = df["Close"].rolling(50).mean()
            signals[symbol] = df["Close"] > ma50

        return signals

    def generate_sell_signals(self, data):
        signals = {}

        for symbol in self.symbols:
            identifier = f"{symbol.lower()}_4h"
            df = data[identifier]
            ma50 = df["Close"].rolling(50).mean()
            signals[symbol] = df["Close"] < ma50

        return signals
```

### Multiple Timeframes

Use multiple timeframes for more sophisticated analysis:

```python
class MultiTimeframeStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]
    trading_symbol = "EUR"

    data_sources = [
        # Daily for long-term trend
        DataSource(
            identifier="btc_daily",
            symbol="BTC/EUR",
            time_frame="1d",
            warmup_window=50,
            market="BITVAVO"
        ),
        # 4-hour for medium-term trend
        DataSource(
            identifier="btc_4h",
            symbol="BTC/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        # Hourly for entry timing
        DataSource(
            identifier="btc_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            warmup_window=200,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.8),
    ]

    def _analyze_trend(self, df, ma_period=20):
        """Determine trend direction"""
        ma = df["Close"].rolling(ma_period).mean()
        current_price = df["Close"].iloc[-1]
        current_ma = ma.iloc[-1]

        if current_price > current_ma:
            return "bullish"
        elif current_price < current_ma:
            return "bearish"
        return "neutral"

    def generate_buy_signals(self, data):
        daily_df = data["btc_daily"]
        h4_df = data["btc_4h"]
        h1_df = data["btc_1h"]

        # Check all timeframes
        daily_trend = self._analyze_trend(daily_df, ma_period=20)
        h4_trend = self._analyze_trend(h4_df, ma_period=20)

        # Generate hourly signals
        h1_ma = h1_df["Close"].rolling(20).mean()
        h1_cross_above = (h1_df["Close"] > h1_ma) & (h1_df["Close"].shift(1) <= h1_ma.shift(1))

        # Only buy when all timeframes align bullish
        buy_signal = h1_cross_above.copy()

        if daily_trend != "bullish" or h4_trend != "bullish":
            buy_signal = buy_signal & False

        return {"BTC": buy_signal}

    def generate_sell_signals(self, data):
        h1_df = data["btc_1h"]
        h1_ma = h1_df["Close"].rolling(20).mean()

        # Sell on hourly MA cross below
        sell_signal = (h1_df["Close"] < h1_ma) & (h1_df["Close"].shift(1) >= h1_ma.shift(1))

        return {"BTC": sell_signal}
```

### Dynamic Data Source Creation

Create data sources programmatically for flexible strategies:

```python
class DynamicMultiAssetStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    trading_symbol = "EUR"

    def __init__(
        self,
        symbols=None,
        market="BITVAVO",
        time_frame="4h",
        warmup_window=100,
        **kwargs
    ):
        if symbols is None:
            symbols = ["BTC", "ETH"]

        self.symbols = symbols
        self.market = market
        self._time_frame = time_frame

        # Dynamically create data sources
        data_sources = []
        position_sizes = []
        allocation = 0.8 / len(symbols)  # 80% total allocation

        for symbol in symbols:
            full_symbol = f"{symbol}/EUR"
            identifier = f"{symbol.lower()}_{time_frame}"

            data_sources.append(
                DataSource(
                    identifier=identifier,
                    symbol=full_symbol,
                    time_frame=time_frame,
                    warmup_window=warmup_window,
                    market=market
                )
            )

            position_sizes.append(
                PositionSize(symbol=symbol, percentage=allocation)
            )

        super().__init__(
            data_sources=data_sources,
            position_sizes=position_sizes,
            **kwargs
        )

    def generate_buy_signals(self, data):
        signals = {}

        for symbol in self.symbols:
            identifier = f"{symbol.lower()}_{self._time_frame}"
            df = data[identifier]
            ma20 = df["Close"].rolling(20).mean()
            signals[symbol] = df["Close"] > ma20

        return signals

    def generate_sell_signals(self, data):
        signals = {}

        for symbol in self.symbols:
            identifier = f"{symbol.lower()}_{self._time_frame}"
            df = data[identifier]
            ma20 = df["Close"].rolling(20).mean()
            signals[symbol] = df["Close"] < ma20

        return signals

# Usage
strategy = DynamicMultiAssetStrategy(
    symbols=["BTC", "ETH", "ADA", "DOT", "LINK"],
    market="BITVAVO",
    time_frame="4h",
    warmup_window=100
)
```

## Supported Markets

The framework ships with built-in data providers for multiple markets. Set the `market` parameter on your `DataSource` to tell the framework where to fetch data from.

### Choosing the Right Market

| Use Case | Recommended Market | Why |
|----------|-------------------|-----|
| **Crypto trading** (live) | CCXT exchanges (`BINANCE`, `BITVAVO`, etc.) | Direct exchange connection, supports order execution |
| **US stocks / ETFs** (research & backtesting) | `YAHOO` | Free, no API key, broad coverage |
| **US stocks** (production-grade) | `POLYGON` | High reliability, real-time data, official exchange feeds |
| **Stocks + forex + crypto** (lightweight) | `ALPHA_VANTAGE` | Simple API, good for prototyping |
| **Local / offline data** | CSV or Pandas provider | Full control, no network dependency |

---

### Yahoo Finance — `market="YAHOO"`

**Best for:** Stocks, ETFs, indices, forex, and crypto research and backtesting.

Free, no API key required. Powered by the [yfinance](https://github.com/ranaroussi/yfinance) library using data from [Yahoo Finance](https://finance.yahoo.com/).

```python
DataSource(
    identifier="aapl_daily",
    market="YAHOO",
    symbol="AAPL",
    data_type="OHLCV",
    time_frame="1d",
    warmup_window=200,
)
```

**Supported timeframes:** `1m`, `2m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1W`, `1M`

**Symbol format:** Standard ticker symbols — `AAPL`, `MSFT`, `GOOGL`, `BTC-USD`, `EURUSD=X`

> ⚠️ Yahoo Finance is great for research and backtesting but is not recommended for production live trading due to rate limits and data delays.

---

### Polygon.io — `market="POLYGON"`

**Best for:** Production-grade US stock, options, forex, and crypto data.

Requires an API key from [Polygon.io](https://polygon.io/). Powered by the [polygon-api-client](https://github.com/polygon-io/client-python) library.

```python
from investing_algorithm_framework import MarketCredential

app.add_market_credential(
    MarketCredential(market="POLYGON", api_key="your_polygon_api_key")
)

DataSource(
    identifier="aapl_daily",
    market="POLYGON",
    symbol="AAPL",
    data_type="OHLCV",
    time_frame="1d",
    warmup_window=200,
)
```

**Supported timeframes:** `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1W`, `1M`

**Symbol format:** Standard ticker symbols — `AAPL`, `MSFT`, `X:BTCUSD` (crypto), `C:EURUSD` (forex)

> You can also configure the API key via environment variable: `export POLYGON_API_KEY=your_key`

---

### Alpha Vantage — `market="ALPHA_VANTAGE"`

**Best for:** Prototyping and lightweight stock/forex/crypto strategies.

Requires a free or premium API key from [Alpha Vantage](https://www.alphavantage.co/). Powered by the [alpha_vantage](https://github.com/RomelTorres/alpha_vantage) Python library.

```python
from investing_algorithm_framework import MarketCredential

app.add_market_credential(
    MarketCredential(market="ALPHA_VANTAGE", api_key="your_av_api_key")
)

DataSource(
    identifier="aapl_daily",
    market="ALPHA_VANTAGE",
    symbol="AAPL",
    data_type="OHLCV",
    time_frame="1d",
    warmup_window=200,
)
```

**Supported timeframes:** `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1W`, `1M`

**Symbol format:** Standard ticker symbols — `AAPL`, `MSFT`, `IBM`

> ⚠️ The free tier is limited to 25 API calls per day. For heavier usage, consider a [premium plan](https://www.alphavantage.co/premium/).

---

### CCXT Exchanges — Crypto

**Best for:** Live crypto trading and backtesting on specific exchanges.

The [CCXT](https://github.com/ccxt/ccxt) provider supports 100+ cryptocurrency exchanges. No additional API key is needed for public OHLCV data, but order execution requires exchange credentials.

```python
DataSource(
    identifier="btc_hourly",
    market="BITVAVO",       # any CCXT-supported exchange
    symbol="BTC/EUR",
    data_type="OHLCV",
    time_frame="1h",
    warmup_window=200,
)
```

**Popular exchanges:**

| Exchange | Market Identifier | Website |
|----------|-------------------|---------|
| Binance | `BINANCE` | [binance.com](https://www.binance.com/) |
| Bitvavo | `BITVAVO` | [bitvavo.com](https://bitvavo.com/) |
| Coinbase | `COINBASE` | [coinbase.com](https://www.coinbase.com/) |
| Kraken | `KRAKEN` | [kraken.com](https://www.kraken.com/) |
| Bybit | `BYBIT` | [bybit.com](https://www.bybit.com/) |
| OKX | `OKX` | [okx.com](https://www.okx.com/) |
| KuCoin | `KUCOIN` | [kucoin.com](https://www.kucoin.com/) |
| Bitfinex | `BITFINEX` | [bitfinex.com](https://www.bitfinex.com/) |

**Symbol format:** Trading pairs with slash — `BTC/EUR`, `ETH/USDT`, `ADA/BTC`

> See the full list of supported exchanges in the [CCXT documentation](https://docs.ccxt.com/#/README?id=supported-cryptocurrency-exchange-markets).

---

### CSV and Pandas — Local Data

**Best for:** Offline backtesting, custom data pipelines, or data from unsupported sources.

#### CSVOHLCVDataProvider

```python
from investing_algorithm_framework.infrastructure import CSVOHLCVDataProvider

csv_provider = CSVOHLCVDataProvider(
    csv_file_path="./data/btc_eur_1h.csv",
    symbol="BTC/EUR",
    time_frame="1h",
    market="bitvavo"
)

app.add_data_provider(csv_provider, priority=1)
```

CSV files must contain columns: `Datetime`, `Open`, `High`, `Low`, `Close`, `Volume`.

#### PandasOHLCVDataProvider

```python
from investing_algorithm_framework.infrastructure import PandasOHLCVDataProvider
import pandas as pd

df = pd.read_csv("btc_data.csv", index_col=0, parse_dates=True)

pandas_provider = PandasOHLCVDataProvider(
    dataframe=df,
    symbol="BTC/EUR",
    time_frame="1h",
    market="bitvavo"
)

app.add_data_provider(pandas_provider, priority=1)
```

---

### Mixing Markets

You can use different markets for different symbols in the same strategy:

```python
class MultiMarketStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["AAPL", "BTC"]
    trading_symbol = "USD"

    data_sources = [
        # Stocks from Yahoo Finance
        DataSource(
            identifier="aapl_daily",
            market="YAHOO",
            symbol="AAPL",
            time_frame="1d",
            warmup_window=200,
        ),
        # Crypto from Binance
        DataSource(
            identifier="btc_daily",
            market="BINANCE",
            symbol="BTC/USDT",
            time_frame="1d",
            warmup_window=200,
        ),
    ]
```

## Data Provider Priority

When multiple data providers can serve the same `DataSource`, the framework uses priority to select the best one. Lower number = higher priority:

```python
from investing_algorithm_framework import create_app
from investing_algorithm_framework.infrastructure import (
    CCXTOHLCVDataProvider,
    PandasOHLCVDataProvider
)

app = create_app()

# Priority 1 = highest priority (used first)
app.add_data_provider(pandas_provider, priority=1)

# Priority 3 = lower priority (fallback)
app.add_data_provider(CCXTOHLCVDataProvider(), priority=3)
```

> To learn how to build your own data provider for a custom API, see [Custom Data Providers](../Advanced%20Concepts/custom-data-providers).

## Warmup Window

The `warmup_window` parameter is crucial for strategies using technical indicators.

### Why Warmup Matters

Many indicators require historical data before producing valid values:

```python
# If you use a 200-period moving average, you need at least 200 data points
# before the indicator produces valid values

data_sources = [
    DataSource(
        identifier="btc_data",
        symbol="BTC/EUR",
        time_frame="1h",
        warmup_window=250,  # 200 + buffer
        market="BITVAVO"
    )
]
```

### Calculating Warmup Window

| Indicator | Typical Period | Recommended Warmup |
|-----------|----------------|-------------------|
| SMA/EMA (20) | 20 | 30 |
| SMA/EMA (50) | 50 | 60 |
| SMA/EMA (200) | 200 | 220 |
| RSI (14) | 14 | 30 |
| MACD (12,26,9) | 26 + 9 = 35 | 50 |
| Bollinger Bands (20) | 20 | 30 |

```python
# Example: Strategy using multiple indicators
# Longest indicator is 200-period MA, so warmup should be at least 200 + buffer
data_sources = [
    DataSource(
        identifier="btc_data",
        symbol="BTC/EUR",
        time_frame="4h",
        warmup_window=250,  # Covers 200-period MA + buffer
        market="BITVAVO"
    )
]
```

## Data Types

### OHLCV Data (Default)

```python
from investing_algorithm_framework import DataSource, DataType

ohlcv_source = DataSource(
    identifier="btc_ohlcv",
    symbol="BTC/EUR",
    time_frame="1h",
    warmup_window=100,
    market="BITVAVO",
    data_type=DataType.OHLCV  # Default
)
```

### Ticker Data

```python
ticker_source = DataSource(
    identifier="btc_ticker",
    symbol="BTC/EUR",
    market="BITVAVO",
    data_type=DataType.TICKER
)
```

## Data Source Patterns

### Pattern 1: Same Symbol, Multiple Timeframes

```python
data_sources = [
    DataSource(identifier="btc_1d", symbol="BTC/EUR", time_frame="1d", warmup_window=50, market="BITVAVO"),
    DataSource(identifier="btc_4h", symbol="BTC/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    DataSource(identifier="btc_1h", symbol="BTC/EUR", time_frame="1h", warmup_window=200, market="BITVAVO"),
]
```

### Pattern 2: Multiple Symbols, Same Timeframe

```python
data_sources = [
    DataSource(identifier="btc_4h", symbol="BTC/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    DataSource(identifier="eth_4h", symbol="ETH/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    DataSource(identifier="ada_4h", symbol="ADA/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
]
```

### Pattern 3: Correlation Analysis

```python
class CorrelationStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC"]
    trading_symbol = "EUR"

    data_sources = [
        DataSource(identifier="btc", symbol="BTC/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
        DataSource(identifier="eth", symbol="ETH/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    ]

    def _calculate_correlation(self, df1, df2, window=20):
        """Calculate rolling correlation between two assets"""
        returns1 = df1["Close"].pct_change()
        returns2 = df2["Close"].pct_change()
        return returns1.rolling(window).corr(returns2)

    def generate_buy_signals(self, data):
        btc_df = data["btc"]
        eth_df = data["eth"]

        # Calculate correlation
        correlation = self._calculate_correlation(btc_df, eth_df)

        # Buy BTC when correlation is high and ETH is rising
        eth_momentum = eth_df["Close"].pct_change(5)

        buy_signal = (correlation > 0.7) & (eth_momentum > 0.02)

        return {"BTC": buy_signal}

    def generate_sell_signals(self, data):
        btc_df = data["btc"]
        ma = btc_df["Close"].rolling(20).mean()
        return {"BTC": btc_df["Close"] < ma}
```

## Retrieving Data for Analysis

Use `get_backtest_data` to retrieve all data sources for visualization and analysis:

```python
from investing_algorithm_framework import create_app, BacktestDateRange
from datetime import datetime, timezone
import matplotlib.pyplot as plt

app = create_app()
# ... configure app with portfolio and strategy ...

# Get all data
data = app.get_backtest_data(
    strategy=MultiAssetStrategy(),
    backtest_date_range=BacktestDateRange(
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
    )
)

# Access by identifier
btc_df = data["btc_4h"]
print(btc_df.head())

# Plot all assets
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
symbols = ["btc_4h", "eth_4h", "ada_4h", "dot_4h"]

for ax, identifier in zip(axes.flat, symbols):
    df = data[identifier]
    ax.plot(df.index, df["Close"])
    ax.set_title(identifier.upper())
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

## Best Practices

### 1. Use Meaningful Identifiers

```python
# Good: Descriptive identifiers
data_sources = [
    DataSource(identifier="btc_4h_trend", ...),
    DataSource(identifier="btc_1h_entry", ...),
    DataSource(identifier="eth_daily_ma", ...),
]

# Avoid: Generic identifiers
data_sources = [
    DataSource(identifier="data1", ...),
    DataSource(identifier="data2", ...),
]
```

### 2. Match Timeframe to Strategy Interval

```python
class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4  # Runs every 4 hours

    data_sources = [
        DataSource(
            identifier="btc_data",
            time_frame="4h",  # Match strategy interval
            ...
        )
    ]
```

### 3. Sufficient Warmup Windows

```python
# Always include buffer for your longest indicator
longest_indicator_period = 200
buffer = 50

data_sources = [
    DataSource(
        warmup_window=longest_indicator_period + buffer,
        ...
    )
]
```

### 4. Use pandas=True for Analysis

```python
data_sources = [
    DataSource(
        identifier="btc_data",
        symbol="BTC/EUR",
        time_frame="1h",
        warmup_window=100,
        market="BITVAVO",
        pandas=True  # Easier for indicator calculations
    )
]
```

### 5. Consistent Naming Convention

```python
# Use consistent identifier patterns: symbol_timeframe
data_sources = [
    DataSource(identifier="btc_4h", ...),
    DataSource(identifier="eth_4h", ...),
    DataSource(identifier="btc_1d", ...),
]
```

### 6. Handle Missing Data

```python
def generate_buy_signals(self, data):
    signals = {}

    for symbol in self.symbols:
        identifier = f"{symbol.lower()}_4h"

        if identifier not in data:
            print(f"Warning: No data for {identifier}")
            continue

        df = data[identifier]

        if len(df) < 50:  # Minimum required data
            signals[symbol] = pd.Series([False] * len(df), index=df.index)
            continue

        # Normal signal generation
        ma = df["Close"].rolling(50).mean()
        signals[symbol] = df["Close"] > ma

    return signals
```

## Next Steps

- Learn about [Backtest Data](backtest_data) for data visualization
- Explore [Download Data](download) to fetch historical data
- Check out [Trading Strategies](../Getting%20Started/strategies) for strategy implementation
