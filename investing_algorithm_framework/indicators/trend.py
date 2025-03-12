import pandas as pd
from typing import Union, List
from datetime import timedelta
import tulipy as tp
import numpy as np
from investing_algorithm_framework.domain import OperationalException, \
    DateRange

"""
This module contains functions for trend analysis. Trend analysis is
the process of analyzing the direction of the price of an asset.
or the direction of the market as a whole. This is done by analyzing the
moving averages of the price data or
indicators such as the RSI.
"""


def is_uptrend(
    data: Union[pd.DataFrame, pd.Series],
    fast_column="SMA_50",
    slow_column="SMA_200"
) -> bool:
    """
    Check if the price data is in a upturn. By default if will check if the
    fast key *SMA_50* is above the slow key *SMA_200*.

    Parameters:
        data: pd.DataFrame or pd.Series - The input pandas DataFrame or Series.
        fast_key: str - The key for the fast moving average (default: SMA_50).
        slow_key: str - The key for the slow moving average (default: SMA_200).

    Returns:
        - Boolean indicating if the price data is in an upturn.
    """

    if not isinstance(data, pd.Series) and not isinstance(data, pd.DataFrame):
        raise OperationalException(
            "Provided data must be of type pandas series or pandas dataframe"
        )

    if isinstance(data, pd.Series):

        # Check if the data keys are present in the data
        if fast_column not in data.index:
            raise OperationalException(
                f"Data column {fast_column} not present in the data."
            )
        if slow_column not in data.index:
            raise OperationalException(
                f"Data columns {slow_column} not present in the data."
            )

        return data[fast_column] > data[slow_column]

    # Check if the data keys are present in the data
    if fast_column not in data.columns:
        raise OperationalException(
            f"Data column {fast_column} not present in the data."
        )

    if slow_column not in data.columns:
        raise OperationalException(
            f"Data columns {slow_column} not present in the data."
        )

    # Check if the index of the data is a datetime index
    if not isinstance(data.index, pd.DatetimeIndex):
        raise OperationalException(
            "Data index must be a datetime index. " +
            f"It is currently of type: {str(type(data.index))}"
        )

    # Check if the data is not empty
    if len(data) == 0:
        return False

    return data[fast_column].iloc[-1] > data[slow_column].iloc[-1]


def is_downtrend(
    data: Union[pd.DataFrame, pd.Series],
    fast_column="SMA_50",
    slow_column="SMA_200"
) -> bool:
    """
    Function to check if the price data is in a downturn.

    Args:
        data (Union[pd.DataFrame, pd.Series]): The input pandas
            DataFrame or Series.
        fast_column (str): The key for the fast moving
            average (default: SMA_50).
        slow_column (str): The key for the slow moving
            average (default: SMA_200).

    Returns:
        bool: Boolean indicating if the price data is in a downturn.
    """

    if not isinstance(data, pd.Series) and not isinstance(data, pd.DataFrame):
        raise OperationalException(
            "Provided data must be of type pandas series or pandas dataframe"
        )

    if isinstance(data, pd.Series):

        # Check if the data keys are present in the data
        if fast_column not in data.index or slow_column not in data.index:
            raise OperationalException("Data keys not present in the data.")

        return data[fast_column] < data[slow_column]

    # Check if the data keys are present in the data
    if fast_column not in data.columns or slow_column not in data.columns:
        raise ValueError("Data keys not present in the data.")

    # Check if the index of the data is a datetime index
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data index must be a datetime index.")

    # Check if the data is not empty
    if len(data) == 0:
        return False

    return data[fast_column].iloc[-1] < data[slow_column].iloc[-1]


def is_crossover(data, key1, key2, strict=True) -> bool:
    """
    Check if the given keys have crossed over.

    Parameters:
        - data: pd.DataFrame - The input pandas DataFrame.
        - key1: str - The first key to compare.
        - key2: str - The second key to compare.
        - strict: bool - Whether to check for a strict crossover.

    Returns:
        - Boolean indicating if the keys have crossed over.
    """

    if len(data) < 2:
        return False

    if strict:
        return data[key1].iloc[-1] > data[key2].iloc[-1] \
            and data[key1].iloc[-2] < data[key2].iloc[-2]

    return data[key1].iloc[-1] >= data[key2].iloc[-1] \
        and data[key1].iloc[-2] <= data[key2].iloc[-2]


def get_up_and_downtrends(data: pd.DataFrame) -> List[DateRange]:
    """
    Function to get the up and down trends of a pandas dataframe.

    Params:
        data: pd.Dataframe - instance of pandas Dateframe
        containing OHLCV data.

    Returns:
        List of date ranges that with up_trend and down_trend
        flags specified.
    """

    # Check if the data is larger then 200 data points
    if len(data) < 200:
        raise OperationalException(
            "The data must be larger than 200 data " +
            "points to determine up and down trends."
        )

    copy = data.copy()
    copy = get_sma(copy, source_column_name="Close", period=50)
    copy = get_sma(copy, source_column_name="Close", period=200)

    # Make selections based on the trend
    current_trend = None
    start_date = copy.index[0]
    selection = copy
    start_date_range = start_date
    date_ranges = []

    for idx, row in enumerate(selection.itertuples(index=True), start=1):
        selected_rows = selection.iloc[:idx]

        # Check if last row is null for the SMA_50 and SMA_200
        if pd.isnull(selected_rows["SMA_Close_50"].iloc[-1]) \
                or pd.isnull(selected_rows["SMA_Close_200"].iloc[-1]):
            continue

        if is_uptrend(
            selected_rows,
            fast_column="SMA_Close_50",
            slow_column="SMA_Close_200"
        ):
            if current_trend != 'Up':

                if current_trend is not None:
                    end_date = selection.loc[
                        row.Index - timedelta(days=1)
                    ].name
                    date_ranges.append(
                        DateRange(
                            start_date=start_date_range,
                            end_date=end_date,
                            name=current_trend,
                            down_trend=True
                        )
                    )
                    start_date_range = row.Index
                    current_trend = 'Up'
                else:
                    current_trend = 'Up'
                    start_date_range = row.Index
        else:

            if current_trend != 'Down':

                if current_trend is not None:
                    end_date = selection.loc[
                        row.Index - timedelta(days=1)
                    ].name
                    date_ranges.append(
                        DateRange(
                            start_date=start_date_range,
                            end_date=end_date,
                            name=current_trend,
                            up_trend=True
                        )
                    )
                    start_date_range = row.Index
                    current_trend = 'Down'
                else:
                    current_trend = 'Down'
                    start_date_range = row.Index

    if current_trend is not None:
        end_date = selection.index[-1]

        if current_trend == 'Up':
            date_ranges.append(
                DateRange(
                    start_date=start_date_range,
                    end_date=end_date,
                    name=current_trend,
                    up_trend=True
                )
            )
        else:
            date_ranges.append(
                DateRange(
                    start_date=start_date_range,
                    end_date=end_date,
                    name=current_trend,
                    down_trend=True
                )
            )

    return date_ranges


