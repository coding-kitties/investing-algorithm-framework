import pathlib
from datetime import datetime, timedelta

import pandas as pd

from investing_algorithm_framework import create_app, TimeUnit, \
    TradingStrategy, RESOURCE_DIRECTORY, PortfolioConfiguration, \
    Algorithm, CCXTOHLCVMarketDataSource


def start_date_func():
    return datetime.utcnow() - timedelta(days=17)

# Define market data sources
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=start_date_func
)
bitvavo_dot_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="DOT",
    market="BITVAVO",
    symbol="DOT/EUR",
    timeframe="2h",
    start_date_func=start_date_func
)


def calculate_moving_average(df: pd.DataFrame, period):
    return df['Close'].rolling(window=period).mean()


def is_ma_above(df: pd.DataFrame, period_one, period_two, date_time=None):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is
    above the ma_<period_two>
    """
    # Filter rows with date less than or equal to the given datetime,
    # if none take all rows
    if date_time is None:
        filtered_df = df
    else:
        filtered_df = df[df['Date'] <= date_time]

    if filtered_df.empty:
        raise Exception(
            f"Could not find moving average data for date {date_time}"
        )

    last_row = filtered_df.iloc[-1]
    ma_one = last_row[f'ma_{period_one}']
    ma_two = last_row[f'ma_{period_two}']
    return ma_one > ma_two


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC/EUR"]
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_dot_eur_ohlcv_2h]

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            if algorithm.has_open_orders(target_symbol):
                continue

            ohlcv_data = market_data[target_symbol]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            df["ma_9"] = calculate_moving_average(df, 9)
            df["ma_50"] = calculate_moving_average(df, 50)
            df["ma_100"] = calculate_moving_average(df, 100)

            if is_ma_above(df, 9, 50):
                print("9 day moving average is above 50 day moving average")

            if is_ma_above(df, 9, 100):
                print("9 day moving average is above 100 day moving average")

            if is_ma_above(df, 50, 100):
                print("50 day moving average is above 100 day moving average")

            if is_ma_above(df, 100, 200):
                print("100 day moving average is above 200 day moving average")


app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_strategy(MyTradingStrategy)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        api_key="<your_api_key>",
        secret_key="<your_secret_key>",
        trading_symbol="<your_trading_symbol>"
    )
)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_dot_eur_ohlcv_2h)

if __name__ == "__main__":
    app.run()
