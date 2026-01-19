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
    RESOURCE_DIRECTORY, SnapshotInterval, generate_algorithm_id


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

        # Create data sources BEFORE calling super().__init__()
        data_sources = []
        for symbol in symbols:
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

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=data_sources,
            time_unit=time_unit,
            interval=interval,
            symbols=symbols,
            position_sizes=position_sizes
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
        Test run_vector_backtest (singular strategy) with backtest storage directory.

        This test verifies run_vector_backtest with:
        - 1 strategy (single RSIEMACrossoverStrategy)
        - 2 date ranges (Period 1: full 3 years, Period 2: last 2 years)
        - backtest_storage_directory provided
        - use_checkpoints=False

        Expected behavior:
        ✅ Returns 1 Backtest object for the strategy
        ✅ The Backtest has 2 BacktestRun instances (one per date range)
        ✅ The Backtest has 2 BacktestMetrics (one per run)
        ✅ Backtests are saved to disk in the storage directory
        ✅ Checkpoint files are CREATED (for future use)
        ❌ Checkpoint files are NOT USED/READ during execution

        Why create checkpoints even when use_checkpoints=False?
        - Builds checkpoint infrastructure progressively
        - Future runs with use_checkpoints=True can skip completed work
        - No performance penalty - checkpoints saved alongside backtests

        Storage structure:
        backtest_storage_dir/
        ├── checkpoints.json  (created for future use)
        └── {algorithm_id}/
            ├── algorithm_id.json
            └── runs/
                ├── {date_range_1_start}_{date_range_1_end}/
                └── {date_range_2_start}_{date_range_2_end}/
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
            resource_directory, "backtest_reports_for_testing", "temp_storage"
        )

        # Clean up any existing storage directory
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)

        param_set = {
            "rsi_time_frame": "2h",
            "rsi_period": 14,
            "rsi_overbought_threshold": 70,
            "rsi_oversold_threshold": 30,
            "ema_time_frame": "2h",
            "ema_short_period": 100,
            "ema_long_period": 150,
            "ema_cross_lookback_window": 4
        }
        strategy = RSIEMACrossoverStrategy(
            algorithm_id=generate_algorithm_id(params=param_set),
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

        backtest = app.run_vector_backtest(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategy=strategy,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=backtest_storage_dir,
            use_checkpoints=False,
            show_progress=True
        )

        self.assertEqual(len(backtest.get_all_backtest_runs()), 2)
        self.assertEqual(len(backtest.get_all_backtest_metrics()), 2)

        # Check that backtest storage directory was created
        self.assertTrue(os.path.exists(backtest_storage_dir))
        # Check that backtest results were saved in the directory
        saved_backtest_dirs = os.listdir(backtest_storage_dir)
        self.assertGreaterEqual(len(saved_backtest_dirs), 1)

        # Check if checkpoint files were created
        checkpoint_file = os.path.join(backtest_storage_dir, "checkpoints.json")
        self.assertTrue(os.path.exists(checkpoint_file))

    def test_run_backtests_with_storage_directory(self):
        """
        Test run_vector_backtests with use_checkpoints=True and
        multiple backtest date ranges, applying progressive filtering to
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
        strategies = []
        for param_set in param_variations:
            strategies.append(
                RSIEMACrossoverStrategy(
                    algorithm_id=generate_algorithm_id(params=param_set),
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

        self.assertEqual(len(strategies), 16)

        # Create backtest storage directory
        backtest_storage_dir = os.path.join(
            resource_directory, "backtest_reports_for_testing", "temp_storage"
        )

        # Clean up any existing storage directory
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)


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
            use_checkpoints=True,
            show_progress=True,
            n_workers=4
        )
        end_time = time.time()
        duration = end_time - start_time

        # There should be 16 backtests with at least one closed trade
        self.assertEqual(
            len(backtests), 16,"There should be 16 backtests returned"
        )

        # Each backtest should have atleast 2 backtest runs (one for each date range)
        for backtest in backtests:
            self.assertGreaterEqual(
                len(backtest.get_all_backtest_runs()), 2,
                "Each backtest should have at least 2 backtest runs"
            )

        # Should have fewer backtests than strategies if filter worked
        self.assertLessEqual(len(backtests), len(strategies))

        # Check if checkpoint files were created
        checkpoint_file = os.path.join(backtest_storage_dir, "checkpoints.json")
        self.assertTrue(os.path.exists(checkpoint_file))

    def tearDown(self):
        # Clean up the backtest storage directory after test
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        backtest_storage_dir = os.path.join(
            resource_directory, "backtest_reports_for_testing", "temp_storage"
        )
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)

    def test_preexisting_backtests_not_included_in_new_run(self):
        """
        Test that pre-existing backtests in storage directory are NOT included
        when running a new batch of strategies.

        This test verifies that when a storage directory already contains
        backtests from a previous run, a new run with different strategies:
        - Only returns backtests for the current strategies
        - Does NOT include backtests from the previous run in results
        - Does NOT apply final_filter_function to pre-existing backtests

        Scenario:
        1. Run backtests for strategies A, B, C -> saves to storage
        2. Run backtests for strategies D, E -> should NOT include A, B, C

        This prevents accidentally mixing results from different optimization
        runs that happen to share the same storage directory.
        """
        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory}

        end_date = datetime(2025, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1095)
        mid_date = start_date + timedelta(days=365)

        date_range_1 = BacktestDateRange(
            start_date=start_date, end_date=end_date, name="Period 1"
        )
        date_range_2 = BacktestDateRange(
            start_date=mid_date, end_date=end_date, name="Period 2"
        )

        # Create backtest storage directory
        backtest_storage_dir = os.path.join(
            resource_directory, "backtest_reports_for_testing", "temp_preexisting_storage"
        )

        # Clean up any existing storage directory
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)

        # ===== FIRST RUN: Run backtests for first set of strategies =====
        app1 = create_app(name="FirstRun", config=config)
        app1.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)

        # Create first set of strategies (4 strategies)
        first_param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [70],
            "rsi_oversold_threshold": [30],
            "ema_time_frame": ["2h"],
            "ema_short_period": [100],
            "ema_long_period": [150, 200],  # 2 variations
            "ema_cross_lookback_window": [4, 6]  # 2 variations = 4 total
        }
        first_variations = [
            dict(zip(first_param_grid.keys(), values))
            for values in product(*first_param_grid.values())
        ]

        first_strategies = []
        for param_set in first_variations:
            first_strategies.append(
                RSIEMACrossoverStrategy(
                    algorithm_id=generate_algorithm_id(params=param_set),
                    time_unit=TimeUnit.HOUR,
                    interval=2,
                    market="BITVAVO",
                    rsi_time_frame=param_set["rsi_time_frame"],
                    rsi_period=param_set["rsi_period"],
                    rsi_overbought_threshold=param_set["rsi_overbought_threshold"],
                    rsi_oversold_threshold=param_set["rsi_oversold_threshold"],
                    ema_time_frame=param_set["ema_time_frame"],
                    ema_short_period=param_set["ema_short_period"],
                    ema_long_period=param_set["ema_long_period"],
                    ema_cross_lookback_window=param_set["ema_cross_lookback_window"],
                    symbols=["BTC", "ETH"],
                    position_sizes=[
                        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
                        PositionSize(symbol="ETH", percentage_of_portfolio=20.0)
                    ]
                )
            )

        self.assertEqual(len(first_strategies), 4)
        first_algorithm_ids = set(s.algorithm_id for s in first_strategies)

        # Run first batch
        first_backtests = app1.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=first_strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=backtest_storage_dir,
            use_checkpoints=False,
            show_progress=True
        )

        # Verify first run results
        self.assertEqual(len(first_backtests), 4)
        first_result_ids = set(b.algorithm_id for b in first_backtests)
        self.assertEqual(first_result_ids, first_algorithm_ids)

        # Verify backtests were saved to storage
        saved_dirs_after_first = set(
            d for d in os.listdir(backtest_storage_dir)
            if os.path.isdir(os.path.join(backtest_storage_dir, d))
        )
        self.assertEqual(len(saved_dirs_after_first), 4)

        # ===== SECOND RUN: Run backtests for DIFFERENT set of strategies =====
        app2 = create_app(name="SecondRun", config=config)
        app2.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)

        # Create second set of strategies (different parameters = different algorithm_ids)
        second_param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [80],  # Different from first run
            "rsi_oversold_threshold": [20],    # Different from first run
            "ema_time_frame": ["2h"],
            "ema_short_period": [100],
            "ema_long_period": [150, 200],  # 2 variations
            "ema_cross_lookback_window": [4, 6]  # 2 variations = 4 total
        }
        second_variations = [
            dict(zip(second_param_grid.keys(), values))
            for values in product(*second_param_grid.values())
        ]

        second_strategies = []
        for param_set in second_variations:
            second_strategies.append(
                RSIEMACrossoverStrategy(
                    algorithm_id=generate_algorithm_id(params=param_set),
                    time_unit=TimeUnit.HOUR,
                    interval=2,
                    market="BITVAVO",
                    rsi_time_frame=param_set["rsi_time_frame"],
                    rsi_period=param_set["rsi_period"],
                    rsi_overbought_threshold=param_set["rsi_overbought_threshold"],
                    rsi_oversold_threshold=param_set["rsi_oversold_threshold"],
                    ema_time_frame=param_set["ema_time_frame"],
                    ema_short_period=param_set["ema_short_period"],
                    ema_long_period=param_set["ema_long_period"],
                    ema_cross_lookback_window=param_set["ema_cross_lookback_window"],
                    symbols=["BTC", "ETH"],
                    position_sizes=[
                        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
                        PositionSize(symbol="ETH", percentage_of_portfolio=20.0)
                    ]
                )
            )

        self.assertEqual(len(second_strategies), 4)
        second_algorithm_ids = set(s.algorithm_id for s in second_strategies)

        # Ensure the two sets of strategies are completely different
        self.assertEqual(
            len(first_algorithm_ids.intersection(second_algorithm_ids)), 0,
            "First and second strategy sets should have different algorithm_ids"
        )

        # Run second batch with the same storage directory
        second_backtests = app2.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=second_strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=backtest_storage_dir,
            use_checkpoints=False,
            show_progress=True
        )

        # ===== VERIFICATION =====
        # The second run should ONLY return backtests for the second strategies
        # It should NOT include backtests from the first run
        self.assertEqual(
            len(second_backtests), 4,
            "Second run should return exactly 4 backtests (one per second strategy)"
        )

        second_result_ids = set(b.algorithm_id for b in second_backtests)
        self.assertEqual(
            second_result_ids, second_algorithm_ids,
            "Second run results should only contain second strategies"
        )

        # Verify NO first strategy backtests are in second results
        for backtest in second_backtests:
            self.assertNotIn(
                backtest.algorithm_id, first_algorithm_ids,
                f"Backtest {backtest.algorithm_id} from first run should NOT "
                "be in second run results"
            )

        # Storage should now contain 8 backtests total (4 from each run)
        saved_dirs_after_second = set(
            d for d in os.listdir(backtest_storage_dir)
            if os.path.isdir(os.path.join(backtest_storage_dir, d))
        )
        self.assertEqual(
            len(saved_dirs_after_second), 8,
            "Storage should contain 8 backtest directories (4 from each run)"
        )

        # Clean up
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)

    def test_preexisting_backtests_not_included_with_final_filter(self):
        """
        Test that pre-existing backtests are NOT included when using
        final_filter_function.

        This test verifies that when a final_filter_function is applied,
        it only operates on backtests from the current run, NOT on
        pre-existing backtests from the storage directory.

        Scenario:
        1. Run backtests for strategies A, B -> saves to storage
        2. Run backtests for strategies C, D with final_filter
        3. Final filter should ONLY see C, D - NOT A, B

        This is important because:
        - Final filter might rank/select top N strategies
        - Including pre-existing backtests could corrupt rankings
        - Different runs may have different selection criteria
        """
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory}

        end_date = datetime(2025, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1095)
        mid_date = start_date + timedelta(days=365)

        date_range_1 = BacktestDateRange(
            start_date=start_date, end_date=end_date, name="Period 1"
        )
        date_range_2 = BacktestDateRange(
            start_date=mid_date, end_date=end_date, name="Period 2"
        )

        backtest_storage_dir = os.path.join(
            resource_directory, "backtest_reports_for_testing", "temp_filter_preexisting"
        )

        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)

        # ===== FIRST RUN: Create pre-existing backtests =====
        app1 = create_app(name="FirstRun", config=config)
        app1.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)

        first_param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [70],
            "rsi_oversold_threshold": [30],
            "ema_time_frame": ["2h"],
            "ema_short_period": [100],
            "ema_long_period": [150, 200],
            "ema_cross_lookback_window": [4]
        }
        first_variations = [
            dict(zip(first_param_grid.keys(), values))
            for values in product(*first_param_grid.values())
        ]

        first_strategies = []
        for param_set in first_variations:
            first_strategies.append(
                RSIEMACrossoverStrategy(
                    algorithm_id=generate_algorithm_id(params=param_set),
                    time_unit=TimeUnit.HOUR,
                    interval=2,
                    market="BITVAVO",
                    rsi_time_frame=param_set["rsi_time_frame"],
                    rsi_period=param_set["rsi_period"],
                    rsi_overbought_threshold=param_set["rsi_overbought_threshold"],
                    rsi_oversold_threshold=param_set["rsi_oversold_threshold"],
                    ema_time_frame=param_set["ema_time_frame"],
                    ema_short_period=param_set["ema_short_period"],
                    ema_long_period=param_set["ema_long_period"],
                    ema_cross_lookback_window=param_set["ema_cross_lookback_window"],
                    symbols=["BTC", "ETH"],
                    position_sizes=[
                        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
                        PositionSize(symbol="ETH", percentage_of_portfolio=20.0)
                    ]
                )
            )

        self.assertEqual(len(first_strategies), 2)
        first_algorithm_ids = set(s.algorithm_id for s in first_strategies)

        first_backtests = app1.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=first_strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=backtest_storage_dir,
            use_checkpoints=False,
            show_progress=True
        )

        self.assertEqual(len(first_backtests), 2)

        # ===== SECOND RUN: With final_filter_function =====
        app2 = create_app(name="SecondRun", config=config)
        app2.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)

        # Track which backtests the filter function sees
        filter_seen_algorithm_ids = []

        def tracking_final_filter(backtests):
            """Filter that tracks which backtests it receives."""
            for bt in backtests:
                filter_seen_algorithm_ids.append(bt.algorithm_id)
            # Return all backtests (no actual filtering)
            return backtests

        second_param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [80],  # Different
            "rsi_oversold_threshold": [20],    # Different
            "ema_time_frame": ["2h"],
            "ema_short_period": [100],
            "ema_long_period": [150, 200],
            "ema_cross_lookback_window": [4]
        }
        second_variations = [
            dict(zip(second_param_grid.keys(), values))
            for values in product(*second_param_grid.values())
        ]

        second_strategies = []
        for param_set in second_variations:
            second_strategies.append(
                RSIEMACrossoverStrategy(
                    algorithm_id=generate_algorithm_id(params=param_set),
                    time_unit=TimeUnit.HOUR,
                    interval=2,
                    market="BITVAVO",
                    rsi_time_frame=param_set["rsi_time_frame"],
                    rsi_period=param_set["rsi_period"],
                    rsi_overbought_threshold=param_set["rsi_overbought_threshold"],
                    rsi_oversold_threshold=param_set["rsi_oversold_threshold"],
                    ema_time_frame=param_set["ema_time_frame"],
                    ema_short_period=param_set["ema_short_period"],
                    ema_long_period=param_set["ema_long_period"],
                    ema_cross_lookback_window=param_set["ema_cross_lookback_window"],
                    symbols=["BTC", "ETH"],
                    position_sizes=[
                        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
                        PositionSize(symbol="ETH", percentage_of_portfolio=20.0)
                    ]
                )
            )

        self.assertEqual(len(second_strategies), 2)
        second_algorithm_ids = set(s.algorithm_id for s in second_strategies)

        # Ensure sets are different
        self.assertEqual(
            len(first_algorithm_ids.intersection(second_algorithm_ids)), 0
        )

        second_backtests = app2.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=second_strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=backtest_storage_dir,
            use_checkpoints=False,
            show_progress=True,
            final_filter_function=tracking_final_filter
        )

        # ===== VERIFICATION =====
        # The filter should have ONLY seen the second strategies' backtests
        filter_seen_set = set(filter_seen_algorithm_ids)

        # Filter should NOT have seen first strategies
        for alg_id in first_algorithm_ids:
            self.assertNotIn(
                alg_id, filter_seen_set,
                f"Final filter saw pre-existing backtest {alg_id} from first run"
            )

        # Filter SHOULD have seen second strategies
        for alg_id in second_algorithm_ids:
            self.assertIn(
                alg_id, filter_seen_set,
                f"Final filter did not see backtest {alg_id} from current run"
            )

        # Results should only contain second strategies
        self.assertEqual(len(second_backtests), 2)
        result_ids = set(b.algorithm_id for b in second_backtests)
        self.assertEqual(result_ids, second_algorithm_ids)

        # Clean up
        if os.path.exists(backtest_storage_dir):
            shutil.rmtree(backtest_storage_dir)
