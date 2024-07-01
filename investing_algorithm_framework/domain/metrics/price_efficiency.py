import logging
from pandas import DataFrame, DatetimeIndex
from investing_algorithm_framework.domain.exceptions import \
    OperationalException

logger = logging.getLogger(__name__)


def get_price_efficiency_ratio(data: DataFrame):
    """
    Calculate the price efficiency ratio (noise) for each symbol.

    The price efficiency ratio is calculated as follows:

    1. Calculate the net price change over the period
    2. Calculate the sum of absolute daily price changes
    3. Calculate Efficiency Ratio = Net Price Change / Sum of Absolute
    Daily Price Changes

    The price efficiency ratio is a measure of the efficiency of the
    price movement over the period. A higher efficiency ratio indicates
    a more efficient price movement.

    Args:
        data (dict): A pandas DataFrame containing a column with either a
        'Close' or 'Price' label and a datetime index.

    returns:
        float: The price efficiency ratio
    """

    # Check if close value and index is a datetime object
    if 'Close' not in data.columns:
        raise OperationalException(
            "Close column not found in data, "
            "required for price efficiency ratio calculation"
        )

    if not isinstance(data.index, DatetimeIndex):
        raise OperationalException(
            "Index is not a datetime object,"
            "required for price efficiency ratio calculation"
        )

    # Calculate daily price changes
    data['Daily Change'] = data['Close'].diff()

    # Calculate net price change over the period
    net_price_change = abs(
        data['Close'].iloc[-1] - data['Close'].iloc[0])

    # Calculate the sum of absolute daily price changes
    sum_absolute_changes = data['Daily Change'] \
        .abs().sum()

    # Calculate Efficiency Ratio
    return net_price_change / sum_absolute_changes
