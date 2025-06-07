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
"""

from typing import Optional

from investing_algorithm_framework.domain import BacktestReport
from .cagr import get_cagr
from .risk_free_rate import get_risk_free_rate_us
from .standard_deviation import get_standard_deviation_downside_returns


def get_sortino_ratio(
    report: BacktestReport, risk_free_rate: Optional[float] = None,
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
        report (BacktestReport): The backtest report containing snapshots.
        region (str): Region used to fetch risk-free rate (e.g. 'us').
        risk_free_rate (float): Override for risk-free rate. If None, fetch from data source.
        frequency (str): Frequency to calculate returns: 'daily' or 'weekly'.

    Returns:
        float: The Sortino Ratio.
    """
    annualized_return = get_cagr(report)

    # Convert annualized return to decimal
    annualized_return = annualized_return / 100.0
    standard_deviation_downside = \
        get_standard_deviation_downside_returns(report)

    if risk_free_rate is None:
        risk_free_rate = get_risk_free_rate_us()

    if standard_deviation_downside == 0.0:
        print("returning inf because standard deviation downside is 0")
        return float("inf")

    if annualized_return == 0:
        return 0

    # Calculate sortino ratio
    return (annualized_return - risk_free_rate) / standard_deviation_downside
