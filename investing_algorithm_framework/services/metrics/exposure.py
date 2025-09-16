"""
High exposure (>1) means you’re deploying capital aggressively, possibly with many simultaneous positions.

Exposure around 1 means capital is nearly fully invested most of the time, but not overlapping.

Low exposure (<1) means capital is mostly idle or only partially invested.
"""

from datetime import datetime, timedelta
from typing import List

from investing_algorithm_framework.domain import Trade


def get_exposure_ratio(
    trades: List["Trade"], start_date: datetime, end_date: datetime
) -> float:
    """
    Calculates the exposure ratio (time in market) as the fraction of the total
    backtest duration where at least one position was open.

    Unlike cumulative exposure, overlapping trades are not double-counted.
    The result is always between 0 and 1.

    Args:
        trades (List[Trade]): List of trades executed during the backtest.
        start_date (datetime): The start date of the backtest.
        end_date (datetime): The end date of the backtest.

    Returns:
        A float between 0 and 1 representing the exposure ratio.
    """
    if not trades:
        return 0.0

    # Collect trade intervals
    intervals = []
    for trade in trades:
        entry = max(trade.opened_at, start_date)
        exit = min(trade.closed_at or end_date, end_date)
        if exit > entry:
            intervals.append((entry, exit))

    if not intervals:
        return 0.0

    # Sort intervals by start time
    intervals.sort(key=lambda x: x[0])

    # Merge overlapping intervals
    merged = []
    current_start, current_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= current_end:  # overlap
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    merged.append((current_start, current_end))

    # Total time with at least one open trade
    total_exposed_time = sum((end - start for start, end in merged), timedelta(0))

    backtest_duration = end_date - start_date
    if backtest_duration.total_seconds() == 0:
        return 0.0

    return total_exposed_time.total_seconds() \
        / backtest_duration.total_seconds()


def get_cumulative_exposure(
    trades: List[Trade], start_date: datetime, end_date: datetime
) -> float:
    """
    Calculates the exposure time as a fraction of the total backtest duration
    that the strategy had capital deployed (i.e., at least one open position).

    This value can be greater than 1 if the strategy had overlapping trades.
    For example, if the strategy had two trades open at the same time,
    the exposure factor would be 2.0, indicating that capital was deployed
    for twice the duration of the backtest period.

    Args:
        trades (List[Trade]): List of trades executed during the backtest.
        start_date (datetime): The start date.
        end_date (datetime): The end date.

    Returns:
        A float representing the exposure factor, which is the fraction of time
        the strategy had capital deployed during the backtest period.

    """
    if not trades:
        return 0.0

    total_trade_duration = timedelta(0)
    for trade in trades:
        entry = trade.opened_at
        exit = trade.closed_at or end_date  # open trades counted up to end

        if exit > entry:
            total_trade_duration += exit - entry

    backtest_duration = end_date - start_date

    if backtest_duration.total_seconds() == 0:
        return 0.0

    return (total_trade_duration.total_seconds()
            / backtest_duration.total_seconds())


def get_average_trade_duration(trades: List[Trade]):
    """
    Calculates the average duration of trades in the backtest report.

    Args:
        trades (List[Trade]): List of trades executed during the backtest.

    Returns:
        A float representing the average trade duration in hours.
    """
    if not trades:
        return 0.0

    total_duration = 0

    for trade in trades:
        trade_duration = trade.duration

        if trade_duration is not None:
            total_duration += trade_duration

    average_trade_duration = total_duration / len(trades)
    return average_trade_duration


def get_trade_frequency(
    trades: List[Trade], start_date: datetime, end_date: datetime
) -> float:
    """
    Calculates the trade frequency as the number of trades per day
    during the backtest period.

    Args:
        trades (List[Trade]): List of trades executed during the backtest.
        start_date (datetime): The start date of the backtest.
        end_date (datetime): The end date of the backtest.

    Returns:
        A float representing the average number of trades per day.
    """

    if not trades:
        return 0.0

    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return 0.0

    return len(trades) / total_days


def get_trades_per_day(
    trades: List[Trade], start_date: datetime, end_date: datetime
) -> float:
    """
    Calculates the average number of trades per day during the backtest period.

    Args:
        trades (List[Trade]): List of trades executed during the backtest.
        start_date (datetime): The start date of the backtest.
        end_date (datetime): The end date of the backtest.

    Returns:
        A float representing the average number of trades per day.
    """
    if not trades:
        return 0.0

    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return 0.0

    return len(trades) / total_days


def get_trades_per_year(
    trades: List[Trade], start_date: datetime, end_date: datetime
) -> float:
    """
    Calculates the average number of trades per year during the backtest period.

    Args:
        trades (List[Trade]): List of trades executed during the backtest.
        start_date (datetime): The start date of the backtest.
        end_date (datetime): The end date of the backtest.

    Returns:
        A float representing the average number of trades per year.
    """
    if not trades:
        return 0.0

    total_years = (end_date - start_date).days / 365.25
    if total_years <= 0:
        return 0.0

    return len(trades) / total_years
