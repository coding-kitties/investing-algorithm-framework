"""
| **Calmar Ratio** | **Interpretation**                                          |
| ---------------- | ----------------------------------------------------------- |
| **> 3.0**        | **Excellent** – strong return vs. drawdown                  |
| **2.0 – 3.0**    | **Very Good** – solid risk-adjusted performance             |
| **1.0 – 2.0**    | **Acceptable** – decent, especially for volatile strategies |
| **< 1.0**        | **Poor** – high drawdowns relative to return                |
"""

from typing import List
from investing_algorithm_framework.domain import PortfolioSnapshot
from .cagr import get_cagr
from .drawdown import get_max_drawdown


def get_calmar_ratio(snapshots: List[PortfolioSnapshot]):
    """
    Calculate the Calmar Ratio, which is the ratio of the annualized
    return to the maximum drawdown.

    Formula:
        Calmar Ratio = CAGR / |Maximum Drawdown|

    The Calmar Ratio is a measure of risk-adjusted return,
    where a higher ratio indicates a more favorable risk-return profile.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.

    Returns:
        float: The Calmar Ratio.
    """
    cagr = get_cagr(snapshots)
    max_drawdown = get_max_drawdown(snapshots)

    if max_drawdown == 0 or max_drawdown is None:
        return 0.0

    return cagr / max_drawdown
