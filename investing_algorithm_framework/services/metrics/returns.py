from typing import List, Tuple
from datetime import datetime, date

import pandas as pd

from investing_algorithm_framework.domain import PortfolioSnapshot, Trade


def get_monthly_returns(snapshots: List[PortfolioSnapshot]) -> List[Tuple[float, datetime]]:
    """
    Calculate the monthly returns from a list of portfolio snapshots.

    Monthly return is calculated as the percentage change in portfolio value
    from the end of one month to the end of the next month.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        List[Tuple[float, datetime]]: A list of tuples containing the monthly return
            and the corresponding month.
    """

    # Create DataFrame from snapshots
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')

    # Resample to monthly frequency using last value of the month
    monthly_df = df.resample('ME').last().dropna()
    monthly_df['return'] = monthly_df['total_value'].pct_change()
    monthly_df = monthly_df.dropna()

    # Ensure returns are Python floats, not numpy floats
    monthly_returns = [
        (float(row['return']), row.name) for _, row in monthly_df.iterrows()
    ]
    return monthly_returns


def get_yearly_returns(snapshots: List[PortfolioSnapshot]) -> List[Tuple[float, date]]:
    """
    Calculate the yearly returns from a list of portfolio snapshots.

    Yearly return is calculated as the percentage change in portfolio value
    from the end of one year to the end of the next year.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        List[Tuple[float, date]]: A list of tuples containing the yearly return
            and the corresponding year.
    """

    # Create DataFrame from snapshots
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')

    # Remove timezone information if present to avoid warning
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # Resample to yearly frequency using last value of the year
    yearly_df = df.resample('YE').last().dropna()
    yearly_df['return'] = yearly_df['total_value'].pct_change()
    yearly_df = yearly_df.dropna()

    # Yearly returns with date objects only representing the year
    yearly_df.index = yearly_df.index.to_period('Y').to_timestamp()
    yearly_returns = [
        (float(row['return']), row.name) for _, row in yearly_df.iterrows()
    ]
    return yearly_returns


