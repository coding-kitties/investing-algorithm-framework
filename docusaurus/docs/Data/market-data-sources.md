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

For strategies using multiple assets, multiple timeframes, or mixing different markets, see [Multiple Market Data Sources](multiple-market-data-sources).

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

**Installation:** `pip install investing-algorithm-framework[yahoo]`

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

**Installation:** `pip install investing-algorithm-framework[polygon]`

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

**Installation:** `pip install investing-algorithm-framework[alpha_vantage]`

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

## Next Steps

- Learn about [Multiple Market Data Sources](multiple-market-data-sources) for multi-asset, multi-timeframe, and cross-market strategies
- Explore [External Data](external-data) to load CSV, JSON, or Parquet from URLs
- Check out [Trading Strategies](../Getting%20Started/strategies) for strategy implementation
