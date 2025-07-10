from datetime import datetime
from typing import List
from investing_algorithm_framework.domain import PortfolioSnapshot


def get_equity_curve(
    snapshots: List[PortfolioSnapshot]
) -> list[tuple[float, datetime]]:
    """
    Calculate the total size of the portfolio at each snapshot timestamp.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.
    Returns:
        list[tuple[datetime, float]]: A list of tuples with
            timestamps and total sizes.
    """
    series = []
    for snapshot in snapshots:
        timestamp = snapshot.created_at
        total_size = snapshot.total_value
        series.append((total_size, timestamp))

    return series
