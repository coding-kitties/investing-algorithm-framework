"""
Test that strategy metadata is preserved when running vector backtests.
"""
import os
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest import TestCase

from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import create_app, BacktestDateRange, \
    SnapshotInterval, RESOURCE_DIRECTORY, DATA_DIRECTORY, TimeUnit, \
    TradingStrategy, DataSource, DataType, PositionSize, \
    generate_algorithm_id, Schedule, Study, Universe, BacktestWindow, \
    BacktestEngine, SignalSide, signal_series_from_column


class RSIEMACrossoverStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    def __init__(
        self,
        algorithm_id,
        symbols,
        position_sizes,
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
            schedule=schedule,
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

            # Combine both conditions
            buy_signal = rsi_oversold & ema_crossover_lookback
            buy_signal = buy_signal.fillna(False).astype(bool)

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


class Test(TestCase):

    def setUp(self):
        self.backtest_storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'resources',
            'test_backtest_storage'
        )


    def test_metadata_preserved_single_strategy(self):
        """Test that metadata is preserved for a single strategy."""

        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        # Resource directory should point to /tests/resources
        # Resource directory is two levels up from the current file
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), '..', 'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory, DATA_DIRECTORY: "test_data/ohlcv"}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)
        end_date = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=60)

        # Split into multiple date ranges to test progressive filtering
        date_range_1 = BacktestDateRange(
            start_date=start_date, end_date=end_date, name="Period 1"
        )
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
            schedule=Schedule.every(2, TimeUnit.HOUR),
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
            symbols=["BTC"],
            position_sizes=[
                PositionSize(
                    symbol="BTC", percentage_of_portfolio=20.0
                )
            ]
        )
        strategy.metadata = {
            "author": "Test User",
            "version": "1.0",
            "description": "Test strategy",
            "custom_param": "custom_value"
        }
        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            initial_capital=1000,
            risk_free_rate=0.027,
            backtest_windows=[BacktestWindow(train_range=date_range_1)],
            engines=[BacktestEngine.VECTOR],
        )
        backtests = app.run_backtest(
            strategy=strategy,
            study=study,
            snapshot_interval=SnapshotInterval.DAILY,
            use_checkpoints=False,
            backtest_storage_directory=self.backtest_storage_dir
        )
        backtest = backtests[0]

        # Verify metadata is preserved
        self.assertIsNotNone(backtest.metadata)
        self.assertEqual(backtest.metadata.get("author"), "Test User")
        self.assertEqual(backtest.metadata.get("version"), "1.0")
        self.assertEqual(backtest.metadata.get("description"), "Test strategy")
        self.assertEqual(backtest.metadata.get("custom_param"), "custom_value")


    def test_metadata_preserved_multiple_strategies(self):
        """Test that metadata is preserved for a single strategy."""

        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        # Resource directory should point to /tests/resources
        # Resource directory is two levels up from the current file
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory, DATA_DIRECTORY: "test_data/ohlcv"}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(market="BITVAVO", trading_symbol="EUR",
                       initial_balance=400)
        end_date = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=60)

        # Split into multiple date ranges to test progressive filtering
        date_range_1 = BacktestDateRange(
            start_date=start_date, end_date=end_date, name="Period 1"
        )
        param_set_one = {
            "rsi_time_frame": "2h",
            "rsi_period": 14,
            "rsi_overbought_threshold": 70,
            "rsi_oversold_threshold": 30,
            "ema_time_frame": "2h",
            "ema_short_period": 100,
            "ema_long_period": 150,
            "ema_cross_lookback_window": 4
        }
        param_set_two = {
            "rsi_time_frame": "2h",
            "rsi_period": 14,
            "rsi_overbought_threshold": 80,
            "rsi_oversold_threshold": 40,
            "ema_time_frame": "2h",
            "ema_short_period": 100,
            "ema_long_period": 150,
            "ema_cross_lookback_window": 4
        }
        strategy_one = RSIEMACrossoverStrategy(
            algorithm_id=generate_algorithm_id(params=param_set_one),
            schedule=Schedule.every(2, TimeUnit.HOUR),
            market="BITVAVO",
            rsi_time_frame=param_set_one["rsi_time_frame"],
            rsi_period=param_set_one["rsi_period"],
            rsi_overbought_threshold=param_set_one[
                "rsi_overbought_threshold"
            ],
            rsi_oversold_threshold=param_set_one[
                "rsi_oversold_threshold"
            ],
            ema_time_frame=param_set_one["ema_time_frame"],
            ema_short_period=param_set_one["ema_short_period"],
            ema_long_period=param_set_one["ema_long_period"],
            ema_cross_lookback_window=param_set_one[
                "ema_cross_lookback_window"
            ],
            symbols=["BTC"],
            position_sizes=[
                PositionSize(
                    symbol="BTC", percentage_of_portfolio=20.0
                )
            ]
        )
        strategy_one.metadata = {
            "author": "Test User",
            "version": "1.0",
            "description": "Test strategy",
            "custom_param": "custom_value"
        }

        strategy_two = RSIEMACrossoverStrategy(
            algorithm_id=generate_algorithm_id(params=param_set_two),
            schedule=Schedule.every(2, TimeUnit.HOUR),
            market="BITVAVO",
            rsi_time_frame=param_set_two["rsi_time_frame"],
            rsi_period=param_set_two["rsi_period"],
            rsi_overbought_threshold=param_set_two[
                "rsi_overbought_threshold"
            ],
            rsi_oversold_threshold=param_set_two[
                "rsi_oversold_threshold"
            ],
            ema_time_frame=param_set_two["ema_time_frame"],
            ema_short_period=param_set_two["ema_short_period"],
            ema_long_period=param_set_two["ema_long_period"],
            ema_cross_lookback_window=param_set_two[
                "ema_cross_lookback_window"
            ],
            symbols=["BTC"],
            position_sizes=[
                PositionSize(
                    symbol="BTC", percentage_of_portfolio=20.0
                )
            ]
        )
        strategy_two.metadata = {
            "author": "Test User",
            "version": "1.0",
            "description": "Test strategy",
            "custom_param": "custom_value"
        }
        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            initial_capital=1000,
            risk_free_rate=0.027,
            backtest_windows=[BacktestWindow(train_range=date_range_1)],
            engines=[BacktestEngine.VECTOR],
        )
        backtests = app.run_backtests(
            strategies=[strategy_one, strategy_two],
            study=study,
            snapshot_interval=SnapshotInterval.DAILY,
            use_checkpoints=False,
            backtest_storage_directory=self.backtest_storage_dir
        )

        for backtest in backtests:
            # Verify metadata is preserved
            self.assertIsNotNone(backtest.metadata)
            self.assertEqual(backtest.metadata.get("author"), "Test User")
            self.assertEqual(backtest.metadata.get("version"), "1.0")
            self.assertEqual(backtest.metadata.get("description"),
                             "Test strategy")
            self.assertEqual(backtest.metadata.get("custom_param"),
                             "custom_value")

    def tearDown(self):
        # Clean up storage directory after tests
        teardown_sqlalchemy()
        if os.path.exists(self.backtest_storage_dir):
            shutil.rmtree(self.backtest_storage_dir, ignore_errors=True)
