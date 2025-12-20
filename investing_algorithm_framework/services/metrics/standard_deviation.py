import numpy as np
import pandas as pd


def get_standard_deviation_downside_returns(snapshots):
    """
    Calculate the standard deviation of downside returns from the net size
    of the reports.

    Args:
        report (BacktestReport): The report containing the equity curve.

    Returns:
        float: The standard deviation of downside returns.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    # Create DataFrame of net_size over time
    data = [(s.total_value, s.created_at) for s in snapshots]
    df = pd.DataFrame(data, columns=["total_value", "created_at"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at').copy()

    # Compute percentage returns
    df['return'] = df['total_value'].pct_change()
    df = df.dropna()

    if df.empty:
        return 0.0

    # Filter downside returns
    downside_returns = df['return'][df['return'] < 0]

    if downside_returns.empty:
        return 0.0

    # Compute standard deviation of downside returns
    downside_std = downside_returns.std(ddof=1)  # ddof=1 for sample std dev

    # Handle edge cases
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
        float: The standard deviation of downside returns.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    # Create DataFrame of net_size over time
    data = [(s.total_value, s.created_at) for s in snapshots]
    df = pd.DataFrame(data, columns=["total_value", "created_at"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at').copy()

    # Compute percentage returns
    df['return'] = df['total_value'].pct_change()
    df = df.dropna()

    if df.empty:
        return 0.0

    # Filter downside returns
    df_returns = df['return']

    if df_returns.empty:
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

    # Create DataFrame from snapshots
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.drop_duplicates("created_at").set_index("created_at")
    df = df.sort_index()
    # Resample to daily frequency (end of day)
    daily_df = df.resample("D").last().ffill().dropna()

    # Calculate daily returns
    daily_df["return"] = daily_df["total_value"].pct_change().dropna()

    if daily_df["return"].empty:
        return 0.0

    return daily_df["return"].std()


def get_downside_std_of_daily_returns(snapshots):
    """
    Calculate the downside standard deviation of daily returns from a list of snapshots.
    Resamples data to daily frequency using end-of-day values.

    Args:
        snapshots (List[PortfolioSnapshot]): Snapshots with total_value and created_at.

    Returns:
        float: Downside standard deviation of daily returns.
    """
    if len(snapshots) < 2:
        return 0.0  # Not enough data

    # Create DataFrame from snapshots
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.drop_duplicates("created_at").set_index("created_at")
    df = df.sort_index()

    # Resample to daily frequency (end of day)
    daily_df = df.resample("D").last().dropna()

    # Calculate daily returns
    daily_df["return"] = daily_df["total_value"].pct_change().dropna()

    # Filter only negative returns for downside deviation
    negative_returns = daily_df["return"][daily_df["return"] < 0]

    if negative_returns.empty:
        return 0.0

    return negative_returns.std()
