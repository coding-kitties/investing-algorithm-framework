from datetime import timedelta
from investing_algorithm_framework.domain import BacktestReport


def get_exposure_time(report: BacktestReport):
    """
    Calculates the exposure time as a fraction of the total backtest duration
    that the strategy had capital deployed (i.e., at least one open position).

    Returns:
        A float between 0 and 1 representing the fraction of time the strategy
        was exposed to the market.
    """
    trades = report.get_trades()

    if not trades:
        return 0.0

    total_trade_duration = timedelta(0)
    for trade in trades:
        entry = trade.created_at
        exit = trade.closed_at or report.backtest_end_date  # open trades counted up to end

        if exit > entry:
            total_trade_duration += exit - entry

    backtest_duration = report.backtest_end_date - report.backtest_start_date
    if backtest_duration.total_seconds() == 0:
        return 0.0

    return (total_trade_duration.total_seconds()
            / backtest_duration.total_seconds())


def get_average_trade_duration(report: BacktestReport):
    """
    Calculates the average duration of trades in the backtest report.

    Returns:
        A float representing the average trade duration in hours.
    """
    trades = report.get_trades()

    if not trades:
        return 0.0

    total_duration = timedelta(0)
    for trade in trades:
        trade_duration = trade.duration

        if trade_duration is not None:
            total_duration += trade_duration

    average_trade_duration = total_duration / len(trades)
    return average_trade_duration.total_seconds() / 3600.0  # Convert to hours
