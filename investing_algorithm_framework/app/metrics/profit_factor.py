from collections import deque
from datetime import datetime
from typing import List, Tuple

from investing_algorithm_framework.domain.models import BacktestReport, \
    TradeStatus


def get_cumulative_profit_factor_series(
    backtest_report: BacktestReport
) -> list[tuple[datetime, float]]:
    """
    Calculates the cumulative profit factor over time from a backtest report.

    Args:
        backtest_report (BacktestReport): Instance containing closed trades.

    Returns:
        List of (datetime, float) tuples: (timestamp, cumulative profit factor)
    """
    results = []
    gross_profit = 0.0
    gross_loss = 0.0

    for trade in backtest_report.get_trades(
        trade_status=TradeStatus.CLOSED.value
    ):
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
    backtest_report: BacktestReport, window_size: int = 20
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

    for trade in backtest_report.get_trades(
        trade_status=TradeStatus.CLOSED.value
    ):
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


def get_profit_factor(backtest_report: BacktestReport) -> float:
    """
    Calculates the total profit factor at the end of the backtest.

    The profit factor is defined as:
        Total Gross Profit / Total Gross Loss

    Args:
        backtest_report (BacktestReport): An instance of BacktestReport
            containing closed trades.

    Returns:
        float: The profit factor at the end of the backtest.
               Returns float('inf') if there are no losses,
               and 0.0 if there are no profits and losses.
    """
    gross_profit = 0.0
    gross_loss = 0.0

    for trade in backtest_report.get_trades(trade_status=TradeStatus.CLOSED):
        profit = trade.net_gain
        if profit > 0:
            gross_profit += profit
        elif profit < 0:
            gross_loss += abs(profit)

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss
