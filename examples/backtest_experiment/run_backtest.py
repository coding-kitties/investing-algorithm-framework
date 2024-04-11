import json
from datetime import datetime, timedelta

from algorithms import create_algorithm
from app import app
from investing_algorithm_framework import PortfolioConfiguration, \
    pretty_print_backtest_reports_evaluation, BacktestReportsEvaluation

if __name__ == "__main__":
    end_date = datetime(2023, 12, 2)
    start_date = end_date - timedelta(days=100)
    json = json.load(open("configuration.json"))
    algorithms = []

    # Create the algorithms with the configuration json
    for configuration in json:
        algorithms.append(create_algorithm(**configuration))

    # Add a portfolio configuration of 400 euro initial balance
    app.add_portfolio_configuration(
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="EUR",
            initial_balance=400,
        )
    )
    reports = app.run_backtests(
        algorithms=algorithms,
        date_ranges=[
            (datetime(2023, 7, 2),
             datetime(2023, 7, 2) + timedelta(days=200)),
            (datetime(2022, 7, 2),
             datetime(2022, 7, 2) + timedelta(days=200)),
            (datetime(2024, 1, 1),
             datetime(2024, 1, 1) + timedelta(days=100)),
        ],
        pending_order_check_interval="2h",
    )
    evaluation = BacktestReportsEvaluation(reports)
    pretty_print_backtest_reports_evaluation(evaluation)
