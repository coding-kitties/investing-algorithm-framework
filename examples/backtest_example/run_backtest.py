from datetime import datetime, timedelta

from algorithm.algorithm import algorithm
from algorithm.data_sources import bitvavo_btc_eur_ohlcv_2h, \
    bitvavo_dot_eur_ohlcv_2h, bitvavo_dot_eur_ticker, bitvavo_btc_eur_ticker
from app import app
from investing_algorithm_framework import PortfolioConfiguration, \
    pretty_print_backtest, BacktestDateRange

app.add_algorithm(algorithm)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_dot_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_market_data_source(bitvavo_dot_eur_ticker)


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
    date_range = BacktestDateRange(
        start_date=start_date,
        end_date=end_date
    )
    backtest_report = app.run_backtest(
        algorithm=algorithm,
        backtest_date_range=date_range,
    )
    pretty_print_backtest(backtest_report)
