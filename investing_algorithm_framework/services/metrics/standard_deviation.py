import numpy as np
import pandas as pd

from ._returns_helper import daily_twr_returns


def _twr_period_returns(snapshots) -> pd.Series:
    """Per-snapshot TWR returns (subtracting per-snapshot cash_flow).

    Used by metrics that operate on the raw snapshot series rather than
    a daily resample.
    """
    data = [
        (s.created_at, s.total_value, getattr(s, "cash_flow", 0) or 0)
        for s in snapshots
    ]
    df = pd.DataFrame(
        data, columns=["created_at", "total_value", "cash_flow"]
    )
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')
    prev_v = df['total_value'].shift(1)
    return ((df['total_value'] - df['cash_flow']) / prev_v - 1).dropna()


def get_standard_deviation_downside_returns(snapshots):
    """
    Calculate the downside deviation of returns: the root-mean-square
    shortfall below the target, averaged over every period.

    Args:
        report (BacktestReport): The report containing the equity curve.

    Returns:
        float: The downside deviation of returns.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    df_returns = _twr_period_returns(snapshots)

    if df_returns.empty:
        return 0.0

    # Same definition as get_downside_std_of_daily_returns: the root-mean-square
    # shortfall below the target over EVERY period. See the note there for why the
    # dispersion among the losing periods is the wrong quantity.
    shortfall = df_returns.clip(upper=0.0)
    downside_std = float(np.sqrt((shortfall ** 2).mean()))

    if np.isnan(downside_std):
        return 0.0

    return downside_std


def get_standard_deviation_returns(snapshots):
    """
    Calculate the standard deviation of returns from the net size
    of the reports.

    Args:
        report (BacktestReport): The report containing the equity curve.

    Returns:
        float: The downside deviation of returns.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    df_returns = _twr_period_returns(snapshots)

    if df_returns.empty:
        return 0.0

    if len(df_returns) < 2:
        return 0.0

    std = df_returns.std(ddof=1)  # ddof=1 for sample std dev

    # Handle edge cases
    if np.isnan(std):
        return 0.0

    return std

def get_daily_returns_std(snapshots):
    """
    Calculate the standard deviation of daily returns from a list of snapshots.
    Resamples data to daily frequency using end-of-day values.

    Args:
        snapshots (List[PortfolioSnapshot]): Snapshots with total_value and created_at.

    Returns:
        float: Standard deviation of daily returns.
    """
    if len(snapshots) < 2:
        return 0.0  # Not enough data

    returns = daily_twr_returns(snapshots)

    if returns.empty or len(returns) < 2:
        return 0.0

    return returns.std()


def get_downside_std_of_daily_returns(snapshots):
    """
    Calculate the downside deviation of daily returns from a list of snapshots.
    Resamples data to daily frequency using end-of-day values.

    Downside deviation is the root-mean-square shortfall below the target over
    every period, not the standard deviation of the losing periods alone.

    Args:
        snapshots (List[PortfolioSnapshot]): Snapshots with total_value and created_at.

    Returns:
        float: Downside deviation of daily returns.
    """
    if len(snapshots) < 2:
        return 0.0  # Not enough data

    returns = daily_twr_returns(snapshots)

    if returns.empty:
        return 0.0

    # Downside deviation is the root-mean-square SHORTFALL below the target,
    # averaged over EVERY period -- not the dispersion among the losing days.
    #
    # Taking negative_returns.std() divides by the number of losing days and
    # measures spread around the mean loss, so a strategy whose losses are all
    # a similar size drives the denominator toward zero and the Sortino ratio
    # toward infinity. Losses of a consistent size are the mark of a
    # risk-controlled strategy, so the previous form rewarded most exactly what
    # the ratio exists to penalise.
    shortfall = returns.clip(upper=0.0)
    return float(np.sqrt((shortfall ** 2).mean()))
