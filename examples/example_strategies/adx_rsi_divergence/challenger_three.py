from investing_algorithm_framework import CCXTOHLCVMarketDataSource, \
    TradingStrategy, TimeUnit, CCXTTickerMarketDataSource, Algorithm
import pandas as pd
from pandas import to_datetime
import numpy as np
from scipy.signal import argrelextrema
from collections import deque
import tulipy as tp

ohlcv_2h_data_source = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR_OHLCV",
    symbol="BTC/EUR",
    market="BITVAVO",
    timeframe="2h",
    window_size=200,
)
ticker_data_source = CCXTTickerMarketDataSource(
    identifier="BTC/EUR_TICKER",
    symbol="BTC/EUR",
    market="BITVAVO",
    backtest_timeframe="2h"
)


class TestStrategy(TradingStrategy):
    """
    Implementation of TradingStrategy that uses RSI and ADX metrics.
    The strategy is parameterized in order to do experiments with it.
    This allows you to test the strategy with different configurations.

    STRATEGY OUTLINE:

    Buy Signal:
        - The +DI crosses above the -DI + one of the following
        conditions is met:
            - If in the last 2 days there is a bullish divergence
                (higher low and lower low) between  the RSI_lows and
                the close price lows
            - If the RSI has decreased significantly in the last day
                (RSI_diff < -2)

    Sell Signal:
        - The -DI crosses above the +DI + one of the following conditions
        is met:
            - If in the last 2 days there is a bearish divergence
                (higher high and lower high) between the RSI_highs and
                the close price highs
            - If the ADX has decreased significantly in the last day
                (ADX_diff < -1)

    Additional Conditions:
        if the stop loss is triggered, the trade is closed.
        Stop loss is set at 6%.

    Args:
        rsi_period (int): The period for the RSI indicator
        adx_period (int): The period for the ADX indicator
        rsi_buy_threshold (int): The RSI buy threshold, range: 0-100
        rsi_sell_threshold (int): The RSI sell threshold,  range: 0-100
        adx_buy_threshold (int): The ADX buy threshold, range: 0-100
        adx_sell_threshold (int): The ADX sell threshold range: 0-100
        peaks_order (int): The number of periods to consider when calculating
        the peaks. For example, if the order is 2, the function will
        consider the current and previous periods to determine the peaks.
        peaks_k (int): The number of consecutive peaks that need to be
        higher or lower to be considered a peak.
    """
    market_data_sources = [ohlcv_2h_data_source, ticker_data_source]
    symbols = ["BTC/EUR"]
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
            self,
            rsi_period=14,
            adx_period=14,
            rsi_buy_threshold=50,
            rsi_sell_threshold=50,
            adx_buy_threshold=35,
            adx_sell_threshold=35,
            peaks_order=5,
            peaks_k=2
    ):
        super(TestStrategy, self).__init__()
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.adx_buy_threshold = adx_buy_threshold
        self.adx_sell_threshold = adx_sell_threshold
        self.peaks_order = peaks_order
        self.peaks_k = peaks_k

    def apply_strategy(self, algorithm, market_data):
        for symbol in self.symbols:

            raw_df = market_data[f"{symbol}_OHLCV"]
            ohlcv_df = raw_df.to_pandas()

            # Convert 'Datetime' column to datetime format if it's not already
            ohlcv_df['Datetime'] = to_datetime(ohlcv_df['Datetime'])

            # Set 'Datetime' column as the index
            ohlcv_df.set_index('Datetime', inplace=True)

            # Remove duplicate dates
            ohlcv_df = ohlcv_df[~ohlcv_df.index.duplicated(keep='first')]
            ohlcv_df = self.add_adx(ohlcv_df, period=self.adx_period)
            ohlcv_df = self.add_rsi(ohlcv_df, period=self.rsi_period)
            ohlcv_df = self.add_ema(ohlcv_df, key="Close", period=50)
            ohlcv_df = self.add_ema(ohlcv_df, key="Close", period=100)
            ohlcv_df = self.add_peaks(
                ohlcv_df, key="Close", order=self.peaks_order, k=self.peaks_k
            )
            ohlcv_df = self.add_peaks(
                ohlcv_df, key="RSI", order=self.peaks_order, k=self.peaks_k
            )
            target_symbol = symbol.split("/")[0]
            price = market_data[f"{symbol}_TICKER"]["bid"]

            if self.is_buy_signal(
                    symbol=target_symbol, algorithm=algorithm, data=ohlcv_df
            ):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side="BUY",
                    price=price,
                    percentage_of_portfolio=20,
                    precision=4
                )
            elif self.is_sell_signal(
                    symbol=target_symbol, algorithm=algorithm, data=ohlcv_df
            ):
                algorithm.close_position(
                    symbol=target_symbol
                )

            # Checking manual stop losses
            open_trades = algorithm.get_open_trades(target_symbol)

            for open_trade in open_trades:
                if open_trade.is_manual_stop_loss_trigger(
                        ohlcv_df=raw_df,
                        current_price=market_data[f"{symbol}_TICKER"]["bid"],
                        stop_loss_percentage=6
                ):
                    algorithm.close_trade(open_trade)

            self.add_trace(symbol=symbol, data=ohlcv_df)

    def is_buy_signal(self, symbol, algorithm, data):

        if algorithm.has_open_orders(symbol):
            return False

        if algorithm.has_position(symbol):
            return False

        row = data.iloc[-1]

        if self.is_crossover(data, "+DI", "-DI"):
            match = False
            # Check if there is a bullish divergence between the RSI_lows
            # and the close price lows in the last 2 days
            rsi_window = data.loc[
                         row.name - pd.Timedelta(days=2):row.name, 'RSI_lows'
                         ]
            close_window = data.loc[
                           row.name - pd.Timedelta(days=2):row.name,
                           'Close_lows'
                           ]

            # Go over each row and check if there is a bullish
            # divergence between the RSI and the close price lows
            for rsi_row, close_row in zip(rsi_window, close_window):

                if rsi_row == -1 and close_row == 1:
                    match = True
                    break

            if not match:
                # Check if the RSI had decreased significantly in the last day
                rsi_window = data.loc[
                             row.name - pd.Timedelta(days=1):row.name, 'RSI'
                             ]
                rsi_diff = rsi_window.diff().mean()

                if rsi_diff < -2:
                    return True
            else:
                return True

        return False

    def is_crossover(self, data, key1, key2):
        """
        Check if the given keys have crossed over.
        """
        return data[key1].iloc[-1] > data[key2].iloc[-1] \
            and data[key1].iloc[-2] < data[key2].iloc[-2]

    def is_sell_signal(self, symbol, algorithm, data):
        """
        Creates sell signal. A sell signal is created when the DI+ crosses below
        the DI- or when the ADX is below the threshold or when there
        is a divergence between the close price and the RSI.
        """

        if algorithm.has_open_orders(symbol):
            return False

        if not algorithm.has_position(symbol):
            return False

        row = data.iloc[-1]

        if self.is_crossover(data, "-DI", "+DI"):
            match = False
            # Check if there is a bearish divergence between the RSI_lows
            # and the close price lows in the last 2 days
            rsi_window = data.loc[
                         row.name - pd.Timedelta(days=2):row.name,
                         'RSI_highs'
                         ]
            close_window = data.loc[
                           row.name - pd.Timedelta(days=2):row.name,
                           'Close_highs'
                           ]
            # Go over each row and check if there is a bullish
            # divergence between the RSI and the close price
            for rsi_row, close_row in zip(rsi_window, close_window):

                if rsi_row == 1 and close_row == -1:
                    match = True
                    break

            if not match:
                # Check if the ADX had decreased significantly in the last day
                adx_window = data.loc[
                             row.name - pd.Timedelta(days=1):row.name, 'ADX'
                             ]
                adx_diff = adx_window.diff().mean()

                if adx_diff < -1:
                    return True
            else:
                return True

        return False

    @staticmethod
    def add_peaks(data, key="Close", order=5, k=2):
        """
        Get peaks in for the given key in the data DataFrame.
        Peaks are calculated using the get_higher_high_index,
        get_lower_highs_index, get_lower_lows_index, and get_higher_lows_index
        functions with the given order and K parameters.

        The order parameter determines the number of periods to
        consider when calculating the peaks. If the order is 2, the
        function will consider
        the current and previous periods to determine the peaks.
        if the order is 3, the function will consider the current and
        two previous periods to determine the peaks.
        A period is a datapoint in the data DataFrame.

        The K parameter determines how many consecutive peaks need to be
        higher or lower to be considered a peak.
        """
        vals = data[key].values
        hh_idx = TestStrategy.get_higher_high_index(vals, order, k)
        lh_idx = TestStrategy.get_lower_highs_index(vals, order, k)
        ll_idx = TestStrategy.get_lower_lows_index(vals, order, k)
        hl_idx = TestStrategy.get_higher_lows_index(vals, order, k)

        # Create columns for highs and lows
        data[f'{key}_highs'] = np.nan
        data[f'{key}_lows'] = np.nan

        # Get the datetime values corresponding to these integer positions
        data[f'{key}_highs'] = data[f'{key}_highs'].ffill().fillna(0)
        data[f'{key}_lows'] = data[f'{key}_lows'].ffill().fillna(0)

        if len(hh_idx) != 0:
            hh_datetime_values = data.index[hh_idx]
            data.loc[hh_datetime_values, f'{key}_highs'] = 1

        if len(lh_idx) != 0:
            lh_datetime_values = data.index[lh_idx]
            data.loc[lh_datetime_values, f'{key}_highs'] = -1

        if len(ll_idx) != 0:
            ll_datetime_values = data.index[ll_idx]
            data.loc[ll_datetime_values, f'{key}_lows'] = 1

        if len(hl_idx) != 0:
            hl_datetime_values = data.index[hl_idx]
            data.loc[hl_datetime_values, f'{key}_lows'] = -1

        return data

    @staticmethod
    def add_rsi(data, period=14):
        # Calculate RSI
        rsi_values = tp.rsi(data['Close'].to_numpy(), period=period)

        # Pad NaN values for initial rows with a default value, e.g., 0
        rsi_values = np.concatenate((np.full(period, 0), rsi_values))

        # Assign RSI values to the DataFrame
        data["RSI"] = rsi_values
        return data

    @staticmethod
    def add_ema(data, key="Close", period=100):
        """
        Add an Exponential Moving Average (EMA) to the data DataFrame.
        """
        ema = tp.ema(data[key].to_numpy(), period=period)
        data[f"EMA_{period}"] = ema
        return data

    @staticmethod
    def get_higher_lows(data: np.array, order=5, K=2):
        '''
        Finds consecutive higher lows in price pattern.
        Must not be exceeded within the number of periods indicated by
        the width parameter for the value to be confirmed.
        K determines how many consecutive lows need to be higher.
        '''
        # Get lows
        low_idx = argrelextrema(data, np.less, order=order)[0]
        lows = data[low_idx]
        # Ensure consecutive lows are higher than previous lows
        extrema = []
        ex_deque = deque(maxlen=K)
        for i, idx in enumerate(low_idx):
            if i == 0:
                ex_deque.append(idx)
                continue
            if lows[i] < lows[i - 1]:
                ex_deque.clear()

            ex_deque.append(idx)

            if len(ex_deque) == K:
                extrema.append(ex_deque.copy())

        return extrema

    @staticmethod
    def get_lower_highs(data: np.array, order=5, K=2):
        '''
        Finds consecutive lower highs in price pattern.
        Must not be exceeded within the number of periods
        indicated by the width
        parameter for the value to be confirmed.
        K determines how many consecutive highs need to be lower.
        '''
        # Get highs
        high_idx = argrelextrema(data, np.greater, order=order)[0]
        highs = data[high_idx]
        # Ensure consecutive highs are lower than previous highs
        extrema = []
        ex_deque = deque(maxlen=K)
        for i, idx in enumerate(high_idx):

            if i == 0:
                ex_deque.append(idx)
                continue
            if highs[i] > highs[i - 1]:
                ex_deque.clear()

            ex_deque.append(idx)

            if len(ex_deque) == K:
                extrema.append(ex_deque.copy())

        return extrema

    @staticmethod
    def get_higher_highs(data: np.array, order=5, K=2):
        '''
        Finds consecutive higher highs in price pattern.
        Must not be exceeded within the number of periods indicated
        by the width
        parameter for the value to be confirmed.
        K determines how many consecutive highs need to be higher.
        '''
        # Get highs
        high_idx = argrelextrema(data, np.greater, order=order)[0]
        highs = data[high_idx]
        # Ensure consecutive highs are higher than previous highs
        extrema = []
        ex_deque = deque(maxlen=K)

        for i, idx in enumerate(high_idx):
            if i == 0:
                ex_deque.append(idx)
                continue
            if highs[i] < highs[i - 1]:
                ex_deque.clear()

            ex_deque.append(idx)

            if len(ex_deque) == K:
                extrema.append(ex_deque.copy())

        return extrema

    @staticmethod
    def get_lower_lows(data: np.array, order=5, K=2):
        '''
        Finds consecutive lower lows in price pattern.
        Must not be exceeded within the number of periods indicated by the width
        parameter for the value to be confirmed.

        params:

        order : int, optional
        How many points on each side to use for the comparison
        to consider ``comparator(n, n+x)`` to be True.

        K : int, optional
        How many consecutive lows need to be lower. This means that for
        a given low, the next
        K lows must be lower than the k lows before. So say K=2, then
        the low at index i must be lower than the low at
        index i-2 and i-1. If this
        condition is met, then the low at index i is considered a
        lower low. If the condition is not met, then the low at
        index i is not considered a lower low.
        '''
        # Get lows
        low_idx = argrelextrema(data, np.less, order=order)[0]
        lows = data[low_idx]
        # Ensure consecutive lows are lower than previous lows
        extrema = []
        ex_deque = deque(maxlen=K)

        for i, idx in enumerate(low_idx):

            if i == 0:
                ex_deque.append(idx)
                continue

            if lows[i] > lows[i - 1]:
                ex_deque.clear()

            ex_deque.append(idx)

            if len(ex_deque) == K:
                extrema.append(ex_deque.copy())

        return extrema

    @staticmethod
    def get_higher_high_index(data: np.array, order=5, K=2):
        extrema = TestStrategy.get_higher_highs(data, order, K)
        idx = np.array([i[-1] + order for i in extrema])
        return idx[np.where(idx < len(data))]

    @staticmethod
    def get_lower_highs_index(data: np.array, order=5, K=2):
        extrema = TestStrategy.get_lower_highs(data, order, K)
        idx = np.array([i[-1] + order for i in extrema])
        return idx[np.where(idx < len(data))]

    @staticmethod
    def get_lower_lows_index(data: np.array, order=5, K=2):
        extrema = TestStrategy.get_lower_lows(data, order, K)
        idx = np.array([i[-1] + order for i in extrema])
        return idx[np.where(idx < len(data))]

    @staticmethod
    def get_higher_lows_index(data: np.array, order=5, K=2):
        extrema = TestStrategy.get_higher_lows(data, order, K)
        idx = np.array([i[-1] + order for i in extrema])
        return idx[np.where(idx < len(data))]

    @staticmethod
    def add_adx(data, period=14):
        plus_di, min_di = tp.di(
            high=data["High"].to_numpy(),
            low=data["Low"].to_numpy(),
            close=data["Close"].to_numpy(),
            period=period
        )
        adx = tp.adx(
            high=data["High"].to_numpy(),
            low=data["Low"].to_numpy(),
            close=data["Close"].to_numpy(),
            period=period
        )

        # Pad NaN values for initial rows with a default value, e.g., 0
        plus_di = np.concatenate((np.full(period - 1, 0), plus_di))
        min_di = np.concatenate((np.full(period - 1, 0), min_di))
        adx = np.concatenate((np.full(period + 12, 0), adx))

        # Assign adx values to the DataFrame
        data["+DI"] = plus_di
        data["-DI"] = min_di
        data["ADX"] = adx
        return data

    def is_above(self, data, key1, key2):
        return data[key1].iloc[-1] > data[key2].iloc[-1]

    def is_below(self, data, key1, key2):
        return data[key1].iloc[-1] < data[key2].iloc[-1]


def create_algorithm(
        name,
        rsi_period=14,
        adx_period=14,
        rsi_buy_threshold=50,
        rsi_sell_threshold=50,
        adx_buy_threshold=35,
        adx_sell_threshold=35,
        peaks_order=5,
        peaks_k=2
):
    algorithm = Algorithm(
        name=name,
        strategy=TestStrategy(
            rsi_period=rsi_period,
            adx_period=adx_period,
            rsi_buy_threshold=rsi_buy_threshold,
            rsi_sell_threshold=rsi_sell_threshold,
            adx_buy_threshold=adx_buy_threshold,
            adx_sell_threshold=adx_sell_threshold,
            peaks_order=peaks_order,
            peaks_k=peaks_k
        ),
    )
    return algorithm
