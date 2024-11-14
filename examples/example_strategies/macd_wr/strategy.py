from investing_algorithm_framework import CCXTOHLCVMarketDataSource, \
    TradingStrategy, TimeUnit, CCXTTickerMarketDataSource, Algorithm
from investing_algorithm_framework.indicators import get_peaks
from typing import Tuple
from datetime import datetime
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


class Strategy(TradingStrategy):
    """
    Implementation of TradingStrategy that uses RSI and ADX metrics.
    The strategy is parameterized in order to do experiments with it.
    This allows you to test the strategy with different configurations.

    STRATEGY OUTLINE:

    Uptrend determination:
        - The ema_50 is above the ema_100

    Downtrend determination:
        - The ema_50 is below the ema_100

    Buy Signal on uptrend:
        - The +DI crosses above the -DI + one of the following
        conditions is met:
            - If in the last 2 days there is a bullish divergence
                (higher low and lower low) between the RSI_lows and
                the close price lows
            - If the RSI has decreased significantly in the last day
                (RSI_diff < -2)

    Buy Signal on downtrend:
        - The -DI crosses above the +DI + one of the following conditions
        is met:
            - If in the last 2 days there is a bearish divergence
                (higher high and lower high) between the RSI_highs and
                the close price highs
            - If the ADX has decreased significantly in the last day
                (ADX_diff < -1)

    Sell Signal on uptrend:
        - The -DI crosses above the +DI + one of the following conditions
        is met:
            - If in the last 2 days there is a bearish divergence
                (higher high and lower high) between the RSI_highs and
                the close price highs
            - If the ADX has decreased significantly in the last day
                (ADX_diff < -1)

    Sell Signal on downtrend:
        - The -DI crosses above the +DI + one of the following conditions
        is met:
            - If in the last 7 days there is a bearish divergence
                (higher high and lower high) between the RSI_highs and
                the close price highs
            - If the ADX has decreased significantly in the last day
                (ADX_diff < -1)
    Additional Conditions:
        if the stop loss is triggered, the trade is closed.
        Stop loss is set at 6%.

    Args:

    """
    market_data_sources = [ohlcv_2h_data_source, ticker_data_source]
    symbols = ["BTC/EUR"]
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(self):
        super(Strategy, self).__init__()


    def apply_strategy(self, algorithm, market_data):
        pass
    
    @staticmethod
    def add_willr(data, period=14):
        # Calculate williams%R
        willr_values = tp.willr(data["High"].to_numpy(), data["Low"].to_numpy(), data["Close"].to_numpy(), period=period)

        # Pad NaN values for initial rows with a default value, e.g., 0
        willr_values = np.concatenate((np.full(period - 1, 0), willr_values))

        # Assign RSI values to the DataFrame
        data["WILLR"] = willr_values
        return data

    @staticmethod
    def add_macd(data, short_period=12, long_period=26, signal_period=9):
        """
        Calculates macd, macd_signal, macd_histogram
        """
        # Calculate MACD 
        macd, macd_signal, macd_histogram  = tp.macd(real=data["Close"].to_numpy(), short_period=short_period, long_period=long_period, signal_period=signal_period)

        # Pad NaN values for initial rows with a default value, e.g., 0
        macd = np.concatenate((np.full(long_period - 1, 0), macd))
        macd_signal = np.concatenate((np.full(long_period - 1, 0), macd_signal))
        macd_histogram = np.concatenate((np.full(long_period - 1, 0), macd_histogram))


        # Assign RSI values to the DataFrame
        data["MACD"] = macd
        data["MACD_SIGNAL"] = macd_signal
        data["MACD_HISTOGRAM"] = macd_histogram
        return data

    @staticmethod
    def is_crossover(data, key1, key2):
        """
        Check if the given keys have crossed over.
        """

        if len(data) < 2:
            return False
    
        return data[key1].iloc[-1] >= data[key2].iloc[-1] \
            and data[key1].iloc[-2] <= data[key2].iloc[-2]    

    @staticmethod
    def is_crossunder(data, key1, key2):
        """
        Check if the given keys have crossed under.
        """
        if len(data) < 2:
            return False
        
        return data[key1].iloc[-1] <= data[key2].iloc[-1] \
            and data[key1].iloc[-2] >= data[key2].iloc[-2] 
    
    @staticmethod
    def has_crossed_upward(data, key, threshold):
        """
        Check if for a given key in a data frame the values have crossed the given threshold upwards. 
        Where there must be a (x_i) < threshold and (x_i + n) > threshold.
        """
        # Ensure the key exists in the DataFrame
        if key not in data.columns:
            raise KeyError(f"Key '{key}' not found in DataFrame")

        # Identify where the values are below and above the threshold
        below_threshold = data[key] < threshold
        above_threshold = data[key] > threshold

        # Check if there is any point where a value is below the threshold followed by a value above the threshold
        crossed_upward = (below_threshold.shift(1, fill_value=False) & above_threshold).any()
        return crossed_upward


    @staticmethod
    def detect_strong_decreases(df: pd.DataFrame, column: str, decrease_threshold: float):
        """
        Detect strong decreases in a specified column of a DataFrame.
        This function finds sequences where the values decrease by at least decrease_threshold.
        
        Parameters:
        - df: pd.DataFrame - The input pandas DataFrame.
        - column: str - The column key to check for decreases.
        - decrease_threshold: float - The threshold value for the total decrease.
        
        Returns:
        - Boolean indicating there was a decrease in the 
        """
        decreases = []
        start_index = None

        for i in range(1, len(df)):
            if start_index is None:
                # Look for the start of a decrease
                if df.iloc[i-1][column] - df.iloc[i][column] >= decrease_threshold:
                    start_index = i - 1
            else:
                # Look for the end of a decrease
                if df.iloc[i][column] <= df.iloc[start_index][column] - decrease_threshold:
                    decreases.append((start_index, i))
                    start_index = None
                elif df.iloc[i][column] > df.iloc[start_index][column]:
                    # Reset if the series goes back above the start_index value
                    start_index = None

        return decreases
    
    @staticmethod
    def calculate_slope(points: Tuple[Tuple[float, float], Tuple[float, float]]):
        """
        Calculate the slope between two peaks in a 1D numpy array.
    
        Parameters:
            points (Tuple(float, float)): A tuple containing the x and y values of the two peaks.
    
        Returns:
            slope (float): The slope between the first two identified peaks.       
        """
        # Calculate the slope between the two points
        x1, y1 = points[0]
        x2, y2 = points[1]
        delta_v = x2 - x1
        delta_t = y2 - y1

        if delta_t == 0:
            raise ValueError("Delta time (delta_t) is zero, can't divide by zero")
    
        slope = delta_v / delta_t
        return slope
