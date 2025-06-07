from investing_algorithm_framework.domain import BacktestReport

def get_net_profit(backtest_report: BacktestReport) -> float:
    """
    Calculate the total net profit of a backtest report.

    The net profit is defined as the difference between the final
    portfolio value and the initial portfolio value.

    Args:
        backtest_report (BacktestReport): The backtest report containing
            history of the portfolio.

    Returns:
        float: The total net profit.
    """
    return backtest_report.get_profit()
