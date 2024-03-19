from datetime import datetime, timedelta

from algorithms import algorithm_one, algorithm_two, algorithm_three
from app import app
from investing_algorithm_framework import PortfolioConfiguration

if __name__ == "__main__":
    end_date = datetime(2023, 12, 2)
    start_date = end_date - timedelta(days=100)

    # Add a portfolio configuration of 400 euro initial balance
    app.add_portfolio_configuration(
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="EUR",
            initial_balance=400,
        )
    )

    # Run the backtest for each algorithm
    reports = app.run_backtests(
        algorithms=[
            algorithm_one,
            algorithm_two,
            algorithm_three,
        ],
        start_date=start_date,
        end_date=end_date,
        pending_order_check_interval="2h",
    )


    # pretty_print_expirement(reports)
