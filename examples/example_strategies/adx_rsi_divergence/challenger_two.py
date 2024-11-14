import numpy as np
import tulipy as tp

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    CCXTTickerMarketDataSource, CCXTOHLCVMarketDataSource, Algorithm

# Ohlcv data source
btc_eur_ohlcv_2h_data = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR_ohlcv_2h",
    symbol="BTC/EUR",
    market="BITVAVO",
    timeframe="2h",
    window_size=200,
)

# Ohlcv data source
btc_eur_ohlcv_1d_data = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR_ohlcv_1d",
    symbol="BTC/EUR",
    market="BITVAVO",
    timeframe="1d",
    window_size=200,
)

# Ticker data source
btc_eur_ticker_data = CCXTTickerMarketDataSource(
    identifier="BTC/EUR_ticker",
    symbol="BTC/EUR",
    market="BITVAVO",
    backtest_timeframe="2h"
)


class RSIADXCrossOverAndDivergenceStrategy(TradingStrategy):
    """
    Implementation of TradingStrategy that uses RSI and ADX metrics. The strategy
    is parameterized in order to do experiments with it. This allows you
    to test the strategy with different configurations.
    """
    market_data_sources = [btc_eur_ohlcv_2h_data, btc_eur_ohlcv_1d_data, btc_eur_ticker_data]
    symbols = ["BTC/EUR"]
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
        self,
        rsi_period = 14,
        adx_period = 14,
        rsi_buy_threshold = 50,
        rsi_sell_threshold = 50,
        adx_buy_threshold = 35,
        adx_sell_threshold = 35,
    ):
        super(RSIADXCrossOverAndDivergenceStrategy, self).__init__()
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.adx_buy_threshold = adx_buy_threshold
        self.adx_sell_threshold = adx_sell_threshold

    def apply_strategy(self, algorithm, market_data):

        for symbol in self.symbols:
            ohlcv_2h_df = market_data[f"{symbol}_ohlcv_2h"]
            ohlcv_1d_df = market_data[f"{symbol}_ohlcv_1d"]
            ohlcv_2h_df = ohlcv_2h_df.to_pandas()
            ohlcv_1d_df = ohlcv_1d_df.to_pandas()
            ohlcv_1d_df = self.add_rsi(ohlcv_1d_df)
            ohlcv_1d_df = self.add_adx(ohlcv_1d_df)
            ohlcv_2h_df = self.add_rsi(ohlcv_2h_df)
            ohlcv_2h_df = self.add_adx(ohlcv_2h_df)
            target_symbol = symbol.split("/")[0]
            price = market_data[f"{symbol}_ticker"]["bid"]

            if self.is_buy_signal(symbol=target_symbol, algorithm=algorithm, ohlcv_2h_df=ohlcv_2h_df, ohlcv_1d_df=ohlcv_1d_df):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side="BUY",
                    price=price,
                    percentage_of_portfolio=20,
                    precision=4
                )
            elif self.is_sell_signal(symbol=target_symbol, algorithm=algorithm, ohlcv_2h_df=ohlcv_2h_df, ohlcv_1d_df=ohlcv_1d_df):
                algorithm.close_position(
                    symbol=target_symbol
                )

    def is_buy_signal(self, symbol, algorithm, ohlcv_2h_df, ohlcv_1d_df):

        if algorithm.has_open_orders(symbol):
            return False

        if algorithm.has_position(symbol):
            return False

        current_row_2h = ohlcv_2h_df.iloc[-1]
        current_row_1d = ohlcv_1d_df.iloc[-1]

        if current_row_1d["ADX"] >= self.adx_buy_threshold and self.is_crossover(ohlcv_2h_df["+DI"], ohlcv_2h_df["-DI"]) and current_row_2h["RSI"] <= self.rsi_buy_threshold:
            return True

        return False

    def is_sell_signal(self, symbol, algorithm, ohlcv_2h_df, ohlcv_1d_df):

        if algorithm.has_open_orders(symbol):
            return False

        if not algorithm.has_position(symbol):
            return False

        current_row_2h = ohlcv_2h_df.iloc[-1]
        current_row_1d = ohlcv_1d_df.iloc[-1]

        if current_row_1d["ADX"] > self.adx_sell_threshold and self.is_bearish_divergence(ohlcv_2h_df) and current_row_2h["RSI"] >= self.rsi_sell_threshold:
             return True

        return False

    def is_crossover(self, series_a, series_b):
        return series_a.iloc[-2] <= series_b.iloc[-2] and series_a.iloc[-1] >= series_b.iloc[-1]

    def add_rsi(self, data):
        # Calculate RSI
        rsi_values = tp.rsi(data['Close'].to_numpy(), period=self.rsi_period)

        # Pad NaN values for initial rows with a default value, e.g., 0
        rsi_values = np.concatenate((np.full(self.rsi_period, 0), rsi_values))

        # Assign RSI values to the DataFrame
        data["RSI"] = rsi_values
        return data

    def add_adx(self, data):
        plus_di, min_di = tp.di(high=data["High"].to_numpy(), low=data["Low"].to_numpy(), close=data["Close"].to_numpy(), period=self.adx_period)
        adx = tp.adx(high=data["High"].to_numpy(), low=data["Low"].to_numpy(), close=data["Close"].to_numpy(), period=self.adx_period)

        # Pad NaN values for initial rows with a default value, e.g., 0
        plus_di = np.concatenate((np.full(self.adx_period - 1, 0), plus_di))
        min_di = np.concatenate((np.full(self.adx_period - 1, 0), min_di))
        adx = np.concatenate((np.full(self.adx_period + 12 , 0), adx))

        # Assign adx values to the DataFrame
        data["+DI"] = plus_di
        data["-DI"] = min_di
        data["ADX"] = adx
        return data

    def is_bearish_divergence(self, data):
        # Get the most recent row (current datetime)
        current_row = data.iloc[-1]

        # Calculate price direction
        price_direction = current_row['Close'] - data.iloc[-2]['Close']

        # Calculate DI- direction
        di_minus_direction = current_row['-DI'] - data.iloc[-2]['-DI']

        # Check for bearish divergence
        return price_direction > 0 and di_minus_direction > 0


def create_algorithm(
    name,
    context,
    rsi_period=14,
    adx_period=14,
    rsi_buy_threshold=50,
    rsi_sell_threshold=50,
    adx_buy_threshold=35,
    adx_sell_threshold=35,
):
    algorithm = Algorithm(
        name=name,
        context=context,
        strategy=RSIADXCrossOverAndDivergenceStrategy(
            rsi_period=rsi_period,
            adx_period=adx_period,
            rsi_buy_threshold=rsi_buy_threshold,
            rsi_sell_threshold=rsi_sell_threshold,
            adx_buy_threshold=adx_buy_threshold,
            adx_sell_threshold=adx_sell_threshold,
        ),
        data_sources=[btc_eur_ohlcv_2h_data, btc_eur_ohlcv_1d_data, btc_eur_ticker_data],
    )
    return algorithm
