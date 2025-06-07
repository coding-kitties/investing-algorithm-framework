import numpy as np
import pandas as pd
from investing_algorithm_framework.domain import BacktestReport

def get_standard_deviation_downside_returns(report: BacktestReport):
    """
    Calculate the standard deviation of downside returns from the net size
    of the reports.

    Args:
        report (BacktestReport): The report containing the equity curve.

    Returns:
        float: The standard deviation of downside returns.
    """
    snapshots = report.get_snapshots()

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


def get_standard_deviation_returns(report: BacktestReport):
    """
    Calculate the standard deviation of returns from the net size
    of the reports.

    Args:
        report (BacktestReport): The report containing the equity curve.

    Returns:
        float: The standard deviation of downside returns.
    """
    snapshots = report.get_snapshots()

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    # Create DataFrame of net_size over time
    data = [(s.net_size, s.created_at) for s in snapshots]
    df = pd.DataFrame(data, columns=["net_size", "created_at"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at').copy()

    # Compute percentage returns
    df['return'] = df['net_size'].pct_change()
    df = df.dropna()

    if df.empty:
        return 0.0

    # Filter downside returns
    df_returns = df['return']

    if df_returns.empty:
        return 0.0

    # Compute standard deviation of downside returns
    std = df_returns.std(ddof=1)  # ddof=1 for sample std dev

    # Handle edge cases
    if np.isnan(std):
        return 0.0

    return std
