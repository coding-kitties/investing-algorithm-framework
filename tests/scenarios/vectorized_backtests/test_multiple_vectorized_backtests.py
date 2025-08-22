import os
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from typing import Dict, Any, List

from pyindicators import ema, rsi, crossover, crossunder, macd

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, \
    Algorithm, RESOURCE_DIRECTORY, SnapshotInterval




class RSIEMACrossoverStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
        self,
        time_unit: TimeUnit,
        interval: int,
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

        data_sources.append(
            DataSource(
                identifier=f"rsi_data",
                data_type=DataType.OHLCV,
                time_frame=self.rsi_time_frame,
                market=market,
                symbol="BTC/EUR",
                pandas=True
            )
        )
        data_sources.append(
            DataSource(
                identifier=f"ema_data",
                data_type=DataType.OHLCV,
                time_frame=self.ema_time_frame,
                market=market,
                symbol="BTC/EUR",
                pandas=True
            )
        )

        super().__init__(data_sources=data_sources, time_unit=time_unit, interval=interval)

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

    def buy_signal_vectorized(self, data: Dict[str, Any]) -> pd.Series:
        ema_data_identifier = "ema_data"
        rsi_data_identifier = "rsi_data"
        ema_data, rsi_data = self.prepare_indicators(
            data[ema_data_identifier].copy(),
            data[rsi_data_identifier].copy()
        )

        # crossover confirmed
        ema_crossover_confirmed = (
                ema_data[self.ema_crossover_result_column]
                .rolling(window=self.ema_cross_lookback_window)
                .sum() > 0
        )

        # use only RSI column
        rsi_oversold = rsi_data[self.rsi_result_column] \
                       < self.rsi_oversold_threshold

        buy_signal = rsi_oversold & ema_crossover_confirmed
        return buy_signal.fillna(False).astype(bool)

    def sell_signal_vectorized(self, data: Dict[str, Any]) -> pd.Series:
        """
        Generate sell signals based on the moving average crossover.

        Args:
            data (pd.DataFrame): DataFrame containing OHLCV data.

        Returns:
            pd.Series: Series of sell signals (1 for sell, 0 for no action).
        """
        ema_data_identifier = "ema_data"
        rsi_data_identifier = "rsi_data"
        ema_data, rsi_data = self.prepare_indicators(
            data[ema_data_identifier].copy(),
            data[rsi_data_identifier].copy()
        )

        # Confirmed by crossover between short-term EMA and long-term EMA
        # within a given lookback window
        ema_crossunder_confirmed = ema_data[self.ema_crossunder_result_column] \
                                      .rolling(
            window=self.ema_cross_lookback_window).sum() > 0

        # use only RSI column
        rsi_overbought = rsi_data[self.rsi_result_column] \
                       >= self.rsi_overbought_threshold

        # Combine both conditions
        sell_signal = rsi_overbought & ema_crossunder_confirmed
        sell_signal = sell_signal.fillna(False).astype(bool)
        return sell_signal

class Test(TestCase):

    def test_run(self):
        """
        """
        start_time = time.time()
        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        # Resource directory should point to /tests/resources
        # Resource directory is two levels up from the current file
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=400)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        strategies = [
            RSIEMACrossoverStrategy(
                time_unit=TimeUnit.HOUR,
                interval=2,
                market="BITVAVO",
                rsi_time_frame="2h",
                rsi_period=14,
                rsi_overbought_threshold=70,
                rsi_oversold_threshold=30,
                ema_time_frame="2h",
                ema_short_period=50,
                ema_long_period=200,
                ema_cross_lookback_window=10
            ),
            RSIEMACrossoverStrategy(
                time_unit=TimeUnit.HOUR,
                interval=2,
                market="BITVAVO",
                rsi_time_frame="2h",
                rsi_period=14,
                rsi_overbought_threshold=70,
                rsi_oversold_threshold=30,
                ema_time_frame="2h",
                ema_short_period=50,
                ema_long_period=150,
                ema_cross_lookback_window=10
            )
        ]
        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_range=date_range,
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Test completed in {elapsed_time:.2f} seconds")
        self.assertEqual(2, len(backtests))

    def test_run_without_data_sources_initialization(self):
        start_time = time.time()
        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        # Resource directory should point to /tests/resources
        # Resource directory is two levels up from the current file
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=400)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        strategies = [
            RSIEMACrossoverStrategy(
                time_unit=TimeUnit.HOUR,
                interval=2,
                market="BITVAVO",
                rsi_time_frame="2h",
                rsi_period=14,
                rsi_overbought_threshold=70,
                rsi_oversold_threshold=30,
                ema_time_frame="2h",
                ema_short_period=50,
                ema_long_period=200,
                ema_cross_lookback_window=10
            ),
            RSIEMACrossoverStrategy(
                time_unit=TimeUnit.HOUR,
                interval=2,
                market="BITVAVO",
                rsi_time_frame="2h",
                rsi_period=14,
                rsi_overbought_threshold=70,
                rsi_oversold_threshold=30,
                ema_time_frame="2h",
                ema_short_period=50,
                ema_long_period=150,
                ema_cross_lookback_window=10
            )
        ]
        data_sources = []

        for strategy in strategies:
           data_sources.extend(strategy.data_sources)

        app.initialize_data_sources_backtest(
            data_sources=data_sources, backtest_date_range=date_range
        )
        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_range=date_range,
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            skip_data_sources_initialization=True
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Test completed in {elapsed_time:.2f} seconds")
        self.assertEqual(2, len(backtests))
