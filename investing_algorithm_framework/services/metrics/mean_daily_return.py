import pandas as pd
import numpy as np

from .cagr import get_cagr


def get_mean_daily_return(snapshots):
    """
    Calculate the mean daily return from the total value of the snapshots.

    This function computes the mean daily return based on the list of
    snapshots in the report. If the snapshots have a granularity of less
    than a day, the function will resample to daily frequency and compute
    average daily returns.

    If there is less data then for a year, it will use cagr to
    calculate the mean daily return.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots

    Returns:
        float: The mean daily return.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    # Create DataFrame from snapshots
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')

    start_date = df.iloc[0].name
    end_date = df.iloc[-1].name

    # Check if the period is less than a year
    if (end_date - start_date).days < 365:
        # Use CAGR to calculate mean daily return
        cagr = get_cagr(snapshots)
        if cagr == 0.0:
            return 0.0

        return (1 + cagr) ** (1 / 365) - 1

    # Resample to daily frequency using last value of the day
    daily_df = df.resample('1D').last().dropna()

    # Calculate daily returns
    daily_df['return'] = daily_df['total_value'].pct_change()
    daily_df = daily_df.dropna()

    if daily_df.empty:
        return 0.0

    mean_return = daily_df['return'].mean()

    if np.isnan(mean_return):
        return 0.0

    return mean_return


def get_mean_yearly_return(report, periods_per_year=365):
    """
    Calculate the mean yearly return from a backtest report by
    annualizing the mean daily return.

    Args:
        report (BacktestReport): The report containing the snapshots.
        periods_per_year (int): Number of periods in a year (e.g., 365 for daily data).

    Returns:
        float: The mean yearly return (annualized).
    """
    mean_daily_return = get_mean_daily_return(report)

    if mean_daily_return == 0.0:
        return 0.0

    return (1 + mean_daily_return) ** periods_per_year - 1

