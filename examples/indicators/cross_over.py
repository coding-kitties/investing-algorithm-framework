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


def is_crossover(df: pd.DataFrame, period_one, period_two, date_time=None):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """
    df[f"ma_{period_one}_above_ma_{period_two}"] = \
        (df[f"ma_{period_one}"] > df[f"ma_{period_two}"]).astype(int)
    df[f"ma_{period_one}_ma_{period_two}_crosses"] = \
        df[f"ma_{period_one}_above_ma_{period_two}"].diff().astype('Int64')

    if date_time is None:
        filtered_df = df
    else:
        filtered_df = df[df['Date'] <= date_time]

    if filtered_df.empty:
        raise Exception(
            f"Could not find moving average data for date {date_time}"
        )

    last_row = filtered_df.iloc[-1]
    return last_row[f"ma_{period_one}_ma_{period_two}_crosses"] != 0


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


def calculate_moving_average(df: pd.DataFrame, period):
    return df['Close'].rolling(window=period).mean()


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_dot_eur_ohlcv_2h]
    symbols = ["BTC/EUR", "DOT/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]
            ohlcv_data = market_data[target_symbol]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            df["ma_9"] = calculate_moving_average(df, 9)
            df["ma_200"] = calculate_moving_average(df, 200)

            if is_crossover(df, 9, 200):
                print("crossover buy signal")
            elif is_crossover(df, 200, 9):
                print("crossover sell signal")


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

if __name__ == "__main__":
    app.run()