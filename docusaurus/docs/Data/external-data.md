---
sidebar_position: 4
---

# Load External Data

Load CSV, JSON, or Parquet data from any URL during strategy execution or as a pre-declared data source. Use this to bring in sentiment scores, earnings data, macro indicators, or any external dataset.

## Overview

The framework provides two ways to load external data:

1. **Data Sources** — Declare `DataSource.from_csv()`, `DataSource.from_json()`, or `DataSource.from_parquet()` in your strategy's `data_sources` list. Data is fetched automatically and available in your `data` dict.
2. **Context methods** — Call `context.fetch_csv()`, `context.fetch_json()`, or `context.fetch_parquet()` on demand inside your strategy's `run_strategy` method.

Both approaches support caching, refresh intervals, date parsing, and pre/post-processing callbacks.

## Supported Formats

| Format | DataSource Factory | Context Method | Provider Class |
|--------|-------------------|----------------|----------------|
| CSV | `DataSource.from_csv()` | `context.fetch_csv()` | `CSVURLDataProvider` |
| JSON | `DataSource.from_json()` | `context.fetch_json()` | `JSONURLDataProvider` |
| Parquet | `DataSource.from_parquet()` | `context.fetch_parquet()` | `ParquetURLDataProvider` |

## Using DataSource (Pre-Declared)

Declare external data sources alongside your market data. The framework fetches them automatically before your strategy runs.

### CSV

```python
from investing_algorithm_framework import TradingStrategy, DataSource, TimeUnit

class SentimentStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["BTC"]

    data_sources = [
        DataSource.from_csv(
            identifier="sentiment",
            url="https://example.com/crypto_sentiment.csv",
            date_column="date",
            date_format="%Y-%m-%d",
            cache=True,
            refresh_interval="1d",
        ),
    ]

    def run_strategy(self, context, data):
        sentiment_df = data["sentiment"]
        latest_score = sentiment_df["score"][-1]

        if latest_score > 0.7:
            context.create_limit_order(...)
```

### JSON

```python
data_sources = [
    DataSource.from_json(
        identifier="earnings",
        url="https://api.example.com/earnings.json",
        date_column="report_date",
        date_format="%Y-%m-%d",
        refresh_interval="1d",
    ),
]
```

The JSON data must be either:
- An **array of objects** (records orientation): `[{"date": "2024-01-01", "value": 42}, ...]`
- An **object of arrays** (columnar orientation): `{"date": ["2024-01-01", ...], "value": [42, ...]}`

### Parquet

```python
data_sources = [
    DataSource.from_parquet(
        identifier="features",
        url="https://storage.example.com/features.parquet",
        date_column="date",
        refresh_interval="1W",
    ),
]
```

> **Note:** Parquet is a binary format, so `pre_process` callbacks are not supported. Use `post_process` instead.

## Using Context Methods (On-Demand)

Fetch data dynamically inside your strategy without pre-declaring it as a data source. Useful when the URL depends on runtime values or when you only need data conditionally.

```python
class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["BTC"]

    def run_strategy(self, context, data):
        # Fetch CSV on demand
        sentiment = context.fetch_csv(
            url="https://example.com/sentiment.csv",
            date_column="date",
            cache=True,
            refresh_interval="1d",
        )

        # Fetch JSON on demand
        earnings = context.fetch_json(
            url="https://api.example.com/earnings",
            date_column="report_date",
        )

        # Fetch Parquet on demand
        features = context.fetch_parquet(
            url="https://storage.example.com/features.parquet",
        )
```

## Parameters

All three factory methods and context methods accept the same core parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `identifier` | `str` | — | Unique identifier (DataSource only). |
| `url` | `str` | — | URL to fetch the data from. |
| `date_column` | `str` | `None` | Name of the column containing dates. Parsed to `polars.Datetime`. |
| `date_format` | `str` | `None` | strftime format for parsing dates (e.g., `"%Y-%m-%d"`). Auto-detected if omitted. |
| `cache` | `bool` | `True` | Cache fetched data locally to avoid repeated downloads. |
| `refresh_interval` | `str` | `None` | How often to re-fetch: `"1m"`, `"5m"`, `"15m"`, `"30m"`, `"1h"`, `"4h"`, `"1d"`, `"1W"`. |
| `pre_process` | `callable` | `None` | Transform raw text before parsing. Receives `str`, returns `str`. Not available for Parquet. |
| `post_process` | `callable` | `None` | Transform the parsed DataFrame. Receives `DataFrame`, returns `DataFrame`. |

## Pre/Post Processing

### Pre-Processing

Clean or transform raw text before it is parsed into a DataFrame. Useful for removing comment lines, fixing delimiters, or filtering rows.

```python
def clean_csv(text):
    """Remove comment lines starting with #."""
    lines = [line for line in text.split("\n") if not line.startswith("#")]
    return "\n".join(lines)

DataSource.from_csv(
    identifier="cleaned_data",
    url="https://example.com/messy_data.csv",
    pre_process=clean_csv,
)
```

### Post-Processing

Transform the parsed DataFrame — add computed columns, filter rows, change types.

```python
import polars as pl

def add_z_score(df):
    """Add a z-score column for the score field."""
    mean = df["score"].mean()
    std = df["score"].std()
    return df.with_columns(
        ((pl.col("score") - mean) / std).alias("z_score")
    )

DataSource.from_csv(
    identifier="scored_data",
    url="https://example.com/scores.csv",
    post_process=add_z_score,
)
```

## Caching

External data is cached both **in memory** and **on disk**:

- **In-memory cache** — Avoids re-parsing on every strategy tick.
- **File cache** — Stored inside your resource directory (e.g., `resources/data/`). Falls back to `.data_cache/` if no resource directory is configured.
- **Refresh interval** — When set, the framework re-fetches data after the specified interval expires. Staleness is determined by the cache file's modification time, so it survives process restarts.

Cache files are named using an MD5 hash of the URL, so different URLs never collide.

### Cloud Deployments (AWS Lambda / Azure Functions)

When a state handler (`AWSS3StorageStateHandler` or `AzureBlobStorageStateHandler`) is configured, cache files are automatically persisted because they live inside the resource directory that state handlers sync:

1. **Load state** — Cache files are restored from S3 / Azure Blob to `resources/data/`
2. **Check interval** — The file modification time is compared against `refresh_interval`
3. **Skip or re-fetch** — Only fetches from the URL if the interval has elapsed
4. **Save state** — Updated cache files are synced back to cloud storage

This means `refresh_interval` works correctly across cold starts — no extra configuration needed.

## Backtesting

External data sources work with backtesting. The framework calls `prepare_backtest_data()` before the backtest starts, and `get_backtest_data()` on each tick. If a `date_column` is configured, data is automatically filtered to only include rows up to the current backtest date.

```python
data_sources = [
    DataSource.from_csv(
        identifier="macro",
        url="https://example.com/macro_indicators.csv",
        date_column="date",
        date_format="%Y-%m-%d",
    ),
]
```

During backtesting, `data["macro"]` will only contain rows where `date <= current_backtest_date`, giving you realistic point-in-time data.

## Next Steps

- Learn about [Data Sources](data-sources) for market data configuration
- Explore [Custom Data Providers](../Advanced%20Concepts/custom-data-providers) to build your own provider
- Check out [Strategies](../Getting%20Started/strategies) for strategy implementation
