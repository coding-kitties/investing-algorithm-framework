import os
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
        id,
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
            id=id,
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

    @staticmethod
    def filter_function_with_closed_trades(
        backtests, backtest_date_range: BacktestDateRange
    ):
        """
        Filter function that only keeps backtests with at least one closed trade.
        """
        filtered = []
        for backtest in backtests:
            metrics = backtest.get_backtest_metrics(backtest_date_range)
            if metrics.number_of_trades_closed > 0:
                filtered.append(backtest)

        return filtered

    def _verify_filtered_strategy_has_no_closed_trades(self, all_strategies, filtered_backtests, app, date_ranges):
        """
        Helper method to verify that a strategy filtered out by the filter function
        indeed has no closed trades. This ensures the filtering logic works correctly.
        """
        # Get strategy IDs that passed the filter
        filtered_strategy_ids = set()
        for backtest in filtered_backtests:
            filtered_strategy_ids.update(backtest.strategy_ids)

        # Find a strategy that was filtered out
        filtered_out_strategy = None
        for strategy in all_strategies:
            if strategy.id not in filtered_strategy_ids:
                filtered_out_strategy = strategy
                break

        self.assertIsNotNone(
            filtered_out_strategy,
            "Should have at least one strategy that was filtered out"
        )

        print(f"Verifying filtered out strategy: {filtered_out_strategy.id}")

        # Run the filtered-out strategy individually to verify it has no closed trades
        individual_backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=date_ranges,
            strategies=[filtered_out_strategy],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            # No filter function - run it directly
        )

        self.assertEqual(len(individual_backtests), 1, "Should have exactly one backtest result")

        individual_backtest = individual_backtests[0]

        # Check that this strategy indeed has no closed trades in at least one date range
        has_no_closed_trades_in_at_least_one_range = False

        for backtest_run in individual_backtest.backtest_runs:
            trades = backtest_run.get_trades()
            closed_trades = [t for t in trades if TradeStatus.CLOSED.equals(t.status)]

            if len(closed_trades) == 0:
                has_no_closed_trades_in_at_least_one_range = True
                print(f"✓ Strategy {filtered_out_strategy.id} has no closed trades in date range {backtest_run.backtest_date_range_name or f'{backtest_run.backtest_start_date.date()} to {backtest_run.backtest_end_date.date()}'}")
                break

        self.assertTrue(
            has_no_closed_trades_in_at_least_one_range,
            f"Filtered out strategy {filtered_out_strategy.id} should have no closed trades in at least one date range"
        )

        print("✓ Verified that filtered strategy was correctly excluded for having no closed trades")

    def test_run_with_filter_function(self):
        """
        Test run_vector_backtests with a filter_function that filters
        strategies based on whether they have closed trades.
        """
        param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [70, 80],
            "rsi_oversold_threshold": [30, 20],
            "ema_time_frame": ["2h"],
            "ema_short_period": [50, 100],
            "ema_long_period": [150, 200],
            "ema_cross_lookback_window": [2, 4, 6, 12]
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
        strategies = []
        for param_set in param_variations:
            strategies.append(
                RSIEMACrossoverStrategy(
                    id=generate_strategy_id(param_set),
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

        print(f"Starting with {len(strategies)} strategies")
        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            filter_function=self.filter_function_with_closed_trades
        )
        print(f"After filtering: {len(backtests)} strategies remain")

        # Should have fewer backtests than strategies if filter worked
        self.assertLessEqual(len(backtests), len(strategies))

        # All remaining backtests should have closed trades
        for backtest in backtests:
            self.assertGreater(
                backtest.backtest_summary.number_of_trades_closed,
                0,
                "All filtered backtests "
                "should have at least one closed trade"
            )

        # Check that at least one backtest has trades
        self.assertEqual(len(backtests), 12, "Should have at least 12 backtest")
        first_backtest = backtests[0]
        # Check that we have backtest runs
        self.assertGreater(len(first_backtest.backtest_runs), 0)

        # Get trades from the first run
        run = first_backtest.backtest_runs[0]
        trades = run.get_trades()
        self.assertGreater(len(trades), 0, "Should have at least one trade")

        # Verify at least one trade is closed
        closed_trades = [t for t in trades if TradeStatus.CLOSED.equals(t.status)]
        self.assertGreater(len(closed_trades), 0, "Should have at least one closed trade")

        # Verify that filtering actually worked by checking a filtered-out strategy
        self._verify_filtered_strategy_has_no_closed_trades(
            all_strategies=strategies,
            filtered_backtests=backtests,
            app=app,
            date_ranges=[date_range_1, date_range_2]
        )

    def test_run_with_filter_function_and_storage(self):
        """
        Test run_vector_backtests with a filter_function that filters
        strategies based on whether they have closed trades.
        """
        param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [70, 80],
            "rsi_oversold_threshold": [30, 20],
            "ema_time_frame": ["2h"],
            "ema_short_period": [50, 100],
            "ema_long_period": [150, 200],
            "ema_cross_lookback_window": [2, 4, 6, 12]
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
        strategies = []
        for param_set in param_variations:
            strategies.append(
                RSIEMACrossoverStrategy(
                    id=generate_strategy_id(param_set),
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

        print(f"Starting with {len(strategies)} strategies")
        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            filter_function=self.filter_function_with_closed_trades,
            backtest_storage_directory=os.path.join(
                resource_directory, "temp_backtest_storage"
            )
        )
        print(f"After filtering: {len(backtests)} strategies remain")

        # Should have fewer backtests than strategies if filter worked
        self.assertLessEqual(len(backtests), len(strategies))

        # All remaining backtests should have closed trades
        for backtest in backtests:
            self.assertGreater(
                backtest.backtest_summary.number_of_trades_closed,
                0,
                "All filtered backtests "
                "should have at least one closed trade"
            )

        # Check that at least one backtest has trades
        self.assertEqual(len(backtests), 12, "Should have at least 12 backtest")
        first_backtest = backtests[0]
        # Check that we have backtest runs
        self.assertGreater(len(first_backtest.backtest_runs), 0)

        # Get trades from the first run
        run = first_backtest.backtest_runs[0]
        trades = run.get_trades()
        self.assertGreater(len(trades), 0, "Should have at least one trade")

        # Verify at least one trade is closed
        closed_trades = [t for t in trades if TradeStatus.CLOSED.equals(t.status)]
        self.assertGreater(len(closed_trades), 0, "Should have at least one closed trade")

        # Verify that filtering actually worked by checking a filtered-out strategy
        self._verify_filtered_strategy_has_no_closed_trades(
            all_strategies=strategies,
            filtered_backtests=backtests,
            app=app,
            date_ranges=[date_range_1, date_range_2]
        )

    def test_filtered_strategy_has_no_closed_trades(self):
        """
        Test that a strategy filtered out by the filter function indeed has no closed trades.
        This verifies the filtering logic works correctly.
        """
        param_grid = {
            "rsi_time_frame": ["2h"],
            "rsi_period": [14],
            "rsi_overbought_threshold": [70, 80],
            "rsi_oversold_threshold": [30, 20],
            "ema_time_frame": ["2h"],
            "ema_short_period": [50, 100],
            "ema_long_period": [150, 200],
            "ema_cross_lookback_window": [2, 4, 6, 12]
        }

        param_options = param_grid
        param_variations = [
            dict(zip(param_options.keys(), values))
            for values in product(*param_options.values())
        ]

        # RESOURCE_DIRECTORY should always point to the parent directory/resources
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

        # Create all strategies
        all_strategies = []
        for param_set in param_variations:
            strategy = RSIEMACrossoverStrategy(
                id=generate_strategy_id(param_set),
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
            all_strategies.append(strategy)

        print(f"Starting with {len(all_strategies)} strategies")

        # Run vector backtests with filtering
        filtered_backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=all_strategies,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            filter_function=self.filter_function_with_closed_trades
        )

        print(f"After filtering: {len(filtered_backtests)} strategies remain")

        # Get strategy IDs that passed the filter
        filtered_strategy_ids = set()
        for backtest in filtered_backtests:
            filtered_strategy_ids.update(backtest.strategy_ids)

        # Find a strategy that was filtered out
        filtered_out_strategy = None
        for strategy in all_strategies:
            if strategy.id not in filtered_strategy_ids:
                filtered_out_strategy = strategy
                break

        self.assertIsNotNone(
            filtered_out_strategy,
            "Should have at least one strategy that was filtered out"
        )

        print(f"Testing filtered out strategy: {filtered_out_strategy.id}")

        # Run the filtered-out strategy individually to verify it has no closed trades
        individual_backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=[filtered_out_strategy],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            # No filter function - run it directly
        )

        self.assertEqual(len(individual_backtests), 1, "Should have exactly one backtest result")

        individual_backtest = individual_backtests[0]

        # Check that this strategy indeed has no closed trades in at least one date range
        has_no_closed_trades_in_at_least_one_range = False

        for backtest_run in individual_backtest.backtest_runs:
            trades = backtest_run.get_trades()
            closed_trades = [t for t in trades if TradeStatus.CLOSED.equals(t.status)]

            if len(closed_trades) == 0:
                has_no_closed_trades_in_at_least_one_range = True
                print(f"Strategy {filtered_out_strategy.id} has no closed trades in date range {backtest_run.backtest_date_range_name or f'{backtest_run.backtest_start_date.date()} to {backtest_run.backtest_end_date.date()}'}")
                break

        self.assertTrue(
            has_no_closed_trades_in_at_least_one_range,
            f"Filtered out strategy {filtered_out_strategy.id} should have no closed trades in at least one date range"
        )

        print("✓ Verified that filtered strategy was correctly excluded for having no closed trades")

