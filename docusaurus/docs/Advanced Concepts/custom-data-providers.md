---
sidebar_position: 6
---

# Custom Data Providers

Learn how the data provider system works and how to build your own data provider to integrate any data source into the framework.

## How Data Providers Work

The framework uses a **priority-based provider resolution** system. When a strategy declares a `DataSource`, the framework automatically finds the right data provider to fulfill it:

1. **Registration** — All data providers are registered in a `DataProviderIndex`
2. **Matching** — When a `DataSource` is declared, the framework calls `has_data()` on each registered provider
3. **Priority** — If multiple providers match, the one with the lowest `priority` value wins
4. **Instantiation** — The winning provider's `copy()` method creates a dedicated instance for that data source
5. **Data retrieval** — The framework calls `get_data()` (live) or `get_backtest_data()` (backtesting) on the matched provider

```
DataSource("AAPL", market="YAHOO", time_frame="1d")
                │
                ▼
      ┌─────────────────────┐
      │  DataProviderIndex   │
      │  ┌─────────────────┐ │
      │  │  has_data()?    │ │  ← loops all registered providers
      │  └─────────────────┘ │
      └──────────┬──────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
  CCXT        Yahoo       Polygon
  ✗            ✓            ✗
                │
                ▼
         copy(data_source)
                │
                ▼
       Dedicated instance
       for AAPL / 1d / YAHOO
```

## Built-in Data Providers

The framework ships with these OHLCV data providers:

| Provider | Market | API Key Required | Supported Assets |
|----------|--------|-----------------|------------------|
| `CCXTOHLCVDataProvider` | Any CCXT exchange (e.g. `BINANCE`, `BITVAVO`) | Depends on exchange | Crypto |
| `YahooOHLCVDataProvider` | `YAHOO` | No | Stocks, ETFs, indices, forex, crypto |
| `AlphaVantageOHLCVDataProvider` | `ALPHA_VANTAGE` | Yes | Stocks, forex, crypto |
| `PolygonOHLCVDataProvider` | `POLYGON` | Yes | US stocks, options, forex, crypto |
| `CSVOHLCVDataProvider` | N/A | No | Any (from local CSV files) |
| `PandasOHLCVDataProvider` | N/A | No | Any (from pandas DataFrames) |

