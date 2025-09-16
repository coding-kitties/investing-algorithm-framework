from typing import Dict, Any

import pandas as pd
from pyindicators import ema, crossunder, crossover

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    DataSource, PositionSize


class CrossOverStrategyV1(TradingStrategy):
    """
    A simple trading strategy that uses EMA crossovers to generate buy and
    sell signals. The strategy uses a 50-period EMA and a 100-period EMA
    to detect golden and death crosses. It also uses a 200-period EMA to
    determine the overall trend direction. The strategy trades BTC/EUR
    on a 2-hour timeframe. The strategy is designed to be used with the
    Investing Algorithm Framework and uses the PyIndicators library
    to calculate the EMAs and crossover signals.

    The strategy uses a trailing stop loss and take profit to manage
    risk. The stop loss is set to 5% below the entry price and the
    take profit is set to 10% above the entry price. The stop loss and
    take profit are both trailing, meaning that they will move up
    with the price when the price goes up.
    """
    time_unit = TimeUnit.HOUR
    interval = 2
    fast = 50
    slow = 100
    trend = 200
    stop_loss_percentage = 2
    stop_loss_sell_size = 50
    take_profit_percentage = 8
    take_profit_sell_size = 50
    position_sizes = [
        PositionSize(
            symbol="BTC", percentage_of_portfolio=20.0
        )
    ]

    def __init__(
        self,
        symbols = ["BTC"],
        ema_time_frame="2h",
        ema_crossover_result_column="ema_crossover",
        ema_crossunder_result_column="ema_crossunder",
        crossover_lookback_window=4,
    ):
        self.ema_time_frame = ema_time_frame
        self.ema_cross_lookback_window = crossover_lookback_window
        self.ema_crossover_result_column = ema_crossover_result_column
        self.ema_crossunder_result_column = ema_crossunder_result_column
        super().__init__(symbols=symbols)

        for symbol in symbols:
            full_symbol = f"{symbol}/EUR"
            self.data_sources.append(
                DataSource(
                    market="BITVAVO",
                    symbol=full_symbol,
                    data_type="ohlcv",
                    time_frame=self.ema_time_frame,
                    window_size=self.trend,
                    identifier=f"{full_symbol}-ohlcv-2h",
                    pandas=True
                )
            )

    def _prepare_indicators(self, ema_data):
        ema_data = ema(
            ema_data,
            period=self.fast,
            source_column="Close",
            result_column=f"ema_{self.fast}"
        )
        ema_data = ema(
            ema_data,
            period=self.slow,
            source_column="Close",
            result_column=f"ema_{self.slow}"
        )
        ema_data = crossunder(
            ema_data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            result_column=self.ema_crossunder_result_column
        )
        ema_data = crossover(
            ema_data,
            first_column=f"ema_{self.fast}",
            second_column=f"ema_{self.slow}",
            result_column=self.ema_crossover_result_column
        )
        return ema_data

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        signals = {}

        for symbol in self.symbols:
            symbol_pair = f"{symbol}/EUR"
            ema_data = data[f"{symbol_pair}-ohlcv-2h"]
            ema_data = self._prepare_indicators(ema_data)

            # crossover confirmed
            ema_crossover_lookback = ema_data[
                self.ema_crossover_result_column
            ].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            buy_signal = ema_crossover_lookback
            buy_signals = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signals
        return signals

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        signals = {}

        for symbol in self.symbols:
            symbol_pair = f"{symbol}/EUR"
            ema_data = data[f"{symbol_pair}-ohlcv-2h"].copy()
            ema_data = self._prepare_indicators(ema_data)

            # crossover confirmed
            ema_crossunder_lookback = ema_data[
                self.ema_crossunder_result_column
            ].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            sell_signal = ema_crossunder_lookback
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal
        return signals
