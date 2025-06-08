"""
| Metric             | High Value Means...         | Weakness if Used Alone              |
| ------------------ | --------------------------- | ----------------------------------- |
| **Win Rate**       | Many trades are profitable  | Doesn't say how big wins/losses are |
| **Win/Loss Ratio** | Big wins relative to losses | Doesn’t say how *often* you win     |


Example of Non-Overlap:
Strategy A: 90% win rate, but average win is $1, average loss is $10 → not profitable.

Strategy B: 30% win rate, but average win is $300, average loss is $50 → highly profitable.
"""

from investing_algorithm_framework import BacktestReport, TradeStatus


def get_win_rate(backtest_report: BacktestReport) -> float:
    """
    Calculate the win rate of the portfolio based on the backtest report.

    Win Rate is defined as the percentage of trades that were profitable.
    The percentage of trades that are profitable.

    Formula:
        Win Rate = (Number of Profitable Trades / Total Number of Trades) * 100

    Example: If 60 out of 100 trades are profitable, the win rate is 60%.

    Args:
        backtest_report (BacktestReport): The backtest report containing
                                          trade history.

    Returns:
        float: The win rate as a percentage (e.g., 75.0 for 75% win rate).
    """
    return backtest_report.percentage_positive_trades


def get_win_loss_ratio(backtest_report: BacktestReport) -> float:
    """
    Calculate the win/loss ratio of the portfolio based on the backtest report.

    Win/Loss Ratio is defined as the average profit of winning trades divided by
    the average loss of losing trades.

    Formula:
        Win/Loss Ratio = Average Profit of Winning Trades
            / Average Loss of Losing Trades

    Example: If the average profit of winning trades is $200 and the
            average loss of losing trades is $100, the win/loss ratio is 2.0.

    Args:
        backtest_report (BacktestReport): The backtest report containing
                                          trade history.

    Returns:
        float: The win/loss ratio.
    """
    trades = backtest_report.get_trades(trade_status=TradeStatus.CLOSED)

    if not trades:
        return 0.0

    # Separate winning and losing trades
    winning_trades = [t for t in trades if t.net_gain > 0]
    losing_trades = [t for t in trades if t.net_gain < 0]

    if not winning_trades or not losing_trades:
        return 0.0

    # Compute averages
    avg_win = sum(t.net_gain for t in winning_trades) / len(winning_trades)
    avg_loss = abs(
        sum(t.net_gain for t in losing_trades) / len(losing_trades))

    # Avoid division by zero
    if avg_loss == 0:
        return float('inf')

    return avg_win / avg_loss
