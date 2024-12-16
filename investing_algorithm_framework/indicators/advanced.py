from scipy.signal import argrelextrema
from collections import deque
import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import OperationalException


def get_higher_lows(data: np.array, order=5, K=2):
    '''
    Finds consecutive higher lows in price pattern.
    Must not be exceeded within the number of periods indicated by
    the width parameter for the value to be confirmed.
    K determines how many consecutive lows need to be higher.
    '''
    # Get lows
    low_idx = argrelextrema(data, np.less, order=order)[0]
    lows = data[low_idx]

    # Ensure consecutive lows are higher than previous lows
    extrema = []
    ex_deque = deque(maxlen=K)

    for i, idx in enumerate(low_idx):
        if i == 0:
            ex_deque.append(idx)
            continue
        if lows[i] < lows[i - 1]:
            ex_deque.clear()

        ex_deque.append(idx)

        if len(ex_deque) == K:
            extrema.append(ex_deque.copy())

    return extrema


def get_lower_highs(data: np.array, order=5, K=2):
    '''
    Finds consecutive lower highs in price pattern.
    Must not be exceeded within the number of periods
    indicated by the width
    parameter for the value to be confirmed.
    K determines how many consecutive highs need to be lower.

    Parameters:
        order (optional): int -  How many points on each
            side to use for the comparison to
            consider ``comparator(n, n+x)`` to be True.
        K (optional): int -  How many consecutive highs need
            to be lower. This means that for a given high,
            the next K highs must be lower than the k highs
            before. So say K=2, then the high at index i must
            be lower than the high at index i-2 and i-1. If this
            condition is met, then the high at index i is considered a
            lower high. If the condition is not met, then the high at
            index i is not considered a lower high.

    Returns:
        extrema: list - A list of lists containing the indices of the
            consecutive lower highs in the data array.
    '''
    # Get highs
    high_idx = argrelextrema(data, np.greater, order=order)[0]
    highs = data[high_idx]

    # Ensure consecutive highs are lower than previous highs
    extrema = []
    ex_deque = deque(maxlen=K)

    for i, idx in enumerate(high_idx):

        if i == 0:
            ex_deque.append(idx)
            continue
        if highs[i] > highs[i - 1]:
            ex_deque.clear()

        ex_deque.append(idx)

        if len(ex_deque) == K:
            extrema.append(ex_deque.copy())

    return extrema


def get_higher_highs(data: np.array, order=5, K=None):
    '''
    Finds consecutive higher highs in price pattern.
    Must not be exceeded within the number of periods indicated
    by the width
    parameter for the value to be confirmed.
    K determines how many consecutive highs need to be higher.
    '''
    # Get highs
    high_idx = argrelextrema(data, np.greater_equal, order=order)[0]
    highs = data[high_idx]

    # Ensure consecutive highs are higher than previous highs
    extrema = []
    ex_deque = deque(maxlen=K)

    for i, idx in enumerate(high_idx):

        if i == 0:
            ex_deque.append(idx)
            continue
        if highs[i] < highs[i - 1]:
            ex_deque.clear()

        ex_deque.append(idx)

        if len(ex_deque) == K:
            extrema.append(ex_deque.copy())

    idx = np.array([i[-1] + order for i in extrema])
    idx = idx[np.where(idx < len(data))]
    return idx


def get_lower_lows(data: np.array, order=5, K=2):
    '''
    Finds consecutive lower lows in price pattern.
    Must not be exceeded within the number of periods indicated by the width
    parameter for the value to be confirmed.

    Parameters:

        order (optional): int -  How many points on each
            side to use for the comparison to
            consider ``comparator(n, n+x)`` to be True.
        K (optional): int -  How many consecutive lows need
            to be lower. This means that for a given low,
            the next K lows must be lower than the k lows
            before. So say K=2, then the low at index i must
            be lower than the low at index i-2 and i-1. If this
            condition is met, then the low at index i is considered a
            lower low. If the condition is not met, then the low at
            index i is not considered a lower low.

    Returns:
        extrema: list - A list of lists containing the indices of the
            consecutive lower lows in the data array.
    '''
    # Get lows
    low_idx = argrelextrema(data, np.less, order=order)[0]
    lows = data[low_idx]

    # Ensure consecutive lows are lower than previous lows
    extrema = []
    ex_deque = deque(maxlen=K)

    for i, idx in enumerate(low_idx):

        if i == 0:
            ex_deque.append(idx)
            continue

        if lows[i] > lows[i - 1]:
            ex_deque.clear()

        ex_deque.append(idx)

        if len(ex_deque) == K:
            extrema.append(ex_deque.copy())

    return extrema


