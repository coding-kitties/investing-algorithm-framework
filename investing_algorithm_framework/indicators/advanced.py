import importlib.util

if importlib.util.find_spec("scipy") is None \
        or importlib.util.find_spec("tulipy") is None \
        or importlib.util.find_spec("numpy") is None:
    raise ImportError("You have not installed the indicators package")

from scipy.signal import argrelextrema
from collections import deque
import numpy as np


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


def get_peaks(data, key, order=5, k=None):
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
