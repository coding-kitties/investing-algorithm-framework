from typing import Union

import numpy as np
import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import OperationalException


def create_ohlcv_permutation(
    data: Union[pd.DataFrame, pl.DataFrame],
    start_index: int = 0,
    seed: int | None = None,
) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Create a permuted OHLCV dataset by shuffling relative price moves.

    Args:
        data: A single OHLCV DataFrame (pandas or polars)
            with columns ['Open', 'High', 'Low', 'Close', 'Volume'].
            For pandas: Datetime can be either
            index or a 'Datetime' column. For polars: Datetime
            must be a 'Datetime' column.
        start_index: Index at which the permutation should begin
            (bars before remain unchanged).
        seed: Random seed for reproducibility.

    Returns:
        DataFrame of the same type (pandas or polars) with
            permuted OHLCV values, preserving the datetime
            structure (index vs column) of the input.
    """

    if start_index < 0:
        raise OperationalException("start_index must be >= 0")

    if seed is None:
        seed = np.random.randint(0, 1_000_000)

    np.random.seed(seed)
    is_polars = isinstance(data, pl.DataFrame)

    # Normalize input to pandas
    if is_polars:
        has_datetime_col = "Datetime" in data.columns
        ohlcv_pd = data.to_pandas().copy()
        if has_datetime_col:
            time_index = pd.to_datetime(ohlcv_pd["Datetime"])
        else:
            time_index = np.arange(len(ohlcv_pd))
    else:
        has_datetime_col = "Datetime" in data.columns
        if isinstance(data.index, pd.DatetimeIndex):
            time_index = data.index
        elif has_datetime_col:
            time_index = pd.to_datetime(data["Datetime"])
        else:
            time_index = np.arange(len(data))
        ohlcv_pd = data.copy()

    # Prepare data
    n_bars = len(ohlcv_pd)
    perm_index = start_index + 1
    perm_n = n_bars - perm_index

    log_bars = np.log(ohlcv_pd[["Open", "High", "Low", "Close"]])

    # Start bar
    start_bar = log_bars.iloc[start_index].to_numpy()

    # Relative series
    rel_open = (log_bars["Open"] - log_bars["Close"].shift()).to_numpy()
    rel_high = (log_bars["High"] - log_bars["Open"]).to_numpy()
    rel_low = (log_bars["Low"] - log_bars["Open"]).to_numpy()
    rel_close = (log_bars["Close"] - log_bars["Open"]).to_numpy()

    # Shuffle independently
    idx = np.arange(perm_n)
    rel_high = rel_high[perm_index:][np.random.permutation(idx)]
    rel_low = rel_low[perm_index:][np.random.permutation(idx)]
    rel_close = rel_close[perm_index:][np.random.permutation(idx)]
    rel_open = rel_open[perm_index:][np.random.permutation(idx)]

    # Build permuted OHLC
    perm_bars = np.zeros((n_bars, 4))
    perm_bars[:start_index] = log_bars.iloc[:start_index].to_numpy()
    perm_bars[start_index] = start_bar

    for i in range(perm_index, n_bars):
        k = i - perm_index
        perm_bars[i, 0] = perm_bars[i - 1, 3] + rel_open[k]   # Open
        perm_bars[i, 1] = perm_bars[i, 0] + rel_high[k]       # High
        perm_bars[i, 2] = perm_bars[i, 0] + rel_low[k]        # Low
        perm_bars[i, 3] = perm_bars[i, 0] + rel_close[k]      # Close

    perm_bars = np.exp(perm_bars)

    # Rebuild OHLCV
    perm_df = pd.DataFrame(
        perm_bars,
        columns=["Open", "High", "Low", "Close"],
    )
    perm_df["Volume"] = ohlcv_pd["Volume"].values

    # Restore datetime structure
    if is_polars:
        if has_datetime_col:
            perm_df.insert(0, "Datetime", time_index)
        return pl.from_pandas(perm_df)
    else:
        if isinstance(data.index, pd.DatetimeIndex):
            perm_df.index = time_index
            perm_df.index.name = data.index.name or "Datetime"
        elif has_datetime_col:
            perm_df.insert(0, "Datetime", time_index)
        return perm_df
