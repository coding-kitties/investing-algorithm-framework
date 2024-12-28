from pandas import DataFrame
import numpy as np


def is_crossover(
    data: DataFrame,
    first_column: str,
    second_column: str,
    strict=True,
    number_of_data_points=1
) -> bool:
    """
    Check if the given keys have crossed over.

    Parameters:
        data: DataFrame - The data to check.
        first_column: str - The first key.
        second_column: str - The second key.
        strict: bool - Whether to check for a strict crossover. Means that
          the first key has to be strictly greater than the second key.
        number_of_data_points: int - The number of data points to consider
          for the crossover. Default is 1. If 2 then 2 data points
          will be considered.
        which means that any first key has to be greater than the
          second key for the last 2 data points.

    Returns:
        bool - True if the first key has crossed over the second key.
    """

    if len(data) < 2:
        return False

    # Loop through the data points and check if the first key
    # is greater than the second key
    for i in range(number_of_data_points, 0, -1):

        if strict:
            if data[first_column].iloc[-(i + 1)] \
                    < data[second_column].iloc[-(i + 1)] \
                    and data[first_column].iloc[-i] \
                    > data[second_column].iloc[-i]:
                return True
        else:
            if data[first_column].iloc[-(i + 1)] \
                    <= data[second_column].iloc[-(i + 1)]  \
                    and data[first_column].iloc[-i] >= \
                    data[second_column].iloc[-i]:
                return True

    return False


def is_crossunder(
    data: DataFrame, first_column: str, second_column: str, strict=True
) -> bool:
    """
    Check if the given keys have crossed under.

    Parameters:
        data: pd.DataFrame - The input pandas DataFrame.
        key1: str - The first key to compare.
        key2: str - The second key to compare.
        strict: bool - Whether to check for a strict crossover.

    Returns:
        Boolean indicating if the keys have crossed under.
    """
    if len(data) < 2:
        return False

    if strict:
        return data[first_column].iloc[-1] < data[second_column].iloc[-1] \
            and data[first_column].iloc[-2] > data[second_column].iloc[-2]

    return data[first_column].iloc[-1] <= data[second_column].iloc[-1] \
        and data[first_column].iloc[-2] >= data[second_column].iloc[-2]


def is_above(data: DataFrame, first_column: str, second_column: str):
    """
    Check if the first key is above the second key.

    Parameters:
        data: DataFrame - The data to check.
        first_column: str - The first key.
        second_column: str - The second key.

    Returns:
        bool - True if the first key is above the second key.
    """
    return data[first_column].iloc[-1] > data[second_column].iloc[-1]


def is_below(data: DataFrame, first_column: str, second_column: str):
    """
    Check if the first key is below the second key.

    Parameters:
        data: DataFrame - The data to check.
        first_column: str - The first key.
        second_column: str - The second key.

    Returns:
        bool - True if the first key is below the second key.
    """
    return data[first_column].iloc[-1] < data[second_column].iloc[-1]


