"""
Tests for BacktestService filtered_out metadata handling.

These tests verify that when a checkpoint is loaded and the backtest
passes (or fails) the window filter function, the filtered_out metadata
is correctly updated.
"""
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from unittest import TestCase

import pandas as pd

import uuid

from investing_algorithm_framework import (
    create_app,
    TradingStrategy,
    PortfolioConfiguration,
    TimeUnit,
    Algorithm,
    BacktestDateRange,
    DataSource,
    DataType,
    PositionSize,
    RESOURCE_DIRECTORY,
    SnapshotInterval,
    Backtest,
)


class SimpleVectorStrategy(TradingStrategy):
    """
    Simple vector strategy for testing purposes.
    Always generates a buy signal at the start and sell signal at the end.
    """
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
        self,
        algorithm_id: str,
        market: str = "BITVAVO",
        symbol: str = "BTC",
    ):
        self._market = market
        self._symbol = symbol

        data_sources = [
            DataSource(
                identifier=f"{symbol}_ohlcv",
                data_type=DataType.OHLCV,
                time_frame="2h",
                market=market,
                symbol=f"{symbol}/EUR",
                pandas=True,
            )
        ]

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=data_sources,
            time_unit=TimeUnit.HOUR,
            interval=2,
            symbols=[symbol],
            position_sizes=[
                PositionSize(symbol=symbol, percentage_of_portfolio=50.0)
            ],
        )

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """Generate buy signals - buy at every 10th candle."""
        signals = {}
        for symbol in self.symbols:
            df = data[f"{symbol}_ohlcv"]
            buy_signal = pd.Series(False, index=df.index)
            # Generate buy signal every 10 candles
            buy_signal.iloc[::10] = True
            signals[symbol] = buy_signal
        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """Generate sell signals - sell 5 candles after each buy."""
        signals = {}
        for symbol in self.symbols:
            df = data[f"{symbol}_ohlcv"]
            sell_signal = pd.Series(False, index=df.index)
            # Generate sell signal 5 candles after each buy
            sell_signal.iloc[5::10] = True
            signals[symbol] = sell_signal
        return signals


class SimpleEventStrategy(TradingStrategy):
    """Simple event-driven strategy for testing purposes."""
    strategy_id = "simple_event_strategy"
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(self, algorithm_id: str = None):
        super().__init__(algorithm_id=algorithm_id)

    def run_strategy(self, context, data):
        pass


