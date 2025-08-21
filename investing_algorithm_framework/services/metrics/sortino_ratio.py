"""
The Sortino Ratio is a risk-adjusted performance metric that tells you how
much return you're getting per unit of downside risk — a more nuanced
alternative to the Sharpe Ratio, especially when returns are not
symmetrically distributed.

| **Sortino Ratio** | **Interpretation**                                                   |
|-------------------|----------------------------------------------------------------------|
| **< 0**           | 🚫 Bad — Portfolio underperforms the risk-free rate with downside risk |
| **0 to 1**        | ⚠️ Suboptimal — Low excess return relative to downside risk          |
| **1 to 2**        | ✅ Acceptable/Good — Reasonable performance for most portfolios       |
| **2 to 3**        | 💪 Strong — Very good risk-adjusted returns                          |
| **> 3**           | 🌟 Excellent — Rare, may indicate exceptional strategy or overfitting |

Formula:
Sortino Ratio = (Mean Daily Return × Periods Per Year - Risk-Free Rate) /
               (Downside Standard Deviation of Daily Returns × sqrt(Periods Per Year))

"""

from typing import Optional

import math
import numpy as np
from typing import List
from investing_algorithm_framework.domain import PortfolioSnapshot
from .mean_daily_return import get_mean_daily_return
from .risk_free_rate import get_risk_free_rate_us
from .standard_deviation import get_downside_std_of_daily_returns


def get_sortino_ratio(
    snapshots: List[PortfolioSnapshot], risk_free_rate: float
) -> float:
    """
    Calculate the Sortino Ratio for a given report.

    The formula for Sortino Ratio is:
        Sortino Ratio = (Annualized Return - Risk-Free Rate) / Downside Standard Deviation

    Where:
        - Annualized Return is the CAGR of the investment
        - Risk-Free Rate is the return of a risk-free asset (e.g. treasury bills)
        - Downside Standard Deviation is the standard deviation of negative returns

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.
        risk_free_rate (float): Annual risk-free rate as a decimal
            (e.g., 0.047 for 4.7%).

    Returns:
        float: The Sortino Ratio.
    """
    snapshots = sorted(snapshots, key=lambda s: s.created_at)

    if not snapshots:
        return float('inf')

    mean_daily_return = get_mean_daily_return(snapshots)
    std_downside_daily_return = get_downside_std_of_daily_returns(snapshots)

    if std_downside_daily_return == 0:
        return float('nan')  # or 0.0, depending on preference

    # Formula: Sharpe Ratio = (Mean Daily Return × Periods Per Year - Risk-Free Rate) /
    # (Standard Deviation of Daily Returns × sqrt(Periods Per Year))
    ratio = (mean_daily_return * 365 - risk_free_rate) / \
        (std_downside_daily_return * math.sqrt(365))

    if np.float64("inf") == ratio or np.float64("-inf") == ratio:
        return float('inf')

    return ratio if not np.isnan(ratio) else 0.0
