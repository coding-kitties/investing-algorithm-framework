import pandas as pd
from logging import getLogger
from datetime import datetime
from typing import List, Dict, Union
from datetime import timezone

from investing_algorithm_framework.domain import BacktestDateRange, \
    OperationalException

logger = getLogger(__name__)


def select_backtest_date_ranges(
    df: pd.DataFrame, window: Union[str, int] = '365D'
) -> List[BacktestDateRange]:
    """
    Identifies the best upturn, worst downturn, and sideways periods
    for the given window duration. This allows you to quickly select
    interesting periods for backtesting.

    Args:
        df (pd.DataFrame): DataFrame with a DateTime index
            and 'Close' column.
        window (Union[str, int]): Duration of the window
            to analyze. Can be a string like '365D' or an
            integer representing days.

    Returns:
        List[BacktestDateRange]: List of BacktestDateRange
            objects representing the best upturn, worst
            downturn, and most sideways periods.
    """
    df = df.copy()
    df = df.sort_index()

    if isinstance(window, int):
        window = pd.Timedelta(days=window)
    elif isinstance(window, str):
        window = pd.to_timedelta(window)
    else:
        raise OperationalException("window must be a string or integer")

    # Check if the window is larger than the DataFrame
    if len(df) == 0:
        raise OperationalException("DataFrame is empty")

    if df.index[-1] - df.index[0] < window:
        raise OperationalException(
            "Window duration is larger than the data duration"
        )

    if len(df) < 2 or df.index[-1] - df.index[0] < window:
        raise OperationalException(
            "DataFrame must contain at least two rows and span "
            "the full window duration"
        )

    best_upturn = {
        "name": "UpTurn", "return": float('-inf'), "start": None, "end": None
    }
    worst_downturn = {
        "name": "DownTurn", "return": float('inf'), "start": None, "end": None
    }
    most_sideways = {
        "name": "SideWays",
        "volatility": float('inf'),
        "return": None,
        "start": None,
        "end": None
    }

    for i in range(len(df)):
        start_time = df.index[i]
        end_time = start_time + window
        window_df = df[(df.index >= start_time) & (df.index <= end_time)]

        if len(window_df) < 2 or (window_df.index[-1] - start_time) < window:
            continue

        start_price = window_df['Close'].iloc[0]
        end_price = window_df['Close'].iloc[-1]
        ret = (end_price / start_price) - 1  # relative return
        volatility = window_df['Close'].std()

        # Ensure datetime for BacktestDateRange and with timezone utc
        start_time = pd.Timestamp(start_time).to_pydatetime()
        start_time = start_time.replace(tzinfo=timezone.utc)
        end_time = pd.Timestamp(window_df.index[-1]).to_pydatetime()
        end_time = end_time.replace(tzinfo=timezone.utc)

        if ret > best_upturn["return"]:
            best_upturn.update(
                {"return": ret, "start": start_time, "end": end_time}
            )

        if ret < worst_downturn["return"]:
            worst_downturn.update(
                {"return": ret, "start": start_time, "end": end_time}
            )

        if volatility < most_sideways["volatility"]:
            most_sideways.update({
                "return": ret,
                "volatility": volatility,
                "start": start_time,
                "end": end_time
            })

    return [
        BacktestDateRange(
            start_date=best_upturn['start'],
            end_date=best_upturn['end'],
            name=best_upturn['name']
        ),
        BacktestDateRange(
            start_date=worst_downturn['start'],
            end_date=worst_downturn['end'],
            name=worst_downturn['name']
        ),
        BacktestDateRange(
            start_date=most_sideways['start'],
            end_date=most_sideways['end'],
            name=most_sideways['name']
        )
    ]


def generate_rolling_backtest_windows(
    start_date: datetime,
    end_date: datetime,
    train_days: int = 365,
    test_days: int = 90,
    step_days: int = 90,
    gap_days: int = 0,
) -> List[Dict[str, BacktestDateRange]]:
    """
    Generate rolling windows for walk-forward backtesting.

    This function creates training and testing date ranges for
    time-series backtesting, avoiding look-ahead bias and providing
    realistic out-of-sample performance estimates.

    Args:
        start_date (datetime): The starting date for the first
            training window.
        end_date (datetime): The ending date for the last
            testing window.
        train_days (int): Number of days in the training window.
        test_days (int): Number of days in the testing window.
        step_days (int): Number of days to step forward for the next window.
        gap_days (int): Number of days to skip between train and test windows.
            Useful to avoid look-ahead bias in indicators
            with lag (e.g., 26 for MACD). Default is 0 (no gap).

    Returns:
        List[Dict[str, BacktestDateRange]]: A list of dictionaries containing:
            - "train_range": BacktestDateRange for training period
            - "test_range": BacktestDateRange for testing period

    Example:
        >>> windows = generate_rolling_backtest_windows(
        ...     start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
        ...     end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ...     train_days=365,
        ...     test_days=90,
        ...     step_days=90,
        ...     gap_days=30
        ... )
    """
    windows = []
    current_start = start_date
    max_iterations = 10000  # Safety limit to prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        train_start = current_start
        train_end = train_start + pd.Timedelta(days=train_days)
        test_start = train_end + pd.Timedelta(days=gap_days)
        test_end = test_start + pd.Timedelta(days=test_days)

        if test_end > end_date:
            break

        train_backtest_date_range = BacktestDateRange(
            name=f"train_window_{iteration}",
            start_date=train_start,
            end_date=train_end
        )
        test_backtest_date_range = BacktestDateRange(
            name=f"test_window_{iteration}",
            start_date=test_start,
            end_date=test_end
        )
        windows.append({
            "train_range": train_backtest_date_range,
            "test_range": test_backtest_date_range,
        })

        current_start += pd.Timedelta(days=step_days)

    return windows
