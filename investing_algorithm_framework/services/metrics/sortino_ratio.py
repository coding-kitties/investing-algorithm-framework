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
               (Downside Deviation of Daily Returns × sqrt(Periods Per Year))

where Downside Deviation = sqrt(mean(min(r, 0)**2)) over ALL periods.

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
        - Downside Standard Deviation is the root-mean-square shortfall
          below the target, averaged over every period (not the standard
          deviation of the negative returns alone)

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.
        risk_free_rate (float): Annual risk-free rate as a decimal
            (e.g., 0.047 for 4.7%).

    Returns:
        float: The Sortino Ratio. Returns ``0.0`` when there is not enough
            data, and ``float('inf')`` when no period fell below the target
            but the excess return is positive (mirrors the division-by-zero
            convention used by ``get_profit_factor`` and ``get_omega_ratio``).
    """
    snapshots = sorted(snapshots, key=lambda s: s.created_at)

    if not snapshots:
        return 0.0

    mean_daily_return = get_mean_daily_return(snapshots)
    std_downside_daily_return = get_downside_std_of_daily_returns(snapshots)

    if std_downside_daily_return == 0:
        # No period fell below the target, so there is no downside risk to
        # divide by. This mirrors the division-by-zero convention already used
        # by get_profit_factor and get_omega_ratio: unbounded when the excess
        # return is positive, 0.0 when there is nothing to reward.
        excess_return = mean_daily_return * 365 - risk_free_rate
        return float('inf') if excess_return > 0 else 0.0

    # Formula: Sharpe Ratio = (Mean Daily Return × Periods Per Year - Risk-Free Rate) /
    # (Standard Deviation of Daily Returns × sqrt(Periods Per Year))
    ratio = (mean_daily_return * 365 - risk_free_rate) / \
        (std_downside_daily_return * math.sqrt(365))

    if np.float64("inf") == ratio or np.float64("-inf") == ratio:
        return float('inf')

    return ratio if not np.isnan(ratio) else 0.0
