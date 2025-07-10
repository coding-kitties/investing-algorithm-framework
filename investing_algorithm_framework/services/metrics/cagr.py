"""
The Compound Annual Growth Rate (CAGR) normalizes returns over a one-year
period, allowing you to compare performance across different timeframes.
It assumes the investment grows at a steady rate and compounds over time.

This formula is suitable whether your data spans:

* Less than a year (e.g. 30 days)
* Exactly a year (365 days)
* More than a year (e.g. 500 days)
"""

import pandas as pd
from typing import List
from investing_algorithm_framework.domain import PortfolioSnapshot


def get_cagr(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the Compound Annual Growth Rate (CAGR) of a backtest report.
    CAGR is a useful metric to evaluate the performance of an investment
    over a period of time, normalizing the return to a one-year basis.

    The formula for CAGR is:
    CAGR = (End Value / Start Value) ^ (1 / Number of Years) - 1

    Where:
        - End Value is the final value of the investment
        - Start Value is the initial value of the investment
        - Number of Years is the total time period in years
    This function assumes that the snapshots in the report are ordered by
    creation date and that the net size represents the value of the investment.

    Args:
        snapshots (list[Snapshot]): A list of snapshots

    Returns:
        Float: The CAGR as a decimal. Returns 0.0 if not enough
            data is available.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    # Convert snapshots to DataFrame
    data = [(s.total_value, s.created_at) for s in snapshots]
    df = pd.DataFrame(data, columns=["total_value", "created_at"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at')
    start_value = df.iloc[0]['total_value']
    end_value = df.iloc[-1]['total_value']
    start_date = df.iloc[0]['created_at']
    end_date = df.iloc[-1]['created_at']
    num_days = (end_date - start_date).days

    if num_days == 0 or start_value == 0:
        return 0.0

    # Apply CAGR formula
    return (end_value / start_value) ** (365 / num_days) - 1
