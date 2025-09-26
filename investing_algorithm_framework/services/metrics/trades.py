from typing import List, Tuple

from investing_algorithm_framework.domain import Trade, TradeStatus, \
    OperationalException


def get_positive_trades(
    trades: List[Trade]
) -> Tuple[int, float]:
    """
    Calculate the number and percentage of positive trades.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        Tuple[int, float]: A tuple containing the number of positive trades
            and the percentage of positive trades.
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is empty or None, cannot compute positive trades."
        )

    closed_trades = [
        trade for trade in trades if TradeStatus.CLOSED.equals(trade.status)
    ]

    positive_trades = [
        trade for trade in closed_trades if trade.net_gain > 0
    ]
    number_of_positive_trades = len(positive_trades)
    percentage_positive_trades = (
        (number_of_positive_trades / len(closed_trades)) * 100.0
        if len(closed_trades) > 0 else 0.0
    )
    return number_of_positive_trades, percentage_positive_trades


def get_negative_trades(
    trades: List[Trade]
) -> Tuple[int, float]:
    """
    Calculate the number and percentage of negative trades.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        Tuple[int, float]: A tuple containing the number of negative trades
            and the percentage of negative trades.
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is empty or None, cannot compute negative trades."
        )

    closed_trades = [
        trade for trade in trades if TradeStatus.CLOSED.equals(trade.status)
    ]

    negative_trades = [
        trade for trade in closed_trades if trade.net_gain < 0
    ]
    number_of_negative_trades = len(negative_trades)
    percentage_negative_trades = (
        (number_of_negative_trades / len(closed_trades)) * 100.0
        if len(closed_trades) > 0 else 0.0
    )
    return number_of_negative_trades, percentage_negative_trades


def get_number_of_trades(
    trades: List[Trade]
) -> int:
    """
    Calculate the total number of trades.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        int: The total number of trades.
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is None, cannot compute number of trades."
        )
    return len(trades)


def get_number_of_open_trades(
    trades: List[Trade]
) -> int:
    """
    Calculate the number of open trades.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        int: The number of open trades.
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is None, cannot compute number of open trades."
        )

    open_trades = [
        trade for trade in trades if TradeStatus.OPEN.equals(trade.status)
    ]
    return len(open_trades)


def get_number_of_closed_trades(
    trades: List[Trade]
) -> int:
    """
    Calculate the number of closed trades.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        int: The number of closed trades.
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is None, cannot compute number of closed trades."
        )

    closed_trades = [
        trade for trade in trades if TradeStatus.CLOSED.equals(trade.status)
    ]
    return len(closed_trades)


def get_average_trade_duration(
    trades: List[Trade]
) -> float:
    """
    Calculate the average duration of closed trades in hours.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        float: The average trade duration in hours.
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is None, cannot compute average trade duration."
        )

    total_duration = 0.0

    for trade in trades:
        if TradeStatus.CLOSED.equals(trade.status):
            total_duration += (trade.closed_at - trade.opened_at)\
                                  .total_seconds() / 3600

    number_of_trades = get_number_of_closed_trades(trades)
    return total_duration / number_of_trades if number_of_trades > 0 else 0.0


def get_average_trade_size(
    trades: List[Trade]
) -> float:
    """
    Calculate the average trade size based on the amount
    and open price of each trade.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        float: The average trade size.
    """

    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is None, cannot compute average trade size."
        )

    total_trade_size = 0.0

    for trade in trades:
        total_trade_size += trade.amount * trade.open_price

    number_of_trades = get_number_of_trades(trades)
    return total_trade_size / number_of_trades if number_of_trades > 0 else 0.0


def get_average_trade_return(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the average return (absolute PnL) and
    average return percentage (per trade) of closed trades.
    """
    if not trades or len(trades) == 0:
        raise OperationalException(
            "Trades list is empty, cannot compute average return."
        )

    closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED]
    if not closed_trades:
        return 0.0, 0.0

    total_return = sum(t.net_gain for t in closed_trades)
    average_return = total_return / len(closed_trades)

    percentage_returns = [
        (t.net_gain / t.cost) * 100.0 for t in closed_trades if t.cost > 0
    ]
    average_return_percentage = (
        sum(percentage_returns) / len(percentage_returns)
        if percentage_returns else 0.0
    )

    return average_return, average_return_percentage


def get_average_trade_gain(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the average gain from a list of trades.

    The average gain is calculated as the mean of all positive returns.

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Tuple[float, float]: The average gain
        percentage of the average loss
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is empty or None, cannot calculate average gain."
        )

    gains = [t.net_gain for t in trades if t.net_gain > 0]
    cost = sum(t.cost for t in trades if t.net_gain > 0)

    if not gains:
        return 0.0, 0.0

    average_gain = sum(gains) / len(gains)
    percentage = (average_gain / cost) if cost > 0 else 0.0
    return average_gain, percentage


def get_average_trade_loss(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the average loss from a list of trades.

    The average loss is calculated as the mean of all negative returns.

    Args:
        trades (List[Trade]): List of trades.
    Returns:
        Tuple[float, float]: The average loss
        percentage of the average loss
    """
    if trades is None or len(trades) == 0:
        raise OperationalException(
            "Trades list is empty or None, cannot calculate average loss."
        )

    losses = [t.net_gain for t in trades if t.net_gain < 0]
    cost = sum(t.cost for t in trades if t.net_gain < 0)

    if not losses:
        return 0.0, 0.0

    average_loss = sum(losses) / len(losses)
    percentage = (average_loss / cost) if cost > 0 else 0.0
    return average_loss, percentage


def get_median_trade_return(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the median return from a list of trades.

    The median return is calculated as the median of all returns.

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Tuple[float, float]: The median return
        percentage of the median return
    """

    if not trades:
        return 0.0, 0.0

    sorted_returns = sorted(t.net_gain for t in trades)
    n = len(sorted_returns)
    mid = n // 2

    if n % 2 == 0:
        median_return = (sorted_returns[mid - 1] + sorted_returns[mid]) / 2
    else:
        median_return = sorted_returns[mid]

    cost = sum(t.cost for t in trades)
    percentage = (median_return / cost) if cost > 0 else 0.0
    return median_return, percentage


def get_best_trade(trades: List[Trade]) -> Trade:
    """
    Get the trade with the highest net gain.

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Trade: The trade with the highest net gain.
    """

    if not trades:
        return None

    return max(trades, key=lambda t: t.net_gain)


def get_worst_trade(trades: List[Trade]) -> Trade:
    """
    Get the trade with the lowest net gain (worst trade).

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Trade: The trade with the lowest net gain.
    """

    if not trades:
        return None

    return min(trades, key=lambda t: t.net_gain)


