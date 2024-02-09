from datetime import datetime, timedelta

from investing_algorithm_framework import PortfolioConfiguration, \
    pretty_print_backtest

from app import app


# Add a portfolio configuration of 400 euro initial balance
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BINANCE",
        trading_symbol="EUR",
        initial_balance=400,
    )
)

if __name__ == "__main__":
    end_date = datetime(2023, 12, 2)
    start_date = end_date - timedelta(days=100)
    backtest_report = app.backtest(
        start_date=start_date,
        end_date=end_date,
        pending_order_check_interval="2h",
    )
    pretty_print_backtest(backtest_report)
