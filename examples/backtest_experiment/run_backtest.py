import json
from datetime import datetime

from algorithms import create_algorithm
from app import app
from investing_algorithm_framework import PortfolioConfiguration, \
    pretty_print_backtest_reports_evaluation, BacktestReportsEvaluation, \
    BacktestDateRange

if __name__ == "__main__":
    down_turn_date_range = BacktestDateRange(
        start_date=datetime(2021, 12, 21),
        end_date=datetime(2022, 6, 20),
        name="down_turn"
    )
    up_turn_date_range = BacktestDateRange(
        start_date=datetime(2022, 12, 20),
        end_date=datetime(2023, 6, 1),
        name="up_turn"
    )
    sideways_date_range = BacktestDateRange(
        start_date=datetime(2022, 6, 10),
        end_date=datetime(2023, 1, 10),
        name="sideways"
    )

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
            down_turn_date_range,
            up_turn_date_range,
            sideways_date_range
        ],
        pending_order_check_interval="2h",
    )
    evaluation = BacktestReportsEvaluation(reports)
    pretty_print_backtest_reports_evaluation(evaluation)
