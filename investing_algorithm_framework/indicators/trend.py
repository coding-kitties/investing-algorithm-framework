import importlib.util
import pandas as pd
from typing import Union, List
from datetime import timedelta
import tulipy as tp
import numpy as np
from investing_algorithm_framework.domain import OperationalException, \
    DateRange

if importlib.util.find_spec("scipy") is None \
        or importlib.util.find_spec("tulipy") is None \
        or importlib.util.find_spec("numpy") is None:
    raise ImportError(
        "You have not installed the indicators package"
    )

"""
This module contains functions for trend analysis. Trend analysis is
the process of analyzing the direction of the price of an asset.
or the direction of the market as a whole. This is done by analyzing the
moving averages of the price data or
indicators such as the RSI.
"""


def is_uptrend(
    data: Union[pd.DataFrame, pd.Series], fast_key="SMA_50", slow_key="SMA_200"
) -> bool:
    """
    Check if the price data is in a upturn.

    Parameters:
        data: pd.DataFrame or pd.Series - The input pandas DataFrame or Series.
        fast_key: str - The key for the fast moving average.
        slow_key: str - The key for the slow moving average.

    Returns:
        - Boolean indicating if the price data is in an upturn.
    """

    if not isinstance(data, pd.Series) and not isinstance(data, pd.DataFrame):
        raise OperationalException(
            "Provided data must be of type pandas series or pandas dataframe"
        )

    if isinstance(data, pd.Series):

        # Check if the data keys are present in the data
        if fast_key not in data.index or slow_key not in data.index:
            raise OperationalException("Data keys not present in the data.")

        return data[fast_key] > data[slow_key]

    # Check if the data keys are present in the data
    if fast_key not in data.columns or slow_key not in data.columns:
        raise OperationalException("Data keys not present in the data.")

    # Check if the index of the data is a datetime index
    if not isinstance(data.index, pd.DatetimeIndex):
        raise OperationalException("Data index must be a datetime index.")

    # Check if the data is not empty
    if len(data) == 0:
        return False

    return data[fast_key].iloc[-1] > data[slow_key].iloc[-1]


def is_downtrend(
    data: Union[pd.DataFrame, pd.Series], fast_key="SMA_50", slow_key="SMA_200"
) -> bool:
    """
    Check if the price data is in a downturn.
    """

    if not isinstance(data, pd.Series) and not isinstance(data, pd.DataFrame):
        raise OperationalException(
            "Provided data must be of type pandas series or pandas dataframe"
        )

    if isinstance(data, pd.Series):

        # Check if the data keys are present in the data
        if fast_key not in data.index or slow_key not in data.index:
            raise OperationalException("Data keys not present in the data.")

        return data[fast_key] < data[slow_key]

    # Check if the data keys are present in the data
    if fast_key not in data.columns or slow_key not in data.columns:
        raise ValueError("Data keys not present in the data.")

    # Check if the index of the data is a datetime index
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data index must be a datetime index.")

    # Check if the data is not empty
    if len(data) == 0:
        return False

    return data[fast_key].iloc[-1] < data[slow_key].iloc[-1]


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


def is_crossunder(data, key1, key2, strict=True) -> bool:
    """
    Check if the given keys have crossed under.

    Parameters:
        - data: pd.DataFrame - The input pandas DataFrame.
        - key1: str - The first key to compare.
        - key2: str - The second key to compare.
        - strict: bool - Whether to check for a strict crossover.

    Returns:
        - Boolean indicating if the keys have crossed under.
    """
    if len(data) < 2:
        return False

    if strict:
        return data[key1].iloc[-1] < data[key2].iloc[-1] \
            and data[key1].iloc[-2] > data[key2].iloc[-2]

    return data[key1].iloc[-1] <= data[key2].iloc[-1] \
        and data[key1].iloc[-2] >= data[key2].iloc[-2]


def has_crossed_upward(
    data: pd.DataFrame, key, threshold, strict=True
) -> bool:
    """
    Check if the given key has crossed upward.

    Parameters:
        - data: pd.DataFrame - The input pandas DataFrame.
        - key: str - The key to compare.
        - threshold: float - The threshold value to compare.
        - strict: bool - Whether to check for a strict crossover.

    Returns:
        - Boolean indicating if the key has crossed upward through the
        threshold within the given data frame.
    """

    # Ensure the key exists in the DataFrame
    if key not in data.columns:
        raise KeyError(f"Key '{key}' not found in DataFrame")

    # Identify where the values are below and above the threshold
    if strict:
        below_threshold = data[key].shift(1) < threshold
        above_threshold = data[key] > threshold
    else:
        below_threshold = data[key] <= threshold
        above_threshold = data[key] >= threshold

    # Check if there is any point where a value is below the threshold
    # followed by a value above the threshold
    crossed_upward = (
        below_threshold.shift(1, fill_value=False) & above_threshold
    ).any()
    return crossed_upward


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
            selected_rows, fast_key="SMA_Close_50", slow_key="SMA_Close_200"
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

    Params:
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
    # Check if the period is larger than the data
    if period > len(data):
        raise OperationalException(
            f"The period {period} is larger than the data."
        )

    sma_values = tp.sma(
        data[source_column_name].to_numpy(),
        period=period
    )

    # Pad NaN values for initial rows with a default value, e.g., 0
    sma_values = np.concatenate(
        (np.full(period - 1, None), sma_values)
    )

    if result_column_name:
        data[result_column_name] = sma_values
    else:
        # Assign SMA values to the DataFrame
        data[f"SMA_{source_column_name}_{period}"] = sma_values

    return data