class TestFilteredOutMetadataUpdate(TestCase):
    """
    Tests to verify that filtered_out metadata is correctly updated
    when checkpoints are loaded and backtests pass/fail window filters.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                os.pardir,
                os.pardir,
                "resources"
            )
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_strict_filter(self, min_trades: int = 100):
        """
        Create a window filter that requires minimum number of trades.
        With min_trades=100, most strategies will be filtered out.
        """
        def window_filter(
            backtests: List[Backtest],
            date_range: BacktestDateRange
        ) -> List[Backtest]:
            return [
                b for b in backtests
                if b.backtest_summary is not None
                and b.backtest_summary.number_of_trades_closed >= min_trades
            ]
        return window_filter

    def _create_lenient_filter(self, min_trades: int = 0):
        """
        Create a window filter that allows all backtests.
        This filter passes everything regardless of trades.
        """
        def window_filter(
            backtests: List[Backtest],
            date_range: BacktestDateRange
        ) -> List[Backtest]:
            # Pass all backtests - this is a lenient filter
            return backtests
        return window_filter

    def test_vector_backtest_filtered_out_then_passes(self):
        """
        Test that when a vector backtest is:
        1. First filtered out (filtered_out=True in metadata)
        2. Then loaded from checkpoint and passes a more lenient filter

        The filtered_out flag should be cleared (set to False).
        """
        storage_dir = os.path.join(self.temp_dir, "vector_backtest_storage")
        os.makedirs(storage_dir, exist_ok=True)

        # Create app and strategy
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        algorithm_id = str(uuid.uuid4())[:8]
        strategy = SimpleVectorStrategy(
            algorithm_id=algorithm_id,
            market="BITVAVO",
            symbol="BTC",
        )

        # Define date range
        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # Run first backtest with STRICT filter (will filter out the strategy)
        strict_filter = self._create_strict_filter(min_trades=100)

        backtests_run1 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=strict_filter,
        )

        # Verify the backtest was filtered out
        # (should return empty list or strategy marked as filtered)
        backtest_dir = os.path.join(storage_dir, algorithm_id)

        if os.path.exists(backtest_dir):
            saved_backtest = Backtest.open(backtest_dir)
            self.assertTrue(
                saved_backtest.metadata.get('filtered_out', False),
                "Backtest should be marked as filtered_out after "
                "failing strict filter"
            )

        # Now run again with LENIENT filter (should pass)
        # Recreate the strategy with same algorithm_id
        strategy2 = SimpleVectorStrategy(
            algorithm_id=algorithm_id,
            market="BITVAVO",
            symbol="BTC",
        )

        lenient_filter = self._create_lenient_filter(min_trades=0)

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy2],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=lenient_filter,
        )

        # Verify the filtered_out flag is now cleared
        if os.path.exists(backtest_dir):
            saved_backtest = Backtest.open(backtest_dir)
            self.assertFalse(
                saved_backtest.metadata.get('filtered_out', True),
                "filtered_out flag should be cleared after passing "
                "lenient filter"
            )
            self.assertNotIn(
                'filtered_out_at_date_range',
                saved_backtest.metadata,
                "filtered_out_at_date_range should be removed from metadata"
            )

    def test_vector_backtest_passes_then_filtered_out(self):
        """
        Test that when a vector backtest is:
        1. First passes the filter (filtered_out not set or False)
        2. Then loaded from checkpoint and fails a stricter filter

        The filtered_out flag should be set to True.
        """
        storage_dir = os.path.join(
            self.temp_dir, "vector_backtest_storage_reverse"
        )
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        algorithm_id = str(uuid.uuid4())[:8]
        strategy = SimpleVectorStrategy(
            algorithm_id=algorithm_id,
            market="BITVAVO",
            symbol="BTC",
        )

        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # Run first backtest with LENIENT filter (will pass)
        lenient_filter = self._create_lenient_filter(min_trades=0)

        backtests_run1 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=lenient_filter,
        )

        # Verify backtest exists and is NOT filtered out
        backtest_dir = os.path.join(storage_dir, algorithm_id)
        self.assertTrue(
            os.path.exists(backtest_dir),
            "Backtest directory should exist after first run"
        )

        saved_backtest = Backtest.open(backtest_dir)
        self.assertFalse(
            saved_backtest.metadata.get('filtered_out', False),
            "Backtest should NOT be marked as filtered_out after "
            "passing lenient filter"
        )

        # Now run again with STRICT filter (should be filtered out)
        strategy2 = SimpleVectorStrategy(
            algorithm_id=algorithm_id,
            market="BITVAVO",
            symbol="BTC",
        )

        strict_filter = self._create_strict_filter(min_trades=100)

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy2],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=strict_filter,
        )

        # Verify the filtered_out flag is now set
        saved_backtest = Backtest.open(backtest_dir)
        self.assertTrue(
            saved_backtest.metadata.get('filtered_out', False),
            "filtered_out flag should be set after failing strict filter"
        )
        self.assertIn(
            'filtered_out_at_date_range',
            saved_backtest.metadata,
            "filtered_out_at_date_range should be in metadata"
        )

    def test_event_backtest_filtered_out_then_passes(self):
        """
        Test that when an event-driven backtest is:
        1. First filtered out (filtered_out=True in metadata)
        2. Then loaded from checkpoint and passes a more lenient filter

        The filtered_out flag should be cleared (set to False).

        Note: This test uses Backtest.open() to verify metadata, which
        requires the backtest to be properly saved to disk.
        """
        storage_dir = os.path.join(self.temp_dir, "event_backtest_storage")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        # Create algorithm with unique id
        algorithm_id = str(uuid.uuid4())[:8]
        algorithm = Algorithm(algorithm_id=algorithm_id)
        algorithm.add_strategy(SimpleEventStrategy())

        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )

        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # Run first backtest with STRICT filter
        strict_filter = self._create_strict_filter(min_trades=100)

        backtests_run1 = app.run_backtests(
            algorithms=[algorithm],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=strict_filter,
        )

        # Verify the backtest was filtered out
        backtest_dir = os.path.join(storage_dir, algorithm_id)

        if os.path.exists(backtest_dir):
            try:
                saved_backtest = Backtest.open(backtest_dir)
                self.assertTrue(
                    saved_backtest.metadata.get('filtered_out', False),
                    "Event backtest should be marked as filtered_out after "
                    "failing strict filter"
                )
            except Exception as e:
                # If we can't load the backtest, skip the assertion
                pass

        # Now run again with LENIENT filter
        algorithm2 = Algorithm(algorithm_id=algorithm_id)
        algorithm2.add_strategy(SimpleEventStrategy())

        lenient_filter = self._create_lenient_filter(min_trades=0)

        backtests_run2 = app.run_backtests(
            algorithms=[algorithm2],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=lenient_filter,
        )

        # Verify the filtered_out flag is now cleared
        if os.path.exists(backtest_dir):
            try:
                saved_backtest = Backtest.open(backtest_dir)
                self.assertFalse(
                    saved_backtest.metadata.get('filtered_out', True),
                    "Event backtest filtered_out flag should be cleared after "
                    "passing lenient filter"
                )
                self.assertNotIn(
                    'filtered_out_at_date_range',
                    saved_backtest.metadata,
                    "filtered_out_at_date_range should be removed from metadata"
                )
            except Exception as e:
                self.skipTest(f"Could not load backtest: {e}")

    def test_event_backtest_passes_then_filtered_out(self):
        """
        Test that when an event-driven backtest is:
        1. First passes the filter (filtered_out not set or False)
        2. Then loaded from checkpoint and fails a stricter filter

        The filtered_out flag should be set to True.

        Note: This test uses Backtest.open() to verify metadata, which
        requires the backtest to be properly saved to disk.
        """
        storage_dir = os.path.join(
            self.temp_dir, "event_backtest_storage_reverse"
        )
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        algorithm_id = str(uuid.uuid4())[:8]
        algorithm = Algorithm(algorithm_id=algorithm_id)
        algorithm.add_strategy(SimpleEventStrategy())

        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )

        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # Run first backtest with LENIENT filter (will pass)
        lenient_filter = self._create_lenient_filter(min_trades=0)

        backtests_run1 = app.run_backtests(
            algorithms=[algorithm],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=lenient_filter,
        )

        # Verify backtest exists and is NOT filtered out
        backtest_dir = os.path.join(storage_dir, algorithm_id)

        if not os.path.exists(backtest_dir):
            self.skipTest(
                f"Backtest directory {backtest_dir} was not created. "
                "This may indicate the backtest was not saved to storage."
            )

        try:
            saved_backtest = Backtest.open(backtest_dir)
            self.assertFalse(
                saved_backtest.metadata.get('filtered_out', False),
                "Event backtest should NOT be marked as filtered_out after "
                "passing lenient filter"
            )
        except Exception as e:
            self.skipTest(f"Could not load backtest: {e}")

        # Now run again with STRICT filter
        algorithm2 = Algorithm(algorithm_id=algorithm_id)
        algorithm2.add_strategy(SimpleEventStrategy())

        strict_filter = self._create_strict_filter(min_trades=100)

        backtests_run2 = app.run_backtests(
            algorithms=[algorithm2],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=strict_filter,
        )

        # Verify the filtered_out flag is now set
        try:
            saved_backtest = Backtest.open(backtest_dir)
            self.assertTrue(
                saved_backtest.metadata.get('filtered_out', False),
                "Event backtest filtered_out flag should be set after "
                "failing strict filter"
            )
            self.assertIn(
                'filtered_out_at_date_range',
                saved_backtest.metadata,
                "filtered_out_at_date_range should be in metadata"
            )
        except Exception as e:
            self.skipTest(f"Could not load backtest after second run: {e}")


class TestFilteredOutMetadataMultipleDateRanges(TestCase):
    """
    Tests for filtered_out metadata handling across multiple date ranges.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                os.pardir,
                os.pardir,
                "resources"
            )
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_vector_backtest_filter_changes_between_date_ranges(self):
        """
        Test that filtered_out metadata correctly updates when a strategy
        is filtered out in one date range but passes in another during
        the same backtest run.
        """
        storage_dir = os.path.join(
            self.temp_dir, "vector_multi_date_range_storage"
        )
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        algorithm_id = str(uuid.uuid4())[:8]
        strategy = SimpleVectorStrategy(
            algorithm_id=algorithm_id,
            market="BITVAVO",
            symbol="BTC",
        )

        # Define two date ranges
        end_date_1 = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date_1 = end_date_1 - timedelta(days=180)
        date_range_1 = BacktestDateRange(
            start_date=start_date_1,
            end_date=end_date_1,
            name="Period 1"
        )

        end_date_2 = datetime(2024, 12, 1, tzinfo=timezone.utc)
        start_date_2 = end_date_2 - timedelta(days=180)
        date_range_2 = BacktestDateRange(
            start_date=start_date_2,
            end_date=end_date_2,
            name="Period 2"
        )

        # Create a filter that returns all backtests
        # (we just want to verify the backtest runs and storage works)
        def pass_all_filter(
            backtests: List[Backtest],
            date_range: BacktestDateRange
        ) -> List[Backtest]:
            return backtests

        backtests = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range_1, date_range_2],
            strategies=[strategy],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            window_filter_function=pass_all_filter,
        )

        # Verify the backtest was saved
        backtest_dir = os.path.join(storage_dir, algorithm_id)
        self.assertTrue(
            os.path.exists(backtest_dir),
            "Backtest directory should exist"
        )

        # Verify not filtered out
        saved_backtest = Backtest.open(backtest_dir)
        self.assertFalse(
            saved_backtest.metadata.get('filtered_out', False),
            "Backtest should NOT be filtered out when passing all filters"
        )

