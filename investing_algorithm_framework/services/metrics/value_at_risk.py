from typing import List, Tuple
from datetime import datetime

from investing_algorithm_framework.domain import PortfolioSnapshot, \
    OperationalException

import pandas as pd


def get_value_at_risk(
    snapshots: List[PortfolioSnapshot],
    confidence: float = 0.95,
) -> float:
    """
    Calculate the historical Value at Risk (VaR) from portfolio snapshots.

    VaR represents the maximum expected loss at a given confidence level
    over the observed monthly return distribution.

    Args:
        snapshots: List of portfolio snapshots.
        confidence: Confidence level (e.g. 0.95 for 95th percentile).

    Returns:
        float: The VaR as a decimal (e.g. -0.05 means 5% loss).
    """
    monthly = _get_monthly_return_series(snapshots)
    if monthly is None or len(monthly) < 3:
        return 0.0
    quantile = 1 - confidence
    return float(monthly.quantile(quantile))


def get_conditional_value_at_risk(
    snapshots: List[PortfolioSnapshot],
    confidence: float = 0.95,
) -> float:
    """
    Calculate the Conditional Value at Risk (CVaR / Expected Shortfall)
    from portfolio snapshots.

    CVaR is the average loss in the worst (1-confidence)% of months.

    Args:
        snapshots: List of portfolio snapshots.
        confidence: Confidence level (e.g. 0.95 for 95th percentile).

    Returns:
        float: The CVaR as a decimal (e.g. -0.08 means 8% avg loss
            in worst months).
    """
    monthly = _get_monthly_return_series(snapshots)
    if monthly is None or len(monthly) < 3:
        return 0.0
    quantile = 1 - confidence
    var = monthly.quantile(quantile)
    tail = monthly[monthly <= var]
    if len(tail) == 0:
        return float(var)
    return float(tail.mean())


def _get_monthly_return_series(
    snapshots: List[PortfolioSnapshot],
) -> "pd.Series | None":
    """Helper: build a monthly return series from snapshots."""
    if not snapshots or len(snapshots) < 2:
        return None
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')
    monthly_df = df.resample('ME').last().dropna()
    monthly_df['return'] = monthly_df['total_value'].pct_change()
    monthly_df = monthly_df.dropna()
    if monthly_df.empty:
        return None
    return monthly_df['return']
