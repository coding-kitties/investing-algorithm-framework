from typing import List, Tuple
from datetime import datetime, date

import pandas as pd

from investing_algorithm_framework.domain import PortfolioSnapshot, Trade, \
    OperationalException


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
            second number is the percentage total return
    """

    if not snapshots or len(snapshots) < 2:
        return 0.0, 0.0

    initial_value = snapshots[0].total_value
    final_value = snapshots[-1].total_value

    if initial_value == 0:
        return 0.0, 0.0

    absolute_return = final_value - initial_value
    percentage = (absolute_return / initial_value)
    return absolute_return, percentage


def get_total_loss(
    snapshots: List[PortfolioSnapshot]
) -> Tuple[float, float]:
    """
    Calculate the total loss from portfolio snapshots.

    The total loss is calculated as the percentage change in portfolio value
    from the first snapshot to the last snapshot, only if there is a loss.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[Float, Float]: First number is the absolute loss and the
            second number is the percentage total loss
    """

    if not snapshots or len(snapshots) < 2:
        return 0.0, 0.0

    initial_value = snapshots[0].total_value
    final_value = snapshots[-1].total_value

    if initial_value == 0:
        return 0.0, 0.0

    absolute_return = final_value - initial_value

    if absolute_return >= 0:
        return 0.0, 0.0

    percentage = (absolute_return / initial_value)
    return absolute_return, percentage


def get_total_growth(
    snapshots: List[PortfolioSnapshot]
) -> Tuple[float, float]:
    """
    Calculate the total growth from portfolio snapshots.

    The total return is calculated as the percentage change in portfolio value
    from the first snapshot to the last snapshot added to the initial value.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        Tuple[Float, Float]: First number is the absolute return and the
            second number is the percentage total return
    """

    if not snapshots or len(snapshots) < 2:
        return 0.0, 0.0

    initial_value = snapshots[0].total_value
    final_value = snapshots[-1].total_value

    if initial_value == 0:
        return 0.0, 0.0

    growth = final_value - initial_value
    growth_percentage = (growth / initial_value)
    return growth, growth_percentage


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

    return winning_years / len(yearly_returns)


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


def get_cumulative_return(snapshots: list[PortfolioSnapshot]) -> float:
    """
    Calculate cumulative return over the full period of snapshots.
    Returns a single float (e.g., 0.25 for +25%).
    """
    if len(snapshots) < 2:
        return 0.0

    # Sort snapshots by date
    snapshots = sorted(snapshots, key=lambda s: s.created_at)

    start_value = snapshots[0].total_value
    end_value = snapshots[-1].total_value

    if start_value == 0:
        return 0.0

    return (end_value / start_value) - 1


def get_cumulative_return_series(
    snapshots: list[PortfolioSnapshot]
) -> List[Tuple[float, datetime]]:
    """
    Calculate cumulative returns from a list of PortfolioSnapshot objects.

    Args:
        snapshots (list[PortfolioSnapshot]): List of snapshots ordered by time.

    Returns:
        List[Tuple[float, datetime]]: Cumulative returns for each snapshot.
    """

    # Ensure snapshots are sorted by date
    snapshots = sorted(snapshots, key=lambda s: s.get_created_at())

    initial_value = snapshots[0].get_total_value()
    if initial_value == 0:
        raise ValueError("Initial portfolio value cannot be zero.")

    cumulative_returns = []
    for snap in snapshots:
        cum_return = (snap.get_total_value() / initial_value) - 1
        cumulative_returns.append((cum_return, snap.created_at))

    return cumulative_returns
