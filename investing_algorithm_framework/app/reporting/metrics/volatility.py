"""
Volatility is a statistical measure of the dispersion of returns for a
given portfolio. In finance, it is commonly used as a proxy for risk.
This function calculates the standard deviation of daily log returns and
annualizes it, giving an estimate of how much the portfolio's value
fluctuates on a yearly basis.
"""

import pandas as pd
import numpy as np
from investing_algorithm_framework import BacktestReport


def get_volatility(backtest_report: BacktestReport) -> float:
    """
    Calculate the annualized volatility of portfolio net values.

    Args:
        backtest_report: BacktestReport object with snapshots and
            number_of_days

    Returns:
        Float: Annualized volatility as a float
    """
    snapshots = backtest_report.get_snapshots()

    if len(snapshots) < 2:
        return 0.0  # Not enough data to calculate volatility

    # Build DataFrame from snapshots
    records = [
        (snapshot.total_value, snapshot.created_at) for snapshot in snapshots
    ]
    df = pd.DataFrame(records, columns=['total_value', 'created_at'])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at').copy()

    # Calculate log returns
    df['log_return'] = np.log(df['total_value'] / df['total_value'].shift(1))
    df = df.dropna()

    if df.empty:
        return 0.0

    daily_volatility = df['log_return'].std()

    # Estimate trading days per year based on snapshot frequency
    total_days = backtest_report.number_of_days
    num_observations = len(df)

    if total_days > 0:
        trading_days_per_year = (num_observations / total_days) * 365
    else:
        trading_days_per_year = 252  # Default fallback

    return daily_volatility * np.sqrt(trading_days_per_year)