def get_higher_high_index(data: np.array, order=5, K=2):
    # extrema = get_higher_highs(data, order, K)
    # idx = np.array([i[-1] + order for i in extrema])
    # return idx[np.where(idx < len(data))]
    return get_higher_highs(data, order, K)


def get_lower_highs_index(data: np.array, order=5, K=2):
    extrema = get_lower_highs(data, order, K)
    idx = np.array([i[-1] + order for i in extrema])
    return idx[np.where(idx < len(data))]


def get_lower_lows_index(data: np.array, order=5, K=2):
    extrema = get_lower_lows(data, order, K)
    idx = np.array([i[-1] + order for i in extrema])
    return idx[np.where(idx < len(data))]


def get_higher_lows_index(data: np.array, order=5, K=2):
    extrema = get_higher_lows(data, order, K)
    idx = np.array([i[-1] + order for i in extrema])
    return idx[np.where(idx < len(data))]


def get_peaks(data: pd.DataFrame, key, order=5, k=None):
    """
    Get peaks in for the given key in the data DataFrame.
    Peaks are calculated using the get_higher_high_index,
    get_lower_highs_index, get_lower_lows_index, and get_higher_lows_index
    functions with the given order and K parameters.

    The order parameter determines the number of periods to
    consider when calculating the peaks. If the order is 2, the
    function will consider
    the current and previous periods to determine the peaks.
    if the order is 3, the function will consider the current and
    two previous periods to determine the peaks.
    A period is a datapoint in the data DataFrame.

    The K parameter determines how many consecutive peaks need to be
    higher or lower to be considered a peak.

    Parameters:
        data: DataFrame - The data to calculate the peaks for.
        column: str - The column to calculate the peaks for.
        order: int - The number of periods (data points) to consider
          when calculating the peaks.
        K: int - The number of consecutive peaks that need to be
          higher or lower in order to be classified as a peak.

    Returns:
        DataFrame - The data DataFrame with the peaks calculated
          for the given key.
    """
    vals = data[key].values
    hh_idx = get_higher_high_index(vals, order, K=k)
    lh_idx = get_lower_highs_index(vals, order, K=k)
    ll_idx = get_lower_lows_index(vals, order, K=k)
    hl_idx = get_higher_lows_index(vals, order, K=k)

    # Create columns for highs and lows
    data[f'{key}_highs'] = np.nan
    data[f'{key}_lows'] = np.nan

    # Get the datetime values corresponding to these integer positions
    data[f'{key}_highs'] = data[f'{key}_highs'].ffill().fillna(0)
    data[f'{key}_lows'] = data[f'{key}_lows'].ffill().fillna(0)

    if len(hh_idx) != 0:
        hh_datetime_values = data.index[hh_idx]
        data.loc[hh_datetime_values, f'{key}_highs'] = 1

    if len(lh_idx) != 0:
        lh_datetime_values = data.index[lh_idx]
        data.loc[lh_datetime_values, f'{key}_highs'] = -1

    if len(ll_idx) != 0:
        ll_datetime_values = data.index[ll_idx]
        data.loc[ll_datetime_values, f'{key}_lows'] = 1

    if len(hl_idx) != 0:
        hl_datetime_values = data.index[hl_idx]
        data.loc[hl_datetime_values, f'{key}_lows'] = -1

    return data


