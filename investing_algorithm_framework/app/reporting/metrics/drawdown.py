""""
Max Drawdown (MDD) — a key risk metric that shows the worst
peak-to-trough decline of a portfolio:

| **Max Drawdown (%)** | **Interpretation**                                                   |
|-----------------------|----------------------------------------------------------------------|
| **0% to -5%**         | 🟢 Excellent — Very low risk, typical for conservative strategies     |
| **-5% to -10%**       | ✅ Good — Moderate volatility, acceptable for balanced portfolios     |
| **-10% to -20%**      | ⚠️ Elevated Risk — Common in growth or actively managed strategies    |
| **-20% to -40%**      | 🔻 High Risk — Significant drawdown, typical of aggressive strategies |
| **> -40%**            | 🚨 Very High Risk — Risk of capital loss or strategy failure          |
"""
from typing import List, Tuple
from datetime import datetime
from investing_algorithm_framework.domain import BacktestReport
from .equity_curve import get_equity_curve


def get_drawdown_series(
    backtest_report: BacktestReport
) -> List[Tuple[datetime, float]]:
    """
    Calculate the drawdown series of a backtest report.

    The drawdown is calculated as the percentage difference
    between the current equity value and the maximum equity value
    observed up to that point in time.

    Args:
        backtest_report (BacktestReport): The backtest report
            containing history of the portfolio.

    Returns:
        List[Tuple[datetime, float]]: A list of tuples with datetime
            and drawdown percentage. The drawdown is expressed as a
            negative percentage, where 0% means no drawdown and -100%
            means the portfolio has lost all its value.
    """
    equity_curve = get_equity_curve(backtest_report)

    drawdown_series = []
    max_value = None

    for timestamp, value in equity_curve:
        if max_value is None:
            max_value = value
        max_value = max(max_value, value)
        drawdown = (value - max_value) / max_value  # This will be <= 0
        drawdown_series.append((timestamp, drawdown))

    return drawdown_series


def get_max_drawdown(backtest_report: BacktestReport) -> float:
    """
    Calculate the maximum drawdown of the portfolio as a percentage from the peak.

    Max Drawdown is the maximum observed loss from a peak to a trough before a new peak is achieved.
    It is expressed here as a negative percentage.

    Args:
        backtest_report (BacktestReport): The backtest report containing
                                          the equity history of the portfolio.

    Returns:
        float: The maximum drawdown as a negative percentage (e.g., -12.5 for a 12.5% drawdown).
    """
    equity_curve = get_equity_curve(backtest_report)
    if not equity_curve:
        return 0.0

    peak = equity_curve[0][1]
    max_drawdown_pct = 0.0

    for _, equity in equity_curve:
        if equity > peak:
            peak = equity

        drawdown_pct = (equity - peak) / peak  # Will be 0 or negative
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

    return abs(max_drawdown_pct)


def get_max_drawdown_absolute(backtest_report: BacktestReport) -> float:
    """
    Calculate the maximum absolute drawdown of the portfolio.

    This is the largest drop in equity (in currency units) from a peak to a trough
    during the backtest period.

    Args:
        backtest_report (BacktestReport): The backtest report containing
                                          the equity history of the portfolio.

    Returns:
        float: The maximum absolute drawdown as a positive number (e.g., €10,000).
    """
    equity_curve = get_equity_curve(backtest_report)
    if not equity_curve:
        return 0.0

    peak = equity_curve[0][1]
    max_drawdown = 0.0

    for _, equity in equity_curve:
        if equity > peak:
            peak = equity

        drawdown = peak - equity  # Drop from peak
        max_drawdown = max(max_drawdown, drawdown)

    return abs(max_drawdown)  # Return as positive number (e.g., €10,000)
