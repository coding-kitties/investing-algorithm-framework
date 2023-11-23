import pathlib
from datetime import datetime, timedelta

import pandas as pd

from investing_algorithm_framework import create_app, TimeUnit, \
    TradingTimeFrame, TradingDataType, TradingStrategy, \
    RESOURCE_DIRECTORY, pretty_print_backtest, Algorithm, OrderSide


def is_golden_cross(df: pd.DataFrame, period_one, period_two, date_time=None):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is above
    the ma_<period_two>
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
    return last_row[f"ma_{period_one}_ma_{period_two}_crosses"] > 0


def is_death_cross(df: pd.DataFrame, period_one, period_two, date_time=None):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is above
    the ma_<period_two>
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
    return last_row[f"ma_{period_one}_ma_{period_two}_crosses"] < 0


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
    trading_data_types = [TradingDataType.OHLCV, TradingDataType.TICKER]
    trading_time_frame_start_date = datetime.utcnow() - timedelta(days=365)
    trading_time_frame = TradingTimeFrame.TWO_HOUR
    market = "BITVAVO"
    symbols = ["BTC/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            if algorithm.has_open_orders(target_symbol):
                continue

            ohlcv_data = market_data[TradingDataType.OHLCV][symbol]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            df["ma_9"] = calculate_moving_average(df, 9)
            df["ma_50"] = calculate_moving_average(df, 50)
            df["ma_100"] = calculate_moving_average(df, 100)
            price = market_data[TradingDataType.TICKER][symbol]["bid"]

            if is_golden_cross(df, '9', '50') \
                    and not algorithm.has_position(target_symbol) \
                    and not is_ma_above(df, '50', '100'):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4
                )
            elif algorithm.has_position(target_symbol) \
                    and is_death_cross(df, '9', '50'):
                algorithm.close_position(target_symbol)


app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_strategy(MyTradingStrategy)


if __name__ == "__main__":
    backtest_report = app.backtest(
        start_date=datetime(2023, 11, 12) - timedelta(days=100),
        end_date=datetime(2023, 11, 12),
        unallocated=400,
        trading_symbol="EUR"
    )
    pretty_print_backtest(backtest_report)
