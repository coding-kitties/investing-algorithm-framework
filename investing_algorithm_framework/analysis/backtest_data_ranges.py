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
            name=f"window_{iteration}",
            train_range=train_backtest_date_range,
            test_range=test_backtest_date_range,
            warmup_days=warmup_days,
            gap_days=gap_days,
            step_days=step_days,
        ))

        current_start += pd.Timedelta(days=step_days)

    return windows


def generate_anchored_backtest_windows(
    start_date: datetime,
    end_date: datetime,
    initial_train_days: int = 365,
    test_days: int = 90,
    step_days: int = 90,
    gap_days: int = 0,
    warmup_days: int = 0,
) -> List[BacktestWindow]:
    """
    Generate anchored walk-forward windows.

    The training window is *anchored* at ``start_date`` and grows with each
    iteration — every window trains on all history from ``start_date`` up
    to just before the test range. This differs from rolling walk-forward,
    where the training window has a fixed size and slides forward.

    Args:
        start_date (datetime): Anchor date. Every window's training range
            starts here.
        end_date (datetime): The ending date for the last testing window.
        initial_train_days (int): Length of the first window's training
            range in days. Subsequent windows extend this by
            ``step_days`` per iteration.
        test_days (int): Number of days in each testing window.
        step_days (int): Number of days to step the training end (and,
            equivalently, the test start) forward for the next window.
        gap_days (int): Number of days to skip between the end of
            training and the start of testing. Default is 0.
        warmup_days (int): Number of days at the start of each training
            window reserved for warming up indicators. Must be less than
            ``initial_train_days``. Default is 0.

    Returns:
        List[BacktestWindow]: A list of BacktestWindow objects, each with
            an anchored training range and a sliding test range.

    Example:
        >>> windows = generate_anchored_backtest_windows(
        ...     start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
        ...     end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ...     initial_train_days=365,
        ...     test_days=90,
        ...     step_days=90,
        ...     gap_days=30,
        ...     warmup_days=26,
        ... )
    """
    if initial_train_days <= 0:
        raise ValueError("initial_train_days must be > 0")
    if test_days <= 0:
        raise ValueError("test_days must be > 0")
    if step_days <= 0:
        raise ValueError("step_days must be > 0")
    if gap_days < 0:
        raise ValueError("gap_days must be >= 0")

    windows = []
    max_iterations = 10000  # safety limit
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        # Anchor: train always starts at start_date, grows toward test.
        train_start = start_date
        train_end = start_date + pd.Timedelta(
            days=initial_train_days + (iteration - 1) * step_days
        )
        test_start = train_end + pd.Timedelta(days=gap_days)
        test_end = test_start + pd.Timedelta(days=test_days)

        if test_end > end_date:
            break

        train_backtest_date_range = BacktestDateRange(
            name=f"train_anchored_{iteration}",
            start_date=train_start,
            end_date=train_end,
        )
        test_backtest_date_range = BacktestDateRange(
            name=f"test_anchored_{iteration}",
            start_date=test_start,
            end_date=test_end,
        )
        windows.append(BacktestWindow(
            name=f"anchored_window_{iteration}",
            train_range=train_backtest_date_range,
            test_range=test_backtest_date_range,
            warmup_days=warmup_days,
            gap_days=gap_days,
            step_days=step_days,
        ))

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
            name=f"fold_{i}",
            train_range=train_backtest_date_range,
            test_range=test_backtest_date_range,
            warmup_days=warmup_days,
            gap_days=gap_days,
            fold_index=i,
        ))

    return windows