def get_sma(
    data: pd.DataFrame,
    period=50,
    source_column_name="Close",
    result_column_name=None
):
    """
    Function to add Smoothed moving average to a pandas dataframe.

    Parameters:
        data: pd.Dataframe - instance of pandas Dateframe.
        period: int - the number of data points the SMA needs
            to take into account.
        source_column_name: str - the source_column_name that
            will be used to calculate the SMA.
        result_column_name: (option) str - if set, this
            will be used as column in the
        dataframe where the result will be written to. If
            not set the result column is
        named 'SMA_{key}_{period}'.

    Returns:
        Pandas dataframe with SMA column added,
        named 'sma_{key}_{period}' or name
        according to the result_column_name
    """

    if len(data) < period:
        raise OperationalException(
            "The data must be larger than the period " +
            f"{period} to calculate the SMA. The data " +
            f"only contains {len(data)} data points."
        )

    sma = tp.sma(data[source_column_name].to_numpy(), period=period)

    # Pad NaN values for initial rows with a default value,
    #  e.g., 0 up to period - 1
    sma = np.concatenate((np.full(period - 1, 0), sma))

    if result_column_name:
        data[result_column_name] = sma
    else:
        data[f"SMA_{source_column_name}_{period}"] = sma

    return data


def get_rsi(
    data: pd.DataFrame,
    period=50,
    source_column_name="Close",
    result_column_name=None
):
    """
    Function to add Relative Strength Index (RSI) to a pandas dataframe.

    Params:
        data: pd.Dataframe - instance of pandas Dateframe.
        period: int - the number of data points the RSI needs
            to take into account.
        source_column_name: str - the source_column_name that
            will be used to calculate the RSI.
        result_column_name: (option) str - if set, this
            will be used as column in the
        dataframe where the result will be written to. If
            not set the result column is
        named 'RSI_{key}_{period}'.

    Returns:
        Pandas dataframe with RSI column added,
        named 'RSI_{period}' or named according to the
        result_column_name
    """
    # Calculate RSI
    rsi_values = tp.rsi(data[source_column_name].to_numpy(), period=period)

    # Pad NaN values for initial rows with a default value, e.g., 0
    rsi_values = np.concatenate((np.full(period, 0), rsi_values))

    if result_column_name:
        data[result_column_name] = rsi_values
    else:
        data[f"RSI_{period}"] = rsi_values

    return data


def get_ema(
    data: pd.DataFrame,
    period=50,
    source_column_name="Close",
    result_column_name=None
):
    """
    Add an Exponential Moving Average (EMA) to the data DataFrame.

    Parameters:
        data: pd.DataFrame - The input pandas DataFrame.
        period: int - The period for the EMA.
        source_column_name: str - The source column name.
        result_column_name: str - The result column name.

    Returns:
        Pandas dataframe with EMA column added,
        named 'EMA_{period}' or named according to the
        result_column_name
    """

    if source_column_name not in data.columns:
        raise OperationalException(
            f"Source column {source_column_name} not present in the data."
        )

    ema = tp.ema(data[source_column_name].to_numpy(), period=period)

    if result_column_name:
        data[result_column_name] = ema
    else:
        data[f"EMA_{period}"] = ema
    return data


def get_adx(data: pd.DataFrame, period=14) -> pd.DataFrame:
    """
    Add the Average Directional Index (ADX) to the data DataFrame.

    Parameters:
        data: pd.DataFrame - The input pandas DataFrame with OHLCV data.
        period: int - The period for the ADX.

    Returns:
        The input pandas DataFrame with the ADX added. The ADX consists out of
        three columns: +DI, -DI, and ADX.
    """
    plus_di, min_di = tp.di(
        high=data["High"].to_numpy(),
        low=data["Low"].to_numpy(),
        close=data["Close"].to_numpy(),
        period=period
    )
    adx = tp.adx(
        high=data["High"].to_numpy(),
        low=data["Low"].to_numpy(),
        close=data["Close"].to_numpy(),
        period=period
    )

    # Pad NaN values for initial rows with a default value, e.g., 0
    plus_di = np.concatenate((np.full(period - 1, 0), plus_di))
    min_di = np.concatenate((np.full(period - 1, 0), min_di))
    adx = np.concatenate((np.full(period + 12, 0), adx))

    # Assign adx values to the DataFrame
    data["+DI"] = plus_di
    data["-DI"] = min_di
    data["ADX"] = adx
    return data