All OHLCV providers return data as [Polars](https://pola.rs/) DataFrames with columns: `Datetime`, `Open`, `High`, `Low`, `Close`, `Volume`.

## Creating a Custom OHLCV Data Provider

The easiest way to add a new data source is to extend `OHLCVDataProviderBase`. This base class handles all the boilerplate — storage caching, date range resolution, backtesting, `copy()` — and you only need to implement the API-specific download logic.

### Minimal Example

```python
import polars as pl
from datetime import datetime
from investing_algorithm_framework import OHLCVDataProviderBase

class MyBrokerOHLCVDataProvider(OHLCVDataProviderBase):
    # The market string that DataSources will use
    market_name = "MY_BROKER"

    # Unique identifier for this provider
    data_provider_identifier = "my_broker_ohlcv"

    # Map framework timeframes to your API's format
    timeframe_map = {
        "1m": "1min",
        "5m": "5min",
        "1h": "60min",
        "1d": "daily",
    }

    def _download_ohlcv(
        self,
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        """
        Download OHLCV data from your broker's API.

        Must return a Polars DataFrame with columns:
        Datetime (timezone-aware UTC), Open, High, Low, Close, Volume
        """
        import my_broker_sdk

        api_key = self._get_api_key()  # reads from MarketCredential
        client = my_broker_sdk.Client(api_key)

        interval = self._get_provider_interval()  # resolves from timeframe_map
        raw_data = client.get_candles(
            symbol=symbol,
            interval=interval,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        # Convert to the required DataFrame format
        import pandas as pd
        df = pd.DataFrame(raw_data)
        df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        })

        return pl.from_pandas(
            df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )
```

### Using It

```python
from investing_algorithm_framework import (
    create_app,
    DataSource,
    MarketCredential,
    TradingStrategy,
    TimeUnit,
)

app = create_app()

# Register API credentials
app.add_market_credential(
    MarketCredential(
        market="MY_BROKER",
        api_key="your_api_key",
    )
)

# Register the custom provider
app.add_data_provider(MyBrokerOHLCVDataProvider())

# Use it in a strategy
class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["AAPL"]
    trading_symbol = "USD"

    data_sources = [
        DataSource(
            identifier="aapl_daily",
            market="MY_BROKER",     # matches market_name
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",        # must be in timeframe_map
            warmup_window=50,
        ),
    ]
```

## OHLCVDataProviderBase Reference

### Class Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `market_name` | `str` | Yes | The market identifier string (e.g. `"MY_BROKER"`). DataSources match against this. |
| `timeframe_map` | `dict` | Yes | Maps framework timeframe strings (`"1m"`, `"1d"`, etc.) to provider-specific values. |
| `data_provider_identifier` | `str` | Yes | Unique identifier for this provider type. |

### Methods to Override

#### `_download_ohlcv()` (required)

```python
def _download_ohlcv(
    self,
    symbol: str,
    time_frame,
    start_date: datetime,
    end_date: datetime,
) -> pl.DataFrame:
```

Downloads OHLCV data from your external API. Must return a Polars DataFrame with columns `Datetime`, `Open`, `High`, `Low`, `Close`, `Volume`. The `Datetime` column must be timezone-aware UTC.

Use `self._get_provider_interval()` to get the mapped interval value from `timeframe_map`.

Use `self._get_api_key()` to retrieve the API key from the configured `MarketCredential`.

#### `_validate_symbol()` (optional)

```python
def _validate_symbol(self, data_source: DataSource) -> bool:
```

Called during `has_data()` to validate whether the provider supports the requested symbol. Defaults to returning `True`. Override this if your API provides a way to verify symbol availability.

#### `_storage_file_suffix()` (optional)

```python
def _storage_file_suffix(self) -> str:
```

Returns the suffix used for cached CSV file names. Defaults to `market_name.lower()`. Override if you need a different naming convention (e.g. `"alpha_vantage"` instead of `"alpha_vantage"`).

### Inherited Methods (no override needed)

These are handled automatically by the base class:

- `has_data()` — checks market name, timeframe support, storage cache, and calls `_validate_symbol()`
- `get_data()` — resolves date ranges, checks cache, calls `_download_ohlcv()`, handles storage
- `prepare_backtest_data()` — downloads full range and caches for backtesting
- `get_backtest_data()` — slices cached data by backtest index date and window
- `copy()` — creates a dedicated provider instance for a matched DataSource
- `get_number_of_data_points()` — calculates expected data points for a date range
- `get_missing_data_dates()` — returns dates with missing data

## Creating a Fully Custom Data Provider

If you need to provide non-OHLCV data or need complete control, extend `DataProvider` directly. You must implement all abstract methods:

```python
from investing_algorithm_framework import DataProvider, DataType, DataSource

class CustomSentimentDataProvider(DataProvider):
    data_type = DataType.CUSTOM_DATA
    data_provider_identifier = "sentiment_provider"

    def has_data(self, data_source, start_date=None, end_date=None):
        """Return True if this provider can serve the data source."""
        return (
            data_source.data_type == "CUSTOM_DATA"
            and data_source.market == "SENTIMENT_API"
        )

    def get_data(self, date=None, start_date=None, end_date=None, save=False):
        """Fetch live data."""
        # Your API call here
        return {"sentiment_score": 0.75, "volume_buzz": 1.2}

    def prepare_backtest_data(
        self, backtest_start_date, backtest_end_date,
        fill_missing_data=False, show_progress=False,
    ):
        """Download and cache historical data for backtesting."""
        self.data = self._fetch_historical(
            backtest_start_date, backtest_end_date
        )

    def get_backtest_data(
        self, backtest_index_date, backtest_start_date=None,
        backtest_end_date=None, data_source=None,
    ):
        """Return data for a specific backtest date."""
        return self.data.get(backtest_index_date)

    def copy(self, data_source):
        """Create a new instance configured for this data source."""
        provider = CustomSentimentDataProvider()
        provider.symbol = data_source.symbol
        provider.market = data_source.market
        return provider

    def get_number_of_data_points(self, start_date, end_date):
        return 0

    def get_missing_data_dates(self, start_date, end_date):
        return []

    def get_data_source_file_path(self):
        return None
```

## Provider Priority

When multiple providers can serve the same DataSource, the framework picks the one with the lowest `priority` value:

```python
class PrimaryProvider(OHLCVDataProviderBase):
    market_name = "STOCKS"
    priority = 0  # highest priority (default)
    ...

class FallbackProvider(OHLCVDataProviderBase):
    market_name = "STOCKS"
    priority = 10  # lower priority, used as fallback
    ...
```

Custom providers added via `app.add_data_provider()` receive a default priority of `3`. Built-in providers have a priority of `0`.

## API Key Configuration

Providers that require authentication use `MarketCredential`:

```python
from investing_algorithm_framework import MarketCredential

app.add_market_credential(
    MarketCredential(
        market="MY_BROKER",       # must match provider's market_name
        api_key="your_api_key",
        secret_key="your_secret", # optional
    )
)
```

Inside your provider, call `self._get_api_key()` to retrieve the key. This reads from the `MarketCredential` whose `market` matches your provider's `market_name`.

API keys can also be configured via environment variables. `MarketCredential` automatically reads `{MARKET}_API_KEY` and `{MARKET}_SECRET_KEY`:

```bash
export MY_BROKER_API_KEY=your_api_key
export MY_BROKER_SECRET_KEY=your_secret
```

```python
# This will auto-read from MY_BROKER_API_KEY env var
app.add_market_credential(MarketCredential(market="MY_BROKER"))
```

## Storage and Caching

`OHLCVDataProviderBase` automatically caches downloaded data as CSV files. Files are named using the pattern:

```
{symbol}_{timeframe}_{suffix}.csv
```

For example: `AAPL_1d_my_broker.csv`

The storage directory is resolved in order:
1. `storage_directory` passed to the constructor
2. `storage_path` from the DataSource
3. `RESOURCE_DIRECTORY/data/` from the app config

To disable caching, don't configure a storage directory and don't set `save=True` on the DataSource.
