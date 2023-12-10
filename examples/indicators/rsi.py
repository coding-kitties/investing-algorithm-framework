from datetime import datetime, timedelta

import pandas as pd
import pathlib

from investing_algorithm_framework import TimeUnit, \
    TradingStrategy, create_app, RESOURCE_DIRECTORY, \
    Algorithm, CCXTOHLCVMarketDataSource, PortfolioConfiguration


def start_date_func():
    return datetime.utcnow() - timedelta(minutes=17)

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


def calculate_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
    """
    Calculate the Relative Strength Index (RSI) for a given DataFrame with OHLCV data.

    Parameters:
    - data: DataFrame with columns [datetime, open, high, low, close, volume]
    - period: Lookback period for RSI calculation (default is 14)

    Returns:
    - DataFrame with an additional 'rsi' column
    """
    df_deep_copy = df.copy(deep=True)

    # Calculate price changes
    df_deep_copy['Delta'] = df_deep_copy['Close'].diff()

    # Separate gains and losses
    gains = df_deep_copy['Delta'].where(df_deep_copy['Delta'] > 0, 0)
    losses = -df_deep_copy['Delta'].where(df_deep_copy['Delta'] < 0, 0)

    # Calculate average gains and average losses over the specified period
    avg_gains = gains.rolling(window=period, min_periods=1).mean()
    avg_losses = losses.rolling(window=period, min_periods=1).mean()

    # Calculate relative strength (RS)
    rs = avg_gains / avg_losses.replace(0, 1)  # Avoid division by zero

    # Calculate RSI
    df_deep_copy[f'Rsi_{period}'] = 100 - (100 / (1 + rs))

    # Replace NaN values in 'Rsi' column with 0
    df_deep_copy[f'Rsi_{period}'] = df_deep_copy[f'Rsi_{period}'].fillna(0)

    # Drop intermediate columns
    df_deep_copy.drop(['Delta'], axis=1, inplace=True)
    return df_deep_copy[f'Rsi_{period}']


def is_rsi_lower_then(df: pd.DataFrame, period, value, date_time=None):

    if date_time is None:
        filtered_df = df
    else:
        filtered_df = df[df['Date'] <= date_time]

    if filtered_df.empty:
        raise Exception(
            f"Could not find rsi data for date {date_time}"
        )

    last_row = filtered_df.iloc[-1]
    return last_row[f'Rsi_{period}'] < value


def is_rsi_higher_then(df: pd.DataFrame, period, value, date_time=None):

    if date_time is None:
        filtered_df = df
    else:
        filtered_df = df[df['Date'] <= date_time]

    if filtered_df.empty:
        raise Exception(
            f"Could not find rsi data for date {date_time}"
        )

    last_row = filtered_df.iloc[-1]
    return last_row[f'Rsi_{period}'] > value


class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.MINUTE
    interval = 15
    symbols = ["BTC/EUR", "DOT/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data):

        for symbol in self.symbols:
            ohlcv_data = market_data[symbol]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            df['Rsi_14'] = calculate_rsi(df, 14)

            if is_rsi_higher_then(df=df, period=14, value=70):
                print("RSI sell signal")
            elif is_rsi_lower_then(df=df, period=14, value=30):
                print("RSI buy signal")


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
