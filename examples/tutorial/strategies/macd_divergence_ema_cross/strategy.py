from typing import List, Dict, Any
from unittest import signals
import pandas as pd
from investing_algorithm_framework import TradingStrategy, DataSource, DataType, TimeFrame, PositionSize
from pyindicators import macd, ema, detect_peaks, crossover, bullish_divergence_multi_dataframe, bearish_divergence_multi_dataframe,  crossunder
import pandas as pd



class MACDDivergenceEMACrossFilterStrategy(TradingStrategy):
    """
    Implementation of a trading strategy that uses MACD divergence and
    ema crossover filter for trading decisions.

    From the strategy description from the notes:

        Example Logic (Bullish)
            1. MACD shows bullish divergence:
                - MACD makes a higher low.
                - Price makes a lower low.
            2. Confirmed by crossover between short-term EMA and long-term EMA within a given lookback window.
            3. Enter long position.

        Example Logic (Bearish
            1. MACD shows bearish divergence:
                - Price makes a higher high.
                - MACD makes a lower high.
            2. Confirmed by crossunder between short-term EMA and long-term EMA within a given lookback window.
            3. Enter short position.

    For more details, refer to the notes at notes.md
    """
    def __init__(
        self,
        time_unit,
        interval,
        market,
        symbols: List[str],
        close_timeframe: str,
        macd_timeframe: str,
        macd_short_period,
        macd_long_period,
        macd_signal_period,
        ema_timeframe: str,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window,
        number_of_neighbors_to_compare,
        min_consecutive,
        divergence_lookback_window_size,
        macd_result_column='macd',
        macd_signal_result_column="macd_signal",
        macd_histogram_result_column="macd_histogram",
        ema_long_result_column="ema_long",
        ema_short_result_column="ema_short",
        ema_crossover_result_column="ema_crossover",
        ema_crossunder_result_column="ema_crossunder",
        bearish_divergence_result_column="bearish_divergence",
        bullish_divergence_result_column="bullish_divergence",
        ohlcv_window_size=200,
        metadata=None
    ):
        self.market = market
        self.time_unit = time_unit
        self.interval = interval
        self.close_timeframe = TimeFrame.from_value(close_timeframe)
        self.macd_timeframe = TimeFrame.from_value(macd_timeframe)
        self.ema_timeframe = TimeFrame.from_value(ema_timeframe)
        self.macd_short_period = macd_short_period
        self.macd_long_period = macd_long_period
        self.macd_signal_period = macd_signal_period
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window
        self.number_of_neighbors_to_compare = number_of_neighbors_to_compare
        self.min_consecutive = min_consecutive
        self.divergence_lookback_window_size = divergence_lookback_window_size
        self.symbols = symbols
        self.macd_result_column = macd_result_column
        self.macd_signal_result_column = macd_signal_result_column
        self.macd_histogram_result_column = macd_histogram_result_column
        self.ema_long_result_column = ema_long_result_column
        self.ema_short_result_column = ema_short_result_column
        self.bearish_divergence_result_column = \
            bearish_divergence_result_column
        self.bullish_divergence_result_column = \
            bullish_divergence_result_column
        self.ema_crossover_result_column = ema_crossover_result_column
        self.ema_crossunder_result_column = ema_crossunder_result_column
        data_sources = []
        position_sizes = []

        # initialize the data sources
        for symbol in self.symbols:
            symbol_pair = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    data_type=DataType.OHLCV,
                    window_size=ohlcv_window_size,
                    symbol=symbol_pair,
                    market=self.market,
                    time_frame=self.macd_timeframe,
                    identifier=f"macd_{symbol}_{self.macd_timeframe.value}_OHLCV",
                    pandas=True
                )
            )
            data_sources.append(
                DataSource(
                    data_type=DataType.OHLCV,
                    window_size=ohlcv_window_size,
                    symbol=symbol_pair,
                    market=self.market,
                    time_frame=self.ema_timeframe,
                    identifier=f"ema_{symbol}_{self.ema_timeframe.value}_OHLCV",
                    pandas=True
                )
            )
            data_sources.append(
                DataSource(
                    data_type=DataType.OHLCV,
                    window_size=ohlcv_window_size,
                    symbol=symbol_pair,
                    market=self.market,
                    time_frame=self.close_timeframe,
                    identifier=f"close_{symbol}_{self.close_timeframe.value}_OHLCV",
                    pandas=True
                )
            )
            position_sizes.append(
                PositionSize(
                    symbol=symbol,
                    percentage_of_portfolio=20,
                )
            )

        super().__init__(
            data_sources=data_sources,
            metadata=metadata,
            position_sizes=position_sizes,
        )

    def _prepare_indicators(
        self,
        macd_data,
        close_data,
        ema_data,
        divergence_data,
    ):
        """
        Helper function to prepare all indicators for the strategy
        """
        macd_data = macd(
            macd_data,
            source_column="Close",
            short_period=self.macd_short_period,
            long_period=self.macd_long_period,
            signal_period=self.macd_signal_period,
            macd_column=self.macd_result_column,
            histogram_column=self.macd_histogram_result_column,
            signal_column=self.macd_signal_result_column
        )
        macd_data = detect_peaks(
            macd_data,
            source_column=self.macd_result_column,
            number_of_neighbors_to_compare=self.number_of_neighbors_to_compare,
            min_consecutive=self.min_consecutive,
        )
        close_data = detect_peaks(
            close_data,
            source_column="Close",
            number_of_neighbors_to_compare=self.number_of_neighbors_to_compare,
            min_consecutive=self.min_consecutive,
        )
        divergence_data = bearish_divergence_multi_dataframe(
            first_df=macd_data,
            second_df=close_data,
            result_df=divergence_data,
            first_column=self.macd_result_column,
            second_column="Close",
            window_size=self.divergence_lookback_window_size,
            result_column=self.bearish_divergence_result_column
        )
        divergence_data = bullish_divergence_multi_dataframe(
            first_df=macd_data,
            second_df=close_data,
            result_df=divergence_data,
            first_column=self.macd_result_column,
            second_column="Close",
            window_size=self.divergence_lookback_window_size,
            result_column=self.bullish_divergence_result_column
        )
        ema_data = ema(
            ema_data,
            source_column="Close",
            period=self.ema_short_period,
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            source_column="Close",
            period=self.ema_long_period,
            result_column=self.ema_long_result_column
        )
        ema_data = crossover(
            data=ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        ema_data = crossunder(
            data=ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        return macd_data, close_data, ema_data, divergence_data

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Vectorized buy signal detection.

        Buy signal is generated when:
        1. MACD shows bullish divergence
            - MACD makes a higher low.
            - Price makes a lower low.
        2. Confirmed by crossover between short-term EMA and long-term EMA within a given lookback window.
        3. Enter long position.
        """
        signals = {}

        for symbol in self.symbols:
            macd_data_identifier = \
                f"macd_{symbol}_{self.macd_timeframe.value}_OHLCV"
            ema_data_identifier = \
                f"ema_{symbol}_{self.ema_timeframe.value}_OHLCV"
            close_data_identifier = \
                f"close_{symbol}_{self.close_timeframe.value}_OHLCV"

            macd_data = data[macd_data_identifier].copy()
            ema_data = data[ema_data_identifier].copy()
            close_data = data[close_data_identifier].copy()

            # Pick the more granular data as base for divergence data
            divergence_data = (
                close_data.copy()
                if self.close_timeframe < self.macd_timeframe
                else macd_data.copy()
            )

            _, _, ema_data, divergence_data = \
                self._prepare_indicators(
                    macd_data=macd_data,
                    ema_data=ema_data,
                    close_data=close_data,
                    divergence_data=divergence_data,
                )

            # Boolean series for bullish divergence
            bullish_div = divergence_data[self.bullish_divergence_result_column]\
                .fillna(False).astype(bool)

            # Confirmed by crossover between short-term EMA and long-term EMA
            # within a given lookback window
            ema_crossover_confirmed = ema_data[self.ema_crossover_result_column] \
                .rolling(window=self.ema_cross_lookback_window).sum() > 0

            # Combine both conditions
            buy_signal = bullish_div & ema_crossover_confirmed
            buy_signal = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signal

        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Vectorized sell signal detection.

        Sell signal is generated when:
        1. MACD shows bearish divergence
            - Price makes a higher high.
            - MACD makes a lower high.
        2. Confirmed by crossunder between short-term EMA and long-term EMA within a given lookback window.
        3. Enter short position.
        """
        signals = {}

        for symbol in self.symbols:
            macd_data_identifier = f"macd_{symbol}_{self.macd_timeframe.value}_OHLCV"
            ema_data_identifier = f"ema_{symbol}_{self.ema_timeframe.value}_OHLCV"
            close_data_identifier = f"close_{symbol}_{self.close_timeframe.value}_OHLCV"

            macd_data = data[macd_data_identifier].copy()
            ema_data = data[ema_data_identifier].copy()
            close_data = data[close_data_identifier].copy()

            # Pick the more granular data as base for divergence data
            divergence_data = (
                close_data.copy()
                if self.close_timeframe < self.macd_timeframe
                else macd_data.copy()
            )

            _, _, ema_data, divergence_data = \
                self._prepare_indicators(
                    macd_data=macd_data,
                    ema_data=ema_data,
                    close_data=close_data,
                    divergence_data=divergence_data
                )

            # Boolean series for bearish divergence
            bearish_divergence = divergence_data[self.bearish_divergence_result_column]\
                .fillna(False).astype(bool)

            # Confirmed by crossunder between short-term EMA and long-term EMA
            # within a given lookback window
            ema_crossunder_confirmed = ema_data[self.ema_crossunder_result_column] \
                .rolling(window=self.ema_cross_lookback_window).sum() > 0

            # Combine both conditions
            sell_signal = bearish_divergence & ema_crossunder_confirmed
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal

        return signals
