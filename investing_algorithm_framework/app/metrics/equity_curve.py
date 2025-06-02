from datetime import datetime
from investing_algorithm_framework.domain import BacktestReport


def get_equity_curve(
    backtest_report: BacktestReport
) -> list[tuple[datetime, float]]:
    """
    Calculate the total size of the portfolio at each snapshot timestamp.

    Args:
        backtest_report (BacktestReport): The backtest report
            containing history of the portfolio.

    Returns:
        list[tuple[datetime, float]]: A list of tuples with
            timestamps and total sizes.
    """
    series = []
    for snapshot in backtest_report.get_snapshots():
        timestamp = snapshot.created_at
        total_size = snapshot.net_size
        series.append((timestamp, total_size))

    return series