def get_average_loss(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the average loss from a list of trades

    The average loss is calculated as the mean of all negative returns.

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Tuple[float, float]: The average loss
        percentage of the average loss
    """

    losses = [t.net_gain for t in trades if t.net_gain < 0]
    cost = sum(t.cost for t in trades if t.net_gain < 0)

    if not losses:
        return 0.0, 0.0

    average_loss = sum(losses) / len(losses)
    percentage = (average_loss / cost) if cost > 0 else 0.0
    return average_loss, percentage


def get_average_gain(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the average gain from a list of trades.

    The average gain is calculated as the mean of all positive returns.

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Tuple[float, float]: The average gain
        percentage of the average loss
    """

    gains = [t.net_gain for t in trades if t.net_gain > 0]
    cost = sum(t.cost for t in trades if t.net_gain > 0)

    if not gains:
        return 0.0, 0.0

    average_gain = sum(gains) / len(gains)
    percentage = (average_gain / cost) if cost > 0 else 0.0
    return average_gain, percentage


def get_average_return(trades: List[Trade]) -> Tuple[float, float]:
    """
    Calculate the average return from a list of trades.

    The average return is calculated as the mean of all returns.

    Args:
        trades (List[Trade]): List of trades.

    Returns:
        Tuple[float, float]: The average return
        percentage of the average return
    """

    returns = [t.net_gain for t in trades]
    cost = sum(t.cost for t in trades)

    if not returns:
        return 0.0, 0.0

    average_return = sum(returns) / len(returns)
    percentage = (average_return / cost) if cost > 0 else 0.0
    return average_return, percentage


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


def get_percentage_winning_months(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the percentage of winning months from portfolio snapshots.

    A winning month is defined as a month where the portfolio value at the end
    of the month is greater than at the start of the month.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The percentage of winning months.
    """

    monthly_returns = get_monthly_returns(snapshots)
    winning_months = sum(1 for r, _ in monthly_returns if r > 0)

    if not monthly_returns:
        return 0.0

    return (winning_months / len(monthly_returns))


def get_best_month(snapshots: List[PortfolioSnapshot]) -> Tuple[float, datetime]:
    """
    Get the best month in terms of return from portfolio snapshots.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[float, datetime]: The best monthly return and the corresponding month.
    """

    monthly_returns = get_monthly_returns(snapshots)

    if not monthly_returns:
        return 0.0, None

    return max(monthly_returns, key=lambda x: x[0])

def get_worst_month(snapshots: List[PortfolioSnapshot]) -> Tuple[float, datetime]:
    """
    Get the worst month in terms of return from portfolio snapshots.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[float, datetime]: The worst monthly return and the corresponding month.
    """

    monthly_returns = get_monthly_returns(snapshots)

    if not monthly_returns:
        return 0.0, None

    return min(monthly_returns, key=lambda x: x[0])

def get_best_year(
    snapshots: List[PortfolioSnapshot]
) -> Tuple[float, datetime]:
    """
    Get the best year in terms of return from portfolio snapshots.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[float, datetime]: The best yearly return and the corresponding year.
    """

    yearly_returns = get_yearly_returns(snapshots)

    if not yearly_returns:
        return None, None

    return max(yearly_returns, key=lambda x: x[0])


def get_worst_year(
    snapshots: List[PortfolioSnapshot]
) -> Tuple[float, date]:
    """
    Get the worst year in terms of return from portfolio snapshots.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[float, datetime]: The worst yearly return and the corresponding year.
    """

    yearly_returns = get_yearly_returns(snapshots)

    if not yearly_returns:
        return None, None

    return min(yearly_returns, key=lambda x: x[0])


def get_average_monthly_return(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the average monthly return from portfolio snapshots.

    The average monthly return is calculated as the mean of all monthly returns.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The average monthly return as a percentage.
    """

    monthly_returns = get_monthly_returns(snapshots)

    if not monthly_returns:
        return 0.0

    return sum(r for r, _ in monthly_returns) / len(monthly_returns)

def get_average_monthly_return_winning_months(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the average monthly return from winning months in portfolio snapshots.

    The average monthly return is calculated as the mean of all monthly returns
    where the return is positive.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The average monthly return from winning months as a percentage.
    """

    monthly_returns = get_monthly_returns(snapshots)
    winning_months = [r for r, _ in monthly_returns if r > 0]

    if not winning_months:
        return 0.0

    return sum(winning_months) / len(winning_months)

def get_average_monthly_return_losing_months(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the average monthly return from losing months in portfolio snapshots.

    The average monthly return is calculated as the mean of all monthly returns
    where the return is negative.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The average monthly return from losing months as a percentage.
    """

    monthly_returns = get_monthly_returns(snapshots)
    losing_months = [r for r, _ in monthly_returns if r < 0]

    if not losing_months:
        return 0.0

    return sum(losing_months) / len(losing_months)


def get_average_yearly_return(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the average yearly return from portfolio snapshots.

    The average yearly return is calculated as the mean of all yearly returns.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The average yearly return as a percentage.
    """

    yearly_returns = get_yearly_returns(snapshots)

    if not yearly_returns:
        return 0.0

    return sum(r for r, _ in yearly_returns) / len(yearly_returns)


def get_total_return(
    snapshots: List[PortfolioSnapshot]
) -> Tuple[float, float]:
    """
    Calculate the total return from portfolio snapshots.

    The total return is calculated as the percentage change in portfolio value
    from the first snapshot to the last snapshot.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[Float, Float]: First number is the absolute return and the
            second number is the percetage total return
    """

    if not snapshots or len(snapshots) < 2:
        return 0.0

    initial_value = snapshots[0].total_value
    final_value = snapshots[-1].total_value

    if initial_value == 0:
        return 0.0

    absolute_return = final_value - initial_value
    percentage = (absolute_return / initial_value)
    return absolute_return, percentage


def get_percentage_winning_years(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the percentage of winning years from portfolio snapshots.

    A winning year is defined as a year where the portfolio value at the end
    of the year is greater than at the start of the year.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The percentage of winning years.
    """

    yearly_returns = get_yearly_returns(snapshots)
    winning_years = sum(1 for r, _ in yearly_returns if r > 0)

    if not yearly_returns:
        return 0.0

    return (winning_years / len(yearly_returns))


def get_total_net_gain(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the total net gain from portfolio snapshots.

    The total net gain is calculated as the difference between the final
    portfolio value and the initial portfolio value.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The total net gain.
    """

    if not snapshots:
        return 0.0

    return snapshots[-1].total_net_gain


def get_final_value(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the final portfolio value from portfolio snapshots.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The final portfolio value.
    """

    if not snapshots:
        return 0.0

    return snapshots[-1].total_value


def get_growth(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the growth of the portfolio from the first to the last snapshot.

    The growth is calculated as the percentage change in portfolio value
    from the first snapshot to the last snapshot.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The growth as a percentage.
    """

    if not snapshots or len(snapshots) < 2:
        return 0.0

    initial_value = snapshots[0].total_value
    final_value = snapshots[-1].total_value

    if initial_value == 0:
        return 0.0

    return (final_value - initial_value)


def get_growth_percentage(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the growth percentage of the portfolio from the first
    to the last snapshot.

    The growth percentage is calculated as the percentage change in
    portfolio value from the first snapshot to the last snapshot.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The growth percentage.
    """

    if not snapshots or len(snapshots) < 2:
        return 0.0

    initial_value = snapshots[0].total_value
    final_value = snapshots[-1].total_value

    if initial_value == 0:
        return 0.0

    return (final_value - initial_value) / initial_value
