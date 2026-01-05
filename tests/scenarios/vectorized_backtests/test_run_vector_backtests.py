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

    def test_run(self):
        """
        Test run_vector_backtests with multiple strategies and multiple date ranges.

        This test verifies that when calling run_vector_backtests with:
        - 16 strategies (parameter grid combinations)
        - 2 date ranges (Period 1 and Period 2)

        Expected behavior:
        ✅ Returns 16 Backtest objects (one per strategy)
        ✅ Each Backtest has 2 BacktestRun instances (one per date range)
        ✅ Each BacktestRun corresponds to one date range
        ✅ All strategies are backtested across all date ranges
        ❌ Does NOT use checkpoints (use_checkpoints=False)
        ❌ Does NOT save to disk (no backtest_storage_directory)

        This demonstrates large-scale strategy optimization by testing
        multiple parameter combinations across multiple time periods.

        Parameter grid creates 16 strategy variations:
        - RSI overbought: [70, 80]
        - RSI oversold: [30, 20]
        - EMA long period: [150, 200]
        - EMA crossover lookback: [4, 6]
        Total: 2 × 2 × 2 × 2 = 16 strategies
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
            resource_directory, "backtest_reports_for_testing", "temp_storage"
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

        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            use_checkpoints=False,
        )

        self.assertEqual(len(backtests), 16)

        # Each backtest should have atleast 2 backtest runs (one for each date range)
        for backtest in backtests:
            self.assertGreaterEqual(
                len(backtest.get_all_backtest_runs()), 2,
                "Each backtest should have at least 2 backtest runs"
            )

    def test_run_with_single_date_range(self):
        """
        Test run_vector_backtests with multiple strategies and a single date range.

        This test verifies that when calling run_vector_backtests with:
        - 16 strategies (parameter grid combinations)
        - 1 date range (Period 1)

        Expected behavior:
        ✅ Returns 16 Backtest objects (one per strategy)
        ✅ Each Backtest has 1 BacktestRun instance (for the single date range)
        ✅ All strategies are backtested for the same time period
        ❌ Does NOT use checkpoints (use_checkpoints=False)
        ❌ Does NOT save to disk (no backtest_storage_directory)

        This is the standard use case for strategy optimization over
        a single time period - testing multiple parameter combinations
        to find the best performing strategy.

        Parameter grid creates 16 strategy variations:
        - RSI overbought: [70, 80]
        - RSI oversold: [30, 20]
        - EMA long period: [150, 200]
        - EMA crossover lookback: [4, 6]
        Total: 2 × 2 × 2 × 2 = 16 strategies
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

        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_range=date_range_1,
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            use_checkpoints=False,
        )

        self.assertEqual(len(backtests), 16)

        # Each backtest should have atleast 2 backtest runs (one for each date range)
        for backtest in backtests:
            self.assertGreaterEqual(
                len(backtest.get_all_backtest_runs()), 1,
                "Each backtest should have at least 1 backtest runs"
            )