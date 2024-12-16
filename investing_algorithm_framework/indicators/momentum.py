import numpy as np
from pandas import DataFrame
import tulipy as tp

from investing_algorithm_framework.domain import OperationalException


def get_willr(data: DataFrame, period=14, result_column="WILLR") -> DataFrame:
    """
    Calculate the Williams %R indicator for the given data.

    Parameters:
        data: DataFrame - The data to calculate the Williams %R for.
        period: int - The period to consider when calculating the Williams %R.
        result_column: str - The column to store the Williams %R values in.

    Returns:
        DataFrame - The data DataFrame with the Williams %R values calculated.
    """

    # Check if high, low, and close columns are present in the data
    if "High" not in data.columns or "Low" not in data.columns \
            or "Close" not in data.columns:
        raise OperationalException(
            "High, Low, and Close columns are required in the data"
        )

    # Calculate williams%R
    willr_values = tp.willr(
        data["High"].to_numpy(),
        data["Low"].to_numpy(),
        data["Close"].to_numpy(),
        period=period
    )

    # Pad NaN values for initial rows with a default value, e.g., 0
    willr_values = np.concatenate((np.full(period - 1, 0), willr_values))

    # Assign RSI values to the DataFrame
    data[result_column] = willr_values
    return data
