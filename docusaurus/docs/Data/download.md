---
id: download
title: Download Market Data
sidebar_label: Download Market Data
---

## Overview

The `download` function is a utility provided by the **Investing Algorithm Framework** that allows you to retrieve historical market data for specific symbols (assets), including OHLCV data (Open, High, Low, Close, Volume), ticker data, and more. This function is particularly useful for:

- Backtesting trading strategies
- Performing exploratory data analysis
- Preprocessing input data for machine learning models

---

## Function Signature

```python
def download(
    symbol: str,
    market=None,
    date=None,
    time_frame: str = None,
    data_type: str = "ohlcv",
    start_date: str = None,
    end_date: str = None,
    window_size: int = 200,
    pandas: bool = True,
    save: bool = True,
    storage_path: str = None,
) -> Union[pandas.DataFrame, polars.DataFrame]
```

| Parameter      | Type   | Description                                                                      |
| -------------- | ------ | -------------------------------------------------------------------------------- |
| `symbol`       | `str`  | The symbol (e.g., `"BTC/USDT"`) for which data is downloaded.                    |
| `market`       | `str`  | (Optional) The market to download data from (e.g., `"binance"`).                 |
| `date`         | `str`  | (Optional) Specific date to retrieve data for.                                   |
| `time_frame`   | `str`  | The time frame for data (e.g., `"1d"`, `"1h"`).                                  |
| `data_type`    | `str`  | Type of data to retrieve: `"ohlcv"` (default) or `"ticker"`.                     |
| `start_date`   | `str`  | (Optional) Start of the date range to retrieve data.                             |
| `end_date`     | `str`  | (Optional) End of the date range.                                                |
| `window_size`  | `int`  | Number of records to retrieve (default: 200).                                    |
| `pandas`       | `bool` | If `True`, returns a `pandas.DataFrame`; otherwise returns a `polars.DataFrame`. |
| `save`         | `bool` | If `True`, saves the downloaded data to disk.                                    |
| `storage_path` | `str`  | (Optional) Path to store the data when `save=True`.                              |


## Returns
The function returns a DataFrame (pandas or polars) containing the requested market data, ready for analysis, visualization, or model training.

## Why It's Useful?
This function streamlines the process of acquiring market data by:
* Automatically selecting the correct data provider 
* Supporting multiple formats (pandas or polars)
* Handling flexible input dates and ranges 
* Offering a simple way to persist downloaded data to disk

## Example Use Cases
📈 Backtesting a Strategy

```python
df = download("BTC/USDT", market="binance", time_frame="1d", start_date="2021-01-01", end_date="2022-01-01")
```
Use the returned df to simulate your strategy’s performance over historical data.

## 🧠 Preparing Data for Machine Learning
```python
df = download("ETH/USDT", market="binance", time_frame="1h", window_size=500, pandas=True)
features = df[["close", "volume"]]
```

This enables quick preparation of time-series datasets for supervised learning tasks.

## 💾 Saving Data for Offline Analysis

```python
download("SOL/USDT", market="binance", time_frame="1d", save=True, storage_path="./data/")
```

## Internals
The function relies on:
* ConfigurationService and MarketCredentialService to determine available providers and credentials.
* DataProviderService to abstract away direct API calls.
* dateutil.parser for robust datetime parsing.
* Default providers registered via get_default_data_providers() and get_default_ohlcv_data_providers().
