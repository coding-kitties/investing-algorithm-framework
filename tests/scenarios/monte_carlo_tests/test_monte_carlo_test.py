import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest import TestCase

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, \
    RESOURCE_DIRECTORY, DATA_DIRECTORY, PositionSize, Schedule, \
    SignalSide, signal_series_from_column


class RSIEMACrossoverStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(
            symbol="BTC", percentage_of_portfolio=20.0
        )
    ]


    def __init__(
        self,
        algorithm_id: str,
        schedule: Schedule,
        market: str,
        rsi_time_frame: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_time_frame,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window: int = 10
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window
        data_sources = []

        for symbol in self.symbols:
            full_symbol = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_rsi_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    warmup_window=200
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_ema_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    warmup_window=200
                )
            )

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=data_sources,
            schedule=schedule,
        )

        self.buy_signal_dates = {}
        self.sell_signal_dates = {}

        for symbol in self.symbols:
            self.buy_signal_dates[symbol] = []
            self.sell_signal_dates[symbol] = []

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

    def generate_signal_series(self, data: Dict[str, Any]):
        """
        Generate buy/sell signal series based on the RSI + EMA crossover.
        """
        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self.prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # crossover confirmed
            ema_crossover_lookback = ema_data[
                self.ema_crossover_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_oversold = rsi_data[self.rsi_result_column] \
                < self.rsi_oversold_threshold

            buy_signal = rsi_oversold & ema_crossover_lookback
            buy_signal = buy_signal.fillna(False).astype(bool)

            # Get all dates where there is a buy signal
            buy_signal_dates = buy_signal[buy_signal].index.tolist()

            if buy_signal_dates:
                self.buy_signal_dates[symbol] += buy_signal_dates

            # Confirmed by crossover between short-term EMA and long-term EMA
            # within a given lookback window
            ema_crossunder_lookback = ema_data[
                self.ema_crossunder_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_overbought = rsi_data[self.rsi_result_column] \
               >= self.rsi_overbought_threshold

            # Combine both conditions
            sell_signal = rsi_overbought & ema_crossunder_lookback
            sell_signal = sell_signal.fillna(False).astype(bool)

            # Get all dates where there is a sell signal
            sell_signal_dates = sell_signal[sell_signal].index.tolist()

            if sell_signal_dates:
                self.sell_signal_dates[symbol] += sell_signal_dates

            buy_df = pd.DataFrame({"_buy_signal": buy_signal})
            sell_df = pd.DataFrame({"_sell_signal": sell_signal})
            yield signal_series_from_column(
                buy_df, "_buy_signal",
                side=SignalSide.OPEN_LONG, symbol=symbol,
                source="test_fixture",
            )
            yield signal_series_from_column(
                sell_df, "_sell_signal",
                side=SignalSide.CLOSE_LONG, symbol=symbol,
                source="test_fixture",
            )

@unittest.skip("Scenario tests skipped pending optimization — see GitHub issue")
class Test(TestCase):

    def test_run(self):
        """
        """
        start_time = time.time()
        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        # Resource directory should point to /tests/resources
        # Resource directory is two levels up from the current file
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), '..', 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory, DATA_DIRECTORY: "test_data/ohlcv"}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=100)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        strategy = RSIEMACrossoverStrategy(
            algorithm_id="rsi_ema_crossover_strategy",
            schedule=Schedule.every(2, TimeUnit.HOUR),
            market="BITVAVO",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=20,
            ema_long_period=50,
            ema_cross_lookback_window=10
        )
        backtests = app.run_monte_carlo_test(
            initial_amount=1000,
            market="bitvavo",
            trading_symbol="EUR",
            backtest_date_range=date_range,
            strategy=strategy,
            number_of_permutations=5,
            show_progress=False
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
