"""
Module for calculating profit factor metrics from backtest trades.

| **Profit Factor** | **Interpretation**                                                                        |
| ----------------- | ----------------------------------------------------------------------------------------- |
| **< 1.0**         | **Losing strategy** — losses outweigh profits                                             |
| **1.0 – 1.3**     | Weak or barely breakeven — needs improvement or may not be sustainable                    |
| **1.3 – 1.6**     | Average — possibly profitable but sensitive to market regime changes                      |
| **1.6 – 2.0**     | Good — generally indicates a solid, sustainable edge                                      |
| **2.0 – 3.0**     | Very good — strong edge with lower drawdown risk                                          |
| **> 3.0**         | Excellent — rare in real markets; often associated with low-frequency or niche strategies |

"""

from collections import deque
from datetime import datetime
from typing import List, Tuple

from investing_algorithm_framework.domain.models import Trade


def get_cumulative_profit_factor_series(
    trades: List[Trade]
) -> list[tuple[datetime, float]]:
    """
    Calculates the cumulative profit factor over time from a backtest report.

    Args:
        trades (List[Trade]): List of closed trades from the backtest report.

    Returns:
        List of (datetime, float) tuples: (timestamp, cumulative profit factor)
    """
    results = []
    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:
        close_time = trade.closed_at
        profit = trade.net_gain

        if profit >= 0:
            gross_profit += profit
        else:
            gross_loss += abs(profit)

        # Calculate profit factor with division-by-zero protection
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float('inf') if gross_profit > 0 else 0.0

        results.append((close_time, profit_factor))

    return results


def get_rolling_profit_factor_series(
    trades: List[Trade], window_size: int = 20
) -> List[Tuple[datetime, float]]:
    """
    Calculates the rolling profit factor over time from a backtest report.

    The rolling profit factor is computed using the most recent
    `window_size` trades and updated after each closed trade.

    Args:
        backtest_report (BacktestReport): A instance of BacktestReport
            containing closed trades.
        window_size: The number of most recent trades to include in
            each rolling calculation.

    Returns:
        A list of tuples, where each tuple contains:
            - datetime: The close time of the trade (or aligned date).
            - float: The rolling profit factor at that time.
    """

    results = []
    trade_window = deque(maxlen=window_size)

    for trade in trades:
        close_time = trade.closed_at
        profit = trade.net_gain

        trade_window.append(profit)

        gross_profit = sum(p for p in trade_window if p >= 0)
        gross_loss = sum(abs(p) for p in trade_window if p < 0)

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float('inf') if gross_profit > 0 else 0.0

        results.append((close_time, profit_factor))

    return results


def get_profit_factor(trades: List[Trade]) -> float:
    """
    Calculates the total profit factor at the end of the backtest.

    The profit factor is defined as:
        Total Gross Profit / Total Gross Loss

    Args:
        trades (List[Trade]): List of closed trades from the backtest report.

    Returns:
        float: The profit factor at the end of the backtest.
               Returns float('inf') if there are no losses,
               and 0.0 if there are no profits and losses.
    """
    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:
        profit = trade.net_gain
        if profit > 0:
            gross_profit += profit
        elif profit < 0:
            gross_loss += abs(profit)

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def get_gross_profit(trades: List[Trade]) -> float:
    """
    Function to calculate the total gross profit from a list of trades.

    Args:
        trades (List[Trade]): List of closed trades from the backtest report.

    Returns:
        float: The total gross profit from the trades.
    """

    gross_profit = 0.0
    for trade in trades:
        if trade.net_gain > 0:
            gross_profit += trade.net_gain
    return gross_profit


def get_gross_loss(trades: List[Trade]) -> float:
    """
    Function to calculate the total gross loss from a list of trades.

    Args:
        trades (List[Trade]): List of closed trades from the backtest report.

    Returns:
        float: The total gross loss from the trades.
    """

    gross_loss = 0.0
    for trade in trades:
        if trade.net_gain < 0:
            gross_loss += abs(trade.net_gain)
    return gross_loss
