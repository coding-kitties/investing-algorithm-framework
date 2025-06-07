from typing import Optional

from investing_algorithm_framework.domain.models import BacktestReport
from .cagr import get_cagr
from .risk_free_rate import get_risk_free_rate_us
from .standard_deviation import get_standard_deviation_returns


def get_sharpe_ratio(
    backtest_report: BacktestReport, risk_free_rate: Optional[float] = None,
) -> float:
    """
    Calculate the Sharpe Ratio from a backtest report using daily or
    weekly returns.

    The Sharpe Ratio is calculated as:
        (Annualized Return - Risk-Free Rate) / Annualized Std Dev of Returns

    Args:
        backtest_report: Object with get_trades(trade_status=...) and
            `number_of_days` attributes.
        risk_free_rate (float, optional): Annual risk-free rate as a
            decimal (e.g., 0.047 for 4.7%).

    Returns:
        float: The Sharpe Ratio.
    """
    annualized_return = get_cagr(backtest_report)
    # Convert annualized return to decimal
    annualized_return = annualized_return / 100.0
    standard_deviation_downside = \
        get_standard_deviation_returns(backtest_report)

    if risk_free_rate is None:
        risk_free_rate = get_risk_free_rate_us()

    # Calculate sharp ratio
    return (annualized_return - risk_free_rate) / standard_deviation_downside
