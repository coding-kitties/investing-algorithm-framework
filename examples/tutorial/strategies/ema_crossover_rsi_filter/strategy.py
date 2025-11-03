
from typing import Dict, Any

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize


class EMACrossoverRSIFFilterStrategy(TradingStrategy):

    def __init__(
        self,
        symbols: list[str],
        trading_symbol: str,
        rsi_timeframe: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_timeframe,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window,
        ema_long_result_column = "ema_long",
        ema_short_result_column = "ema_short",
        ema_crossunder_result_column = "ema_crossunder",
        ema_crossover_result_column = "ema_crossover",
        rsi_result_column = "rsi",
        time_unit: TimeUnit = TimeUnit.HOUR,
        interval: int = 2,
        market: str = "BITVAVO",
        metadata: dict = None
    ):
        self.symbols = symbols
        self.rsi_timeframe = rsi_timeframe
        self.rsi_period = rsi_period
        self.rsi_result_column = rsi_result_column
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_timeframe = ema_timeframe
        self.ema_short_result_column = ema_short_result_column
        self.ema_long_result_column = ema_long_result_column
        self.ema_crossunder_result_column = ema_crossunder_result_column
        self.ema_crossover_result_column = ema_crossover_result_column
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window
        data_sources = []
        position_sizes = []

        for symbol in symbols:
            full_symbol = f"{symbol}/{trading_symbol}"
            data_sources.append(
                DataSource(
                    identifier=f"rsi_data_{symbol}",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_timeframe,
                    market=market,
                    symbol=full_symbol,
                    pandas=True
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"ema_data_{symbol}",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_timeframe,
                    market=market,
                    symbol=full_symbol,
                    pandas=True
                )
            )
            position_sizes.append(
                PositionSize(
                    symbol=symbol,
                    percentage_of_portfolio=1 / len(symbols)
                )
            )

        super().__init__(
            data_sources=data_sources,
            position_sizes=position_sizes,
            time_unit=time_unit,
            interval=interval,
            metadata=metadata
        )

    def prepare_indicators(
        self,
        rsi_data,
        ema_data
    ):
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        # Detect crossover (short EMA crosses above long EMA)
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        # Detect crossunder (short EMA crosses below long EMA)
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )

        return ema_data, rsi_data

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:

        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"
            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )


            # use only RSI column
            rsi_oversold = rsi_data[self.rsi_result_column] \
                        < self.rsi_oversold_threshold

            crossover = ema_data[self.ema_crossover_result_column] \
                .rolling(window=self.ema_cross_lookback_window).sum() > 0
            buy_signal = rsi_oversold & crossover
            buy_signal = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signal

        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Generate sell signals based on the moving average crossover.

        Args:
            data (pd.DataFrame): DataFrame containing OHLCV data.

        Returns:
            pd.Series: Series of sell signals (1 for sell, 0 for no action).
        """
        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"

            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # # use only RSI column
            rsi_overbought = rsi_data[self.rsi_result_column] \
                        >= self.rsi_overbought_threshold

            # Check that within the lookback window there was a crossunder
            crossunder = ema_data[self.ema_crossunder_result_column] \
                .rolling(window=self.ema_cross_lookback_window).sum() > 0

            sell_signal = crossunder & rsi_overbought
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal

        return signals