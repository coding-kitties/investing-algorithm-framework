import pandas as pd
from logging import getLogger
from datetime import datetime
from typing import List

from investing_algorithm_framework.domain import BacktestDateRange, \
    BacktestWindow

logger = getLogger(__name__)


def generate_rolling_backtest_windows(
    start_date: datetime,
    end_date: datetime,
    train_days: int = 365,
    test_days: int = 90,
    step_days: int = 90,
    gap_days: int = 0,
    warmup_days: int = 0,
) -> List[BacktestWindow]:
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
        warmup_days (int): Number of days at the start of each training
            window reserved for warming up indicators. Must be less than
            train_days. Default is 0.

    Returns:
        List[BacktestWindow]: A list of BacktestWindow objects, each
            containing a train_range, test_range, gap_days, and
            warmup_days.

    Example:
        >>> windows = generate_rolling_backtest_windows(
        ...     start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
        ...     end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ...     train_days=365,
        ...     test_days=90,
        ...     step_days=90,
        ...     gap_days=30,
        ...     warmup_days=26,
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
        windows.append(BacktestWindow(
            train_range=train_backtest_date_range,
            test_range=test_backtest_date_range,
            warmup_days=warmup_days,
        ))

        current_start += pd.Timedelta(days=step_days)

    return windows


def generate_k_fold_backtest_windows(
    start_date: datetime,
    end_date: datetime,
    n_splits: int = 5,
    gap_days: int = 0,
    min_train_days: int = 0,
    warmup_days: int = 0,
) -> List[BacktestWindow]:
    """
    Generate time-series k-fold windows for walk-forward cross-validation.

    The total date range is divided into ``n_splits`` equal-sized test folds
    in strictly chronological order. For fold ``i``, the training window is
    an *expanding* window covering ``[start_date, test_fold_i.start - gap_days)``,
    so every day in the range appears in exactly one test fold and there is
    no look-ahead bias.

    This is especially useful for parameter selection and strategy ranking:
    pick parameter sets that perform consistently well across *all* k folds,
    not just a single rolling split.

    Args:
        start_date (datetime): Start of the overall date range.
        end_date (datetime): End of the overall date range.
        n_splits (int): Number of folds. Default is 5.
        gap_days (int): Days to skip between the end of training and the
            start of the test fold. Mirrors the same parameter in
            ``generate_rolling_backtest_windows``. Default is 0.
        min_train_days (int): Minimum number of effective training days
            required for a fold to be included. Early folds whose training
            history is shorter than this are silently skipped (e.g. set to
            200 if your strategy needs a 200-day SMA). Default is 0.
        warmup_days (int): Days at the start of each training window
            reserved for warming up indicators. Must be less than the
            effective training duration for any included fold. Default is 0.

    Returns:
        List[BacktestWindow]: One ``BacktestWindow`` per included fold, with
            ``fold_index`` set to the zero-based fold number.

    Example:
        >>> windows = generate_k_fold_backtest_windows(
        ...     start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
        ...     end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ...     n_splits=5,
        ...     gap_days=0,
        ...     min_train_days=200,
        ...     warmup_days=26,
        ... )
    """
    if n_splits < 2:
        raise ValueError("n_splits must be >= 2")

    total_days = (end_date - start_date).days
    fold_size = total_days // n_splits
    windows = []

    for i in range(n_splits):
        test_start = start_date + pd.Timedelta(days=i * fold_size)

        # Last fold absorbs any leftover days so the full range is covered.
        if i == n_splits - 1:
            test_end = end_date
        else:
            test_end = test_start + pd.Timedelta(days=fold_size)

        train_end = test_start - pd.Timedelta(days=gap_days)
        train_days = (train_end - start_date).days

        # Skip folds where there is no usable training history.
        if train_days < min_train_days or train_end <= start_date:
            continue

        train_backtest_date_range = BacktestDateRange(
            name=f"train_fold_{i}",
            start_date=start_date,
            end_date=train_end,
        )
        test_backtest_date_range = BacktestDateRange(
            name=f"test_fold_{i}",
            start_date=test_start,
            end_date=test_end,
        )
        windows.append(BacktestWindow(
            train_range=train_backtest_date_range,
            test_range=test_backtest_date_range,
            warmup_days=warmup_days,
            fold_index=i,
        ))

    return windows
