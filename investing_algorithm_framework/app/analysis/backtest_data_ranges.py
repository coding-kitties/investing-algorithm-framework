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
    data: pd.DataFrame,
    window_type: str = "rolling",  # or "expanding"
    start_date: datetime = None,
    end_date: datetime = None,
    train_days: int = 365,
    test_days: int = 90,
    step_days: int = 90,
    gap_days: int = 0,
    min_data_threshold: float = 0.8
) -> List[Dict[str, any]]:
    """
    Generate rolling or expanding windows for walk-forward backtesting.

    This function creates training and testing windows for
    time-series backtesting,
    avoiding look-ahead bias and providing realistic out-of-sample
    performance estimates.

    Args:
        window_type (str): Type of window to generate:
            - "rolling": Fixed train_days
            window (tests with consistent history)
            - "expanding": Growing train window (uses all data from start_date)
        start_date (datetime, optional): The starting date for the first
            training window. Defaults to the earliest date in the data.
        end_date (datetime, optional): The ending date for the last
            testing window. Defaults to the latest date in the data.
        train_days (int): Number of days in the training window.
        test_days (int): Number of days in the testing window.
        step_days (int): Number of days to step forward for the next window.
        gap_days (int): Number of days to skip between train and test windows.
            Useful to avoid look-ahead bias in indicators
            with lag (e.g., 26 for MACD). Default is 0 (no gap).
        min_data_threshold (float): Minimum fraction of expected data required.
            Windows with less data than (train_days * threshold)
            or (test_days * threshold) will be skipped. Default is 0.8 (80%).

    Returns:
        List[Dict[str, any]]: A list of dictionaries containing:
            - "train_range": BacktestDateRange for training period
            - "test_range": BacktestDateRange for testing period
            - "train_data": DataFrame for training period
            - "test_data": DataFrame for testing period
            - "metadata": Dictionary with window statistics

    Example:
        >>> windows = generate_rolling_backtest_windows(
        ...     data=btc_data,
        ...     start_date=datetime(2021, 1, 1),
        ...     end_date=datetime(2024, 12, 31),
        ...     train_days=365,
        ...     test_days=90,
        ...     step_days=90,
        ...     window_type="expanding",
        ...     gap_days=30
        ... )
    """
    if start_date is None:
        start_date = data.index.min()
    if end_date is None:
        end_date = data.index.max()

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

        if window_type == "expanding":
            # Train on ALL data from start_date to train_end (growing window)
            train_data = data[(data.index >= start_date)
                              & (data.index < train_end)]
        else:
            # Current implementation (fixed window)
            train_data = data[(data.index >= train_start)
                              & (data.index < train_end)]

        test_data = data[(data.index >= test_start) & (data.index < test_end)]

        # Validate minimum data threshold
        min_train_records = int(train_days * min_data_threshold)
        min_test_records = int(test_days * min_data_threshold)

        if len(train_data) < min_train_records:
            logger.warning(
                f"Skipping window starting {train_start.date()}: "
                f"train data ({len(train_data)} records) "
                f"below threshold ({min_train_records})"
            )
            current_start += pd.Timedelta(days=step_days)
            continue

        if len(test_data) < min_test_records:
            logger.warning(
                f"Skipping window starting {train_start.date()}: "
                f"test data ({len(test_data)} records) "
                f"below threshold ({min_test_records})"
            )
            current_start += pd.Timedelta(days=step_days)
            continue

        # Calculate metadata
        train_actual_start = train_data.index.min() \
            if len(train_data) > 0 else train_start
        train_actual_end = train_data.index.max() \
            if len(train_data) > 0 else train_end
        test_actual_start = test_data.index.min() \
            if len(test_data) > 0 else test_start
        test_actual_end = test_data.index.max() \
            if len(test_data) > 0 else test_end

        metadata = {
            "train_days_actual": len(train_data),
            "test_days_actual": len(test_data),
            "train_days_expected": train_days,
            "test_days_expected": test_days,
            "gap_days": gap_days,
            "train_actual_start": train_actual_start,
            "train_actual_end": train_actual_end,
            "test_actual_start": test_actual_start,
            "test_actual_end": test_actual_end,
            "window_type": window_type
        }

        # Calculate returns if close price exists
        if 'close' in train_data.columns and len(train_data) > 1:
            metadata["train_return"] = (train_data['close'].iloc[-1]
                                        / train_data['close'].iloc[0]) - 1
        else:
            metadata["train_return"] = None

        if 'close' in test_data.columns and len(test_data) > 1:
            metadata["test_return"] = (test_data['close'].iloc[-1]
                                       / test_data['close'].iloc[0]) - 1
        else:
            metadata["test_return"] = None

        train_backtest_date_range = BacktestDateRange(
            name=f"train_range_{iteration}",
            start_date=train_start,
            end_date=train_end
        )
        test_backtest_date_range = BacktestDateRange(
            name=f"test_range_{iteration}",
            start_date=test_start,
            end_date=test_end
        )
        windows.append({
            "train_range": train_backtest_date_range,
            "test_range": test_backtest_date_range,
            "metadata": metadata
        })

        current_start += pd.Timedelta(days=step_days)

    return windows
