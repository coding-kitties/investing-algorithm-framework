import os
import time
import shutil
from itertools import product
import pandas as pd
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from typing import Dict, Any

from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    TradeStatus, RESOURCE_DIRECTORY, SnapshotInterval, generate_strategy_id


class RSIEMACrossoverStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
        self,
        algorithm_id,
        symbols,
        position_sizes,
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

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=data_sources,
            time_unit=time_unit,
            interval=interval,
            symbols=symbols,
            position_sizes=position_sizes
        )

        for symbol in self.symbols:
            full_symbol = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_rsi_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_ema_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True
                )
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

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Generate buy signals based on the moving average crossover.

        data (Dict[str, Any]): Dictionary containing all the data for
            the strategy data sources.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are symbols and values
                are pandas Series indicating buy signals (True/False).
        """

        signals = {}
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

            # Combine both conditions
            buy_signal = rsi_oversold & ema_crossover_lookback
            buy_signals = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signals
        return signals

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Generate sell signals based on the moving average crossover.

        Args:
            data (Dict[str, Any]): Dictionary containing all the data for
                the strategy data sources.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are symbols and values
                are pandas Series indicating sell signals (True/False).
        """

        signals = {}
        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self.prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

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
            signals[symbol] = sell_signal
        return signals

class Test(TestCase):

    def test_run_with_backtest_storage_directory(self):
        """
        Test run_vector_backtests with backtest storage directory and verify
        that temporary directories are properly cleaned up.
        """
        param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [70, 80],
            "rsi_oversold_threshold": [30, 20],
            "ema_time_frame": ["2h"],
            "ema_short_period": [100],
            "ema_long_period": [150, 200],
            "ema_cross_lookback_window": [4, 6]
        }

        param_options = param_grid
        param_variations = [
            dict(zip(param_options.keys(), values))
            for values in product(*param_options.values())
        ]
        print(
            f"Total parameter combinations to evaluate: {len(param_variations)}")

        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        # Resource directory should point to /tests/resources
        # Resource directory is two levels up from the current file
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)
        end_date = datetime(2025, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1095)

        # Split into multiple date ranges to test progressive filtering
        mid_date = start_date + timedelta(days=365)
        date_range_1 = BacktestDateRange(
            start_date=start_date, end_date=end_date, name="Period 1"
        )
        date_range_2 = BacktestDateRange(
            start_date=mid_date, end_date=end_date, name="Period 2"
        )

        # Create backtest storage directory
        backtest_storage_dir = os.path.join(
            resource_directory, "backtest_reports_for_testing"
        )

        # Clean up any existing storage directory
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)

        strategies = []
        for param_set in param_variations:
            strategies.append(
                RSIEMACrossoverStrategy(
                    algorithm_id=generate_strategy_id(param_set),
                    time_unit=TimeUnit.HOUR,
                    interval=2,
                    market="BITVAVO",
                    rsi_time_frame=param_set["rsi_time_frame"],
                    rsi_period=param_set["rsi_period"],
                    rsi_overbought_threshold=param_set[
                        "rsi_overbought_threshold"
                    ],
                    rsi_oversold_threshold=param_set[
                        "rsi_oversold_threshold"
                    ],
                    ema_time_frame=param_set["ema_time_frame"],
                    ema_short_period=param_set["ema_short_period"],
                    ema_long_period=param_set["ema_long_period"],
                    ema_cross_lookback_window=param_set[
                        "ema_cross_lookback_window"
                    ],
                    symbols=[
                        "BTC",
                        "ETH"
                    ],
                    position_sizes=[
                        PositionSize(
                            symbol="BTC", percentage_of_portfolio=20.0
                        ),
                        PositionSize(
                            symbol="ETH", percentage_of_portfolio=20.0
                        )
                    ]
                )
            )

        # Create expected temporary directory names
        start_str_1 = date_range_1.start_date.strftime('%Y-%m-%d')
        end_str_1 = date_range_1.end_date.strftime('%Y-%m-%d')
        temp_dir_1 = os.path.join(backtest_storage_dir, f"{start_str_1}_to_{end_str_1}")

        start_str_2 = date_range_2.start_date.strftime('%Y-%m-%d')
        end_str_2 = date_range_2.end_date.strftime('%Y-%m-%d')
        temp_dir_2 = os.path.join(backtest_storage_dir, f"{start_str_2}_to_{end_str_2}")

        start_time = time.time()
        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=backtest_storage_dir,
            use_checkpoints=False,
        )
        end_time = time.time()

        self.assertEqual(len(backtests), 16)
        # Duration must be less than 300 seconds (5 minutes)
        # Each backtest should have atleast 2 backtest runs (one for each date range)
        for backtest in backtests:
            self.assertGreaterEqual(
                len(backtest.get_all_backtest_runs()), 2,
                "Each backtest should have at least 2 backtest runs"
            )

        # Verify that temporary directories were cleaned up
        self.assertFalse(
            os.path.exists(temp_dir_1),
            f"Temporary directory {temp_dir_1} should be cleaned up after backtest execution"
        )
        self.assertFalse(
            os.path.exists(temp_dir_2),
            f"Temporary directory {temp_dir_2} should be cleaned up after backtest execution"
        )

        # Verify that the main storage directory exists and contains final results
        self.assertTrue(
            os.path.exists(backtest_storage_dir),
            f"Main storage directory {backtest_storage_dir} should exist with final results"
        )

        # Check that there are actual backtest files in the storage directory
        storage_contents = os.listdir(backtest_storage_dir) if os.path.exists(backtest_storage_dir) else []
        self.assertGreater(
            len(storage_contents), 0,
            "Storage directory should contain backtest result files"
        )

        # Check that total amount of folders are the same as the total amount of strategies
        self.assertEqual(
            len(storage_contents), len(strategies),
            "Storage directory should contain result files for all strategies"
        )

    def tearDown(self):
        """Clean up test artifacts"""
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        backtest_storage_dir = os.path.join(
            resource_directory, "backtest_reports_for_testing"
        )
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)


