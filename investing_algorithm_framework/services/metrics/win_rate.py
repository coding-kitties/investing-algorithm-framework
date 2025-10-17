"""
| Metric             | High Value Means...         | Weakness if Used Alone              |
| ------------------ | --------------------------- | ----------------------------------- |
| **Win Rate**       | Many trades are profitable  | Doesn't say how big wins/losses are |
| **Win/Loss Ratio** | Big wins relative to losses | Doesn’t say how *often* you win     |


Example of Non-Overlap:
Strategy A: 90% win rate, but average win is $1, average loss is $10 → not profitable.

Strategy B: 30% win rate, but average win is $300, average loss is $50 → highly profitable.

| Win Rate          | Win/Loss Ratio | Comment                            |
| ----------------- | -------------- | ---------------------------------- |
| High (>60%)       | <1             | Can still be profitable            |
| Moderate (40-60%) | \~1 or >1      | Ideal sweet spot                   |
| Low (<40%)        | >1             | Possible if big wins offset losses |


Practical Example:
* Win rate 40% with win/loss ratio 2: Good — you win less often but your
wins are twice as big.
* Win rate 60% with win/loss ratio 0.7: Also good — you win often
but your wins are smaller than losses.

What’s “good”?
* Typical win/loss ratio ranges from 0.5 to 3 depending on strategy style.
* Many profitable traders target win/loss ratio between 1.5 and 2.5.
* Very aggressive strategies might have a lower win rate but
higher win/loss ratio.
"""

from typing import List
from investing_algorithm_framework.domain import TradeStatus, Trade


def get_win_rate(trades: List[Trade]) -> float:
    """
    Calculate the win rate of the portfolio based on the backtest report.

    Win Rate is defined as the percentage of trades that were profitable.
    The percentage of trades that are profitable.

    Formula:
        Win Rate = Number of Profitable Trades / Total Number of Trades

    Example: If 60 out of 100 trades are profitable, the win rate is 60%.

    Args:
        trades (List[Trade]): List of trades from the backtest report.

    Returns:
        float: The win rate as a percentage (e.g., o.75 for 75% win rate).
    """
    trades = [
        trade for trade in trades if TradeStatus.CLOSED.equals(trade.status)
    ]
    positive_trades = sum(1 for trade in trades if trade.net_gain > 0)
    total_trades = len(trades)

    if total_trades == 0:
        return 0.0

    return positive_trades / total_trades

def get_current_win_rate(trades: List[Trade]) -> float:
    """
    Calculate the current win rate of the portfolio based on a list
    of recent trades.

    Current Win Rate is defined as the percentage of the most recent trades
    that were profitable. This metric also includes trades that are still open.

    Formula:
        Current Win Rate = Number of Profitable Recent Trades
            / Total Number of Recent Trades

    Args:
        trades (List[Trade]): List of recent trades.

    Returns:
        float: The current win rate as a percentage (e.g., 0.75 for
            75% win rate).
    """
    if not trades:
        return 0.0

    positive_trades = sum(1 for trade in trades if trade.net_gain_absolute > 0)
    total_trades = len(trades)

    return positive_trades / total_trades


def get_win_loss_ratio(trades: List[Trade]) -> float:
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
        trades (List[Trade]): List of trades from the backtest report.

    Returns:
        float: The win/loss ratio.
    """
    trades = [
        trade for trade in trades if TradeStatus.CLOSED.equals(trade.status)
    ]

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


def get_current_win_loss_ratio(trades: List[Trade]) -> float:
    """
    Calculate the current win/loss ratio of the portfolio based on a list
    of recent trades.

    Current Win/Loss Ratio is defined as the average profit of winning
    recent trades divided by the average loss of losing recent trades.
    This metric also includes trades that are still open.

    Formula:
        Current Win/Loss Ratio = Average Profit of Winning Recent Trades
            / Average Loss of Losing Recent Trades
    Args:
        trades (List[Trade]): List of recent trades.

    Returns:
        float: The current win/loss ratio.
    """
    if not trades:
        return 0.0

    # Separate winning and losing trades
    winning_trades = [t for t in trades if t.net_gain_absolute > 0]
    losing_trades = [t for t in trades if t.net_gain_absolute < 0]

    if not winning_trades or not losing_trades:
        return 0.0

    # Compute averages
    avg_win = sum(t.net_gain_absolute for t in winning_trades) / len(winning_trades)
    avg_loss = abs(
        sum(t.net_gain_absolute for t in losing_trades) / len(losing_trades))

    # Avoid division by zero
    if avg_loss == 0:
        return float('inf')

    return avg_win / avg_loss
