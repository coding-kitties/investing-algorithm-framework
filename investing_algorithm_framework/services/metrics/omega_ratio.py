"""
The Omega Ratio is a risk-return measure that, unlike the Sharpe or
Sortino ratio, uses the *entire* return distribution rather than just
its mean and standard deviation. It is the ratio of the probability
weighted gains above a minimum acceptable threshold to the probability
weighted losses below that threshold.

| **Omega Ratio** | **Interpretation**                                   |
| ---------------- | ---------------------------------------------------- |
| **< 1.0**        | Losing strategy relative to the threshold             |
| **1.0 – 1.5**    | Weak edge                                             |
| **1.5 – 3.0**    | Solid edge                                            |
| **> 3.0**        | Excellent — rare, verify for overfitting              |

Omega Ratio Formula (per-period returns ``r`` against threshold ``t``):

    Omega = sum(max(r - t, 0)) / sum(max(t - r, 0))

Unlike Sharpe/Sortino, Omega makes no distributional assumption
(normality) about returns, so it captures skew and fat tails that a
simple mean/variance ratio misses.
"""
from typing import List

from investing_algorithm_framework.domain import PortfolioSnapshot

from ._returns_helper import daily_twr_returns


def get_omega_ratio(
    snapshots: List[PortfolioSnapshot], threshold: float = 0.0
) -> float:
    """
    Calculate the Omega Ratio from a backtest's daily TWR returns.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.
        threshold (float, optional): Minimum acceptable per-period
            (daily) return. Defaults to ``0.0`` (breakeven).

    Returns:
        float: The Omega Ratio. Returns ``0.0`` when there is not
            enough data, and ``float('inf')`` when there are gains but
            no returns below the threshold (mirrors the
            division-by-zero convention used by ``get_profit_factor``).
    """
    returns = daily_twr_returns(snapshots)

    if returns.empty:
        return 0.0

    gains = (returns - threshold).clip(lower=0).sum()
    losses = (threshold - returns).clip(lower=0).sum()

    if losses == 0:
        return float("inf") if gains > 0 else 0.0

    return float(gains / losses)