def has_crossed_upward(data: DataFrame, key, threshold, strict=True) -> bool:
    """
    Check if the given key has crossed upward for a given threshold.

    Parameters:
        data: pd.DataFrame - The input pandas DataFrame.
        key: str - The key to compare.
        threshold: float - The threshold value to compare.
        strict: bool - Whether to check for a strict crossover.

    Returns:
        Boolean indicating if the key has crossed upward
        through the threshold within the given data frame.
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


def has_crossed_downward(data: DataFrame, key, threshold, strict=True) -> bool:
    """
    Check if the given key has crossed downward for a given threshold.

    Parameters:
        data: pd.DataFrame - The input pandas DataFrame.
        key: str - The key to compare.
        threshold: float - The threshold value to compare.
        strict: bool - Whether to check for a strict crossover.

    Returns:
        Boolean indicating if the key has crossed downward
        through the threshold within the given data frame.
    """

    # Ensure the key exists in the DataFrame
    if key not in data.columns:
        raise KeyError(f"Key '{key}' not found in DataFrame")

    # Identify where the values are above and below the threshold
    if strict:
        above_threshold = data[key].shift(1) > threshold
        below_threshold = data[key] < threshold
    else:
        above_threshold = data[key] >= threshold
        below_threshold = data[key] <= threshold

    # Check if there is any point where a value is above the threshold
    # followed by a value below the threshold
    crossed_downward = (
        above_threshold.shift(1, fill_value=False) & below_threshold
    ).any()
    return crossed_downward


def has_any_lower_then_threshold(
    data: DataFrame, column, threshold, strict=True, number_of_data_points=1
) -> bool:
    """
    Check if the given column has reached the threshold with a given
    number of data points.

    Parameters:
        data: DataFrame - The data to check.
        column: str - The column to check.
        threshold: float - The threshold to check.
        strict: bool - Whether to check for a strict crossover downward.
        number_of_data_points: int - The number of data points to consider
            for the threshold. Default is 1.

    Returns:
        bool - True if the column has reached the threshold by having a
            value lower then the threshold.
    """
    if len(data) < number_of_data_points:
        return False

    selected_data = data[-number_of_data_points:]

    # Check if any of the values in the column are lower or
    # equal than the threshold
    if strict:
        return (selected_data[column] < threshold).any()

    return (selected_data[column] <= threshold).any()


def has_any_higher_then_threshold(
    data: DataFrame, column, threshold, strict=True, number_of_data_points=1
) -> bool:
    """
    Check if the given column has reached the threshold with a given
    number of data points.

    Parameters:
        data: DataFrame - The data to check.
        column: str - The column to check.
        threshold: float - The threshold to check.
        strict: bool - Whether to check for a strict crossover upward.
        number_of_data_points: int - The number of data points to consider
            for the threshold. Default is 1.

    Returns:
        bool - True if the column has reached the threshold by
          having a value higher then the threshold.
    """
    if len(data) < number_of_data_points:
        return False

    selected_data = data[-number_of_data_points:]

    # Check if any of the values in the column are
    # higher or equal than the threshold
    if strict:
        return (selected_data[column] > threshold).any()

    return (selected_data[column] >= threshold).any()


def get_slope(data: DataFrame, column, number_of_data_points=10) -> float:
    """
    Function to get the slope of the given column for
      the last n data points using linear regression.

    Parameters:
        data: DataFrame - The data to check.
        column: str - The column to check.
        number_of_data_points: int - The number of data points
            to consider for the slope. Default is 10.

    Returns:
        float - The slope of the given column for the last n data points.
    """

    if len(data) < number_of_data_points or number_of_data_points < 2:
        return 0.0

    index = -(number_of_data_points)

    # Select the first n data points from the column
    selected_data = data[column].iloc[index:].values

    # Create an array of x-values (0, 1, 2, ..., number_of_data_points-1)
    x_values = np.arange(number_of_data_points)

    # Use numpy's polyfit to get the slope of the best-fit
    # line (degree 1 for linear fit)
    slope, _ = np.polyfit(x_values, selected_data, 1)

    return slope


def has_slope_above_threshold(
    data: DataFrame,
    column: str,
    threshold,
    number_of_data_points=10,
    window_size=10
) -> bool:
    """
    Check if the slope of the given column is greater than the
      threshold for the last n data points. If the
    slope is not greater than the threshold for the last n
      data points, then the function will check the slope
    for the last n-1 data points and so on until
      we reach the window size.

    Parameters:
        data: DataFrame - The data to check.
        column: str - The column to check.
        threshold: float - The threshold to check.
        number_of_data_points: int - The number of data points
          to consider for the slope. Default is 10.
        window_size: int - The window size to consider
          for the slope. Default is 10.

    Returns:
        bool - True if the slope of the given column is greater
          than the threshold for the last n data points.
    """

    if len(data) < number_of_data_points:
        return False

    if number_of_data_points < window_size:
        raise ValueError(
            "The number of data points should be larger or equal" +
            " to the window size."
        )

    if window_size < number_of_data_points:
        difference = number_of_data_points - window_size
    else:
        slope = get_slope(data, column, number_of_data_points)
        return slope > threshold

    index = -(window_size)
    count = 0

    # Loop over sliding windows that shrink from the beginning
    while count <= difference:

        if count == 0:
            selected_window = data.iloc[index:]
        else:
            selected_window = data.iloc[index:-count]

        count += 1
        index -= 1

        # Calculate the slope of the window with the given number of points
        slope = get_slope(selected_window, column, window_size)

        if slope > threshold:
            return True

    return False


def has_slope_below_threshold(
    data: DataFrame,
    column: str,
    threshold,
    number_of_data_points=10,
    window_size=10
) -> bool:
    """
    Check if the slope of the given column is lower than the
      threshold for the last n data points. If the
    slope is not lower than the threshold for the
      last n data points, then the function will check the slope
    for the last n-1 data points and
      so on until we reach the window size.

    Parameters:
        data: DataFrame - The data to check.
        column: str - The column to check.
        threshold: float - The threshold to check.
        number_of_data_points: int - The number of data points
          to consider for the slope. Default is 10.
        window_size: int - The window size to consider
          for the slope. Default is 10.

    Returns:
        bool - True if the slope of the given column is
          lower than the threshold for the last n data points.
    """

    if len(data) < number_of_data_points:
        return False

    if number_of_data_points > window_size:
        raise ValueError(
            "The number of data points should be less than the window size."
        )

    if window_size > number_of_data_points:
        difference = window_size - number_of_data_points
    else:
        slope = get_slope(data, column, number_of_data_points)
        return slope < threshold

    index = -(number_of_data_points)
    count = 0

    # Loop over sliding windows that shrink from the beginning
    while count <= difference:

        if count == 0:
            selected_window = data.iloc[index:]
        else:
            selected_window = data.iloc[index:-count]

        count += 1
        index -= 1

        # Calculate the slope of the window with the given number of points
        slope = get_slope(selected_window, column, number_of_data_points)

        if slope < threshold:
            return True

    return False


def has_values_below_threshold(
    df,
    column,
    threshold,
    number_of_data_points,
    proportion=100,
    window_size=None,
    strict=True
) -> bool:
    """
    Detect if the last N data points in a column are below a certain threshold.

    Parameters:
    - df: pandas DataFrame
    - column: str, the column containing the values to analyze
    - threshold: float, the threshold for "low" values
    - number_of_data_points: int, the number of recent data points to analyze
    - proportion: float, the required proportion of values below the threshold
    - window_size: int, the number of data points to consider for the threshold
    - strict: bool, whether to check for a strict comparison

    Returns:
    - bool: True if the last N data points are below the threshold,
      False otherwise
    """
    if window_size is not None and window_size < number_of_data_points:
        difference = number_of_data_points - window_size
        count = 0
    else:
        difference = 1
        window_size = number_of_data_points

    count = 0
    index = -(window_size)
    proportion = proportion / 100

    # Loop over sliding windows that shrink from the beginning
    while count <= difference:

        if count == 0:
            selected_window = df[column].iloc[index:]
        else:
            selected_window = df[column].iloc[index:-count]

        count += 1
        index -= 1

        # Calculate the proportion of values below the threshold
        if strict:
            below_threshold = selected_window < threshold
        else:
            below_threshold = selected_window <= threshold

        proportion_below = below_threshold.mean()

        if proportion_below >= proportion:
            return True

    return False


def has_values_above_threshold(
    df,
    column,
    threshold,
    number_of_data_points,
    proportion=100,
    window_size=None,
    strict=True
) -> bool:
    """
    Detect if the last N data points in a column are above a certain threshold.

    Parameters:
    - df: pandas DataFrame
    - column: str, the column containing the values to analyze
    - threshold: float, the threshold for values
    - number_of_data_points: int, the number of recent data points to analyze
    - proportion: float, the required proportion of values below the threshold
    - window_size: int, the number of data points to consider for the threshold
    - strict: bool, whether to check for a strict comparison

    Returns:
    - bool: True if the last N data points are above the threshold,
      False otherwise
    """
    if window_size is not None and window_size < number_of_data_points:
        difference = number_of_data_points - window_size
        count = 0
    else:
        difference = 1
        window_size = number_of_data_points
        count = 1

    index = -(window_size)
    proportion = proportion / 100

    # Loop over sliding windows that shrink from the beginning
    while count <= difference:

        if count == 0:
            selected_window = df[column].iloc[index:]
        else:
            selected_window = df[column].iloc[index:-count]

        count += 1
        index -= 1

        # Calculate the proportion of values below the threshold
        if strict:
            above_threshold = selected_window > threshold
        else:
            above_threshold = selected_window >= threshold

        proportion_above = above_threshold.mean()

        if proportion_above >= proportion:
            return True

    return False


def get_values_above_threshold(
    df, column, threshold, number_of_data_points
) -> int:
    """
    Return a list of values above the threshold.

    Parameters:
    - df: pandas DataFrame
    - column: str, the column containing the values to analyze
    - threshold: float, the threshold for values
    - number_of_data_points: int, the number of recent data points to analyze
    - window_size: int, the number of

    Returns:
    - list: a list of values above the threshold
    """
    # Get the last `number_of_data_points` data points
    recent_data = df[column].iloc[-number_of_data_points:]

    # Filter for values above the threshold
    above_threshold = recent_data[recent_data > threshold]

    # Return the filtered values as a list
    return above_threshold.tolist()


def get_values_below_threshold(
    df, column, threshold, number_of_data_points
) -> int:
    """
    Return a list of values below the threshold.

    Parameters:
    - df: pandas DataFrame
    - column: str, the column containing the values to analyze
    - threshold: float, the threshold for values
    - number_of_data_points: int, the number of recent data points to analyze

    Returns:
    - list: a list of values below the threshold
    """
    # Get the last `number_of_data_points` data points
    recent_data = df[column].iloc[-number_of_data_points:]

    # Filter for values below the threshold
    below_threshold = recent_data[recent_data < threshold]

    # Return the filtered values as a list
    return below_threshold.tolist()