def is_divergence(
    data: pd.DataFrame,
    column_one: str,
    column_two: str,
    window_size=1,
    number_of_data_points=1
) -> bool:
    """
    Given two columns in a DataFrame with peaks and lows, check if
      there is a divergence.
    Peaks and lows are calculated using the get_peaks function
      and look as follows: [-1, 0] or [1, 0] or [0, -1, 0] or [0, 1, 0].

    For a bullish divergence:
        * Indicator (First Column): Look for higher
          lows (-1) in a technical indicator, such as RSI, MACD, or
            another momentum oscillator.
        * Price Action (Second Column): Identify lower lows (1)
          in the price of the asset. This indicates that the price
            is trending downwards.

    For a bearish divergence:
        * Indicator (First Column): Look for lower highs (-1) in
          a technical indicator, such as RSI, MACD, or
            another momentum oscillator.
        * Price Action (Second Column): Identify higher highs (1)
          in the price of the asset. This indicates that the
            price is trending upwards.

    A divergence occurs when the value of column_one makes
      a higher high or lower low and the
    value of column_two makes a lower high or higher low.
    This is represented by the following sequences:
      [-1, 0] or [1, 0] or [0, -1, 0] or [0, 1, 0].
    This indicates that column_one may be gaining momentum
      and could be due for a reversal.

    Parameters:
        data: DataFrame - The data to check for bullish divergence.
        column_one: str - The column to check for higher low.
        column_two: str - The column to check for lower low.
        window_size: int - The windows size represent the
          total search space when checking for divergence. For example,
          if the window_size is 1, the function will consider only the
          current two data points, e.g. this will be true [1] and [-1]
          and false [0] and [-1]. If the window_size is 2,
            the function will consider the current and previous data point,
            e.g. this will be true [1, 0] and [0, -1]
            and false [0, 0] and [0, -1].
        number_of_data_points: int - The number of data points
            to consider when using a sliding windows size when checking for
          divergence. For example, if the number_of_data_points
          is 1, the function will consider only the current two data points.
          If the number_of_data_points is 4 and the window size is 2,
          the function will consider the current and previous 3 data
          points when checking for divergence. Then the function will
          slide the window by 1 and check the next 2 data points until
          the end of the data.

    Returns:
        Boolean - True if there is a bullish divergence, False otherwise.
    """

    # Check if the two columns are in the data
    if column_one not in data.columns or column_two not in data.columns:
        raise OperationalException(
            f"{column_one} and {column_two} columns are required in the data"
        )

    if window_size < 1:
        raise OperationalException("Window size must be greater than 0")

    if len(data) < window_size:
        raise OperationalException(
            f"Data must have at least {window_size} data points." +
            f"It currently has {len(data)} data points"
        )

    # Limit the DataFrame to the last `number_of_data_points` rows
    last_x_rows = data.tail(number_of_data_points)

    # Extract the column values as lists
    column_one_highs = last_x_rows[column_one].tolist()
    column_two_highs = last_x_rows[column_two].tolist()

    # Iterate through the rows up to the specified number_of_data_points
    # Reverse iterate through the rows up to the specified
    # number_of_data_points

    for i, value in reversed(list(enumerate(column_one_highs))):

        if value == 0 or value == 1:
            continue

        if value == -1:

            # Select up to the window_size number of rows of the second column
            selected_window_column_two = column_two_highs[i:i + window_size]

            for _, valueSecond in reversed(
                list(enumerate(selected_window_column_two))
            ):

                if valueSecond == 0:
                    continue

                # Check if the sequence (-1, 1) occurs within the window
                if valueSecond == 1:
                    return True

                if valueSecond == -1:
                    valueSecond

    return False


def is_lower_low_detected(
        data: pd.DataFrame, column: str, number_of_data_points=1
) -> bool:
    """
    Function to check if a lower low is detected in the data. A lower
    low is detected if the value of the column is -1 thar represents a peak.

    IMPORTANT: The data must have the column with the peaks
    calculated using the get_peaks function. The get_peaks
    function calculates the peaks in the data and assigns the value
    of -1 to the column. You can find the get_peaks function in the
    indicators module.

    Parameters:
        data: DataFrame - The data to check for lower low.
        column: str - The column to check for lower low.
        number_of_data_points: int - The number of data points
        to consider when checking for lower low.

    Returns:
        Boolean - True if a lower low is detected, False otherwise.
    """

    selected_column = data[column].tail(number_of_data_points).tolist()

    for item in selected_column:
        if item == -1:
            return True

    return False
