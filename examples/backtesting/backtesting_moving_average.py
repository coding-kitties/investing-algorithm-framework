import pathlib
from datetime import datetime, timedelta
from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TimeUnit, CCXTOHLCVMarketDataSource, Algorithm, pretty_print_backtest, \
    CCXTTickerMarketDataSource, PortfolioConfiguration

import tulipy as tp
import pandas as pd

# This trading strategy uses tulip indicators https://pypi.org/project/tulipy/
# and pandas https://pypi.org/project/pandas/

# Define market data sources
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="bitvavo",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=lambda : datetime.utcnow() - timedelta(days=17)
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="bitvavo",
    symbol="BTC/EUR",
    backtest_timeframe="2h" # We want the ticker data to
    # be sampled every 2 hours, inline with the strategy interval
)
app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_portfolio_configuration(PortfolioConfiguration(
    initial_balance=400,
    market="bitvavo",
    trading_symbol="EUR",
))
symbols = ["BTC/EUR"]


def is_crossover(fast_series, slow_series):
    """
    Expect two numpy series (fast and slow).
    With the given series it will check if the fast has a crossover with the
    slow series
    """

    return fast_series[-2] <= slow_series[-2] \
           and fast_series[-1] > slow_series[-1]


def is_crossunder(fast_series, slow_series):
    """
    Expect two numpy series (fast and slow).
    With the given series it will check if the fast has a crossunder with the
    slow series
    """

    return fast_series[-2] >= slow_series[-2] \
        and fast_series[-1] < slow_series[-1]


def is_below_trend(fast_series, slow_series):
    return fast_series[-1] < slow_series[-1]


def is_above_trend(fast_series, slow_series):
    return fast_series[-1] > slow_series[-1]


def is_within_rsi_bounds(rsi_series, lower_bound, upper_bound):
    return lower_bound <= rsi_series[-1] <= upper_bound


@app.strategy(
    time_unit=TimeUnit.HOUR,
    interval=2,
    market_data_sources=["BTC/EUR-ticker", "BTC/EUR-ohlcv"]
)
def perform_strategy(algorithm: Algorithm, market_data: dict):

    for symbol in symbols:
        target_symbol = symbol.split('/')[0]

        # Don't open a new order when we already have an open order
        if algorithm.has_open_orders(target_symbol):
            continue

        ohlcv_data = market_data[f"{symbol}-ohlcv"]
        df = pd.DataFrame(
            ohlcv_data,
            columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
        )
        fast = tp.sma(df["Close"].to_numpy(), period=9)
        slow = tp.sma(df["Close"].to_numpy(), period=50)
        price = market_data[f"{symbol}-ticker"]["bid"]

        if algorithm.has_position(target_symbol) \
                and is_crossunder(fast, slow):
            algorithm.close_position(target_symbol)
        elif not algorithm.has_position(target_symbol) and is_crossover(
                fast, slow):
            algorithm.create_limit_order(
                target_symbol=target_symbol,
                order_side="BUY",
                price=price,
                percentage_of_portfolio=25,
                precision=4
            )


if __name__ == "__main__":
    backtest_report = app.backtest(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
        pending_order_check_interval="2h",
    )
    pretty_print_backtest(backtest_report)