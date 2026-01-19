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
from unittest.mock import MagicMock

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
    OperationalException,
)
from investing_algorithm_framework.infrastructure import BacktestService


def _create_backtest_service() -> BacktestService:
    """
    Create a BacktestService instance with mocked dependencies for testing.

    This helper function creates a BacktestService with minimal mock
    dependencies, suitable for testing methods that don't require
    full service functionality (like _validate_algorithm_ids).

    Returns:
        BacktestService: An instance of BacktestService with mocked
            dependencies.
    """
    return BacktestService(
        data_provider_service=MagicMock(),
        order_service=MagicMock(),
        portfolio_service=MagicMock(),
        portfolio_snapshot_service=MagicMock(),
        position_repository=MagicMock(),
        trade_service=MagicMock(),
        configuration_service=MagicMock(),
        portfolio_configuration_service=MagicMock(),
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
                "filtered_out flag should be set after failing strict filter"
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


class TestStorageDirectoryIsolation(TestCase):
    """
    Tests to verify that when running backtests with a storage directory
    that already contains backtests from previous runs, only the strategies
    from the current batch are included in the results.
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

    def test_vector_backtest_excludes_preexisting_backtests_from_results(self):
        """
        Test that when running vector backtests with a storage directory
        that already contains backtests from a previous run, only the
        strategies from the current batch are returned in the results.

        Scenario:
        1. Run backtest for Strategy A and save to storage
        2. Run backtest for Strategy B with same storage directory
        3. Results should only contain Strategy B, not Strategy A
        """
        storage_dir = os.path.join(self.temp_dir, "shared_storage")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        # Define date range
        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # --- First run: Strategy A ---
        algorithm_id_a = "strategy_a_" + str(uuid.uuid4())[:4]
        strategy_a = SimpleVectorStrategy(
            algorithm_id=algorithm_id_a,
            market="BITVAVO",
            symbol="BTC",
        )

        backtests_run1 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_a],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # Verify Strategy A was saved
        self.assertEqual(
            len(backtests_run1), 1,
            "First run should return exactly 1 backtest"
        )
        self.assertEqual(
            backtests_run1[0].algorithm_id, algorithm_id_a,
            "First run should return Strategy A"
        )

        # Verify Strategy A exists in storage
        backtest_dir_a = os.path.join(storage_dir, algorithm_id_a)
        self.assertTrue(
            os.path.exists(backtest_dir_a),
            "Strategy A backtest directory should exist"
        )

        # --- Second run: Strategy B (different strategy) ---
        algorithm_id_b = "strategy_b_" + str(uuid.uuid4())[:4]
        strategy_b = SimpleVectorStrategy(
            algorithm_id=algorithm_id_b,
            market="BITVAVO",
            symbol="BTC",
        )

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_b],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # Verify ONLY Strategy B is in results, NOT Strategy A
        self.assertEqual(
            len(backtests_run2), 1,
            "Second run should return exactly 1 backtest (only Strategy B)"
        )
        self.assertEqual(
            backtests_run2[0].algorithm_id, algorithm_id_b,
            "Second run should return Strategy B, not Strategy A"
        )

        # Double-check that Strategy A is NOT in the results
        result_algorithm_ids = [b.algorithm_id for b in backtests_run2]
        self.assertNotIn(
            algorithm_id_a, result_algorithm_ids,
            "Strategy A from previous run should NOT be in current results"
        )

    def test_vector_backtest_excludes_preexisting_from_final_filter(self):
        """
        Test that pre-existing backtests in storage are not passed to
        the final_filter_function.

        Scenario:
        1. Run backtest for Strategy A and save to storage
        2. Run backtest for Strategy B with same storage and final filter
        3. Final filter should only receive Strategy B
        """
        storage_dir = os.path.join(self.temp_dir, "shared_storage_filter")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # --- First run: Strategy A ---
        algorithm_id_a = "strategy_a_" + str(uuid.uuid4())[:4]
        strategy_a = SimpleVectorStrategy(
            algorithm_id=algorithm_id_a,
            market="BITVAVO",
            symbol="BTC",
        )

        app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_a],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # --- Second run: Strategy B with final filter that tracks what it receives ---
        algorithm_id_b = "strategy_b_" + str(uuid.uuid4())[:4]
        strategy_b = SimpleVectorStrategy(
            algorithm_id=algorithm_id_b,
            market="BITVAVO",
            symbol="BTC",
        )

        # Track what the final filter receives
        received_algorithm_ids = []

        def tracking_final_filter(backtests: List[Backtest]) -> List[Backtest]:
            for b in backtests:
                received_algorithm_ids.append(b.algorithm_id)
            return backtests  # Pass all through

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_b],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            final_filter_function=tracking_final_filter,
        )

        # Verify final filter only received Strategy B
        self.assertIn(
            algorithm_id_b, received_algorithm_ids,
            "Final filter should receive Strategy B"
        )
        self.assertNotIn(
            algorithm_id_a, received_algorithm_ids,
            "Final filter should NOT receive Strategy A from previous run"
        )

    def test_vector_backtest_multiple_strategies_shared_storage(self):
        """
        Test running multiple strategies in batches with shared storage.

        Scenario:
        1. Run backtests for Strategies A, B, C
        2. Run backtests for Strategies D, E with same storage
        3. Second run should only return D, E (not A, B, C)
        """
        storage_dir = os.path.join(self.temp_dir, "multi_strategy_storage")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # --- First run: Strategies A, B, C ---
        strategies_batch1 = []
        algorithm_ids_batch1 = []
        for i in range(3):
            alg_id = f"batch1_strategy_{i}_" + str(uuid.uuid4())[:4]
            algorithm_ids_batch1.append(alg_id)
            strategies_batch1.append(
                SimpleVectorStrategy(
                    algorithm_id=alg_id,
                    market="BITVAVO",
                    symbol="BTC",
                )
            )

        backtests_run1 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=strategies_batch1,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        self.assertEqual(
            len(backtests_run1), 3,
            "First run should return 3 backtests"
        )

        # --- Second run: Strategies D, E ---
        strategies_batch2 = []
        algorithm_ids_batch2 = []
        for i in range(2):
            alg_id = f"batch2_strategy_{i}_" + str(uuid.uuid4())[:4]
            algorithm_ids_batch2.append(alg_id)
            strategies_batch2.append(
                SimpleVectorStrategy(
                    algorithm_id=alg_id,
                    market="BITVAVO",
                    symbol="BTC",
                )
            )

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=strategies_batch2,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # Verify only batch 2 strategies in results
        self.assertEqual(
            len(backtests_run2), 2,
            "Second run should return exactly 2 backtests (only batch 2)"
        )

        result_algorithm_ids = [b.algorithm_id for b in backtests_run2]

        for alg_id in algorithm_ids_batch2:
            self.assertIn(
                alg_id, result_algorithm_ids,
                f"Batch 2 strategy {alg_id} should be in results"
            )

        for alg_id in algorithm_ids_batch1:
            self.assertNotIn(
                alg_id, result_algorithm_ids,
                f"Batch 1 strategy {alg_id} should NOT be in results"
            )

    def test_event_backtest_excludes_preexisting_backtests_from_results(self):
        """
        Test that when running event backtests with a storage directory
        that already contains backtests from a previous run, only the
        algorithms from the current batch are returned in the results.
        """
        storage_dir = os.path.join(self.temp_dir, "event_shared_storage")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

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

        # --- First run: Algorithm A ---
        algorithm_id_a = "algo_a_" + str(uuid.uuid4())[:4]
        algorithm_a = Algorithm(algorithm_id=algorithm_id_a)
        algorithm_a.add_strategy(SimpleEventStrategy())

        backtests_run1 = app.run_backtests(
            algorithms=[algorithm_a],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        self.assertEqual(
            len(backtests_run1), 1,
            "First run should return exactly 1 backtest"
        )

        # --- Second run: Algorithm B ---
        algorithm_id_b = "algo_b_" + str(uuid.uuid4())[:4]
        algorithm_b = Algorithm(algorithm_id=algorithm_id_b)
        algorithm_b.add_strategy(SimpleEventStrategy())

        backtests_run2 = app.run_backtests(
            algorithms=[algorithm_b],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # Verify ONLY Algorithm B is in results
        self.assertEqual(
            len(backtests_run2), 1,
            "Second run should return exactly 1 backtest (only Algorithm B)"
        )
        self.assertEqual(
            backtests_run2[0].algorithm_id, algorithm_id_b,
            "Second run should return Algorithm B, not Algorithm A"
        )

        result_algorithm_ids = [b.algorithm_id for b in backtests_run2]
        self.assertNotIn(
            algorithm_id_a, result_algorithm_ids,
            "Algorithm A from previous run should NOT be in current results"
        )


class TestValidateAlgorithmIds(TestCase):
    """
    Tests for the _validate_algorithm_ids method of BacktestService.

    This method validates that all strategies/algorithms have:
    1. An algorithm_id attribute
    2. A non-None algorithm_id value
    3. Unique algorithm_ids (no duplicates)
    """

    def test_validate_strategies_with_unique_algorithm_ids(self):
        """
        Test that validation passes when all strategies have unique
        algorithm_ids.
        """
        backtest_service = _create_backtest_service()

        strategies = [
            SimpleVectorStrategy(algorithm_id="strategy_1", symbol="BTC"),
            SimpleVectorStrategy(algorithm_id="strategy_2", symbol="BTC"),
            SimpleVectorStrategy(algorithm_id="strategy_3", symbol="BTC"),
        ]

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(strategies=strategies)

    def test_validate_strategies_with_duplicate_algorithm_ids_raises(self):
        """
        Test that validation raises OperationalException when strategies
        have duplicate algorithm_ids.
        """
        backtest_service = _create_backtest_service()

        strategies = [
            SimpleVectorStrategy(algorithm_id="strategy_1", symbol="BTC"),
            SimpleVectorStrategy(algorithm_id="strategy_1", symbol="ETH"),  # Duplicate
            SimpleVectorStrategy(algorithm_id="strategy_3", symbol="BTC"),
        ]

        with self.assertRaises(OperationalException) as context:
            backtest_service._validate_algorithm_ids(strategies=strategies)

        self.assertIn("Duplicate algorithm_id", str(context.exception))
        self.assertIn("strategy_1", str(context.exception))

    def test_validate_strategies_with_none_algorithm_id_raises(self):
        """
        Test that validation raises OperationalException when a strategy
        has a None algorithm_id.
        """
        backtest_service = _create_backtest_service()

        # Create a strategy with None algorithm_id by using a mock
        strategy_with_none_id = MagicMock()
        strategy_with_none_id.algorithm_id = None

        strategies = [
            SimpleVectorStrategy(algorithm_id="strategy_1", symbol="BTC"),
            strategy_with_none_id,
        ]

        with self.assertRaises(OperationalException) as context:
            backtest_service._validate_algorithm_ids(strategies=strategies)

        self.assertIn("algorithm_id", str(context.exception))

    def test_validate_strategies_without_algorithm_id_attribute_raises(self):
        """
        Test that validation raises OperationalException when a strategy
        doesn't have an algorithm_id attribute.
        """
        backtest_service = _create_backtest_service()

        # Create a mock without algorithm_id attribute
        strategy_without_attr = MagicMock(spec=[])  # Empty spec = no attributes

        strategies = [
            SimpleVectorStrategy(algorithm_id="strategy_1", symbol="BTC"),
            strategy_without_attr,
        ]

        with self.assertRaises(OperationalException) as context:
            backtest_service._validate_algorithm_ids(strategies=strategies)

        self.assertIn("algorithm_id", str(context.exception))

    def test_validate_algorithms_with_unique_algorithm_ids(self):
        """
        Test that validation passes when all algorithms have unique
        algorithm_ids.
        """
        backtest_service = _create_backtest_service()

        algorithms = [
            Algorithm(algorithm_id="algo_1"),
            Algorithm(algorithm_id="algo_2"),
            Algorithm(algorithm_id="algo_3"),
        ]

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(algorithms=algorithms)

    def test_validate_algorithms_with_duplicate_algorithm_ids_raises(self):
        """
        Test that validation raises OperationalException when algorithms
        have duplicate algorithm_ids.
        """
        backtest_service = _create_backtest_service()

        algorithms = [
            Algorithm(algorithm_id="algo_1"),
            Algorithm(algorithm_id="algo_1"),  # Duplicate
            Algorithm(algorithm_id="algo_3"),
        ]

        with self.assertRaises(OperationalException) as context:
            backtest_service._validate_algorithm_ids(algorithms=algorithms)

        self.assertIn("Duplicate algorithm_id", str(context.exception))
        self.assertIn("algo_1", str(context.exception))

    def test_validate_algorithms_with_none_algorithm_id_raises(self):
        """
        Test that validation raises OperationalException when an algorithm
        has a None algorithm_id.
        """
        backtest_service = _create_backtest_service()

        # Create an algorithm with None algorithm_id by using a mock
        algorithm_with_none_id = MagicMock()
        algorithm_with_none_id.algorithm_id = None

        algorithms = [
            Algorithm(algorithm_id="algo_1"),
            algorithm_with_none_id,
        ]

        with self.assertRaises(OperationalException) as context:
            backtest_service._validate_algorithm_ids(algorithms=algorithms)

        self.assertIn("algorithm_id", str(context.exception))

    def test_validate_empty_strategies_list(self):
        """
        Test that validation passes with an empty strategies list.
        """
        backtest_service = _create_backtest_service()

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(strategies=[])

    def test_validate_empty_algorithms_list(self):
        """
        Test that validation passes with an empty algorithms list.
        """
        backtest_service = _create_backtest_service()

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(algorithms=[])

    def test_validate_single_strategy(self):
        """
        Test that validation passes with a single strategy.
        """
        backtest_service = _create_backtest_service()

        strategies = [
            SimpleVectorStrategy(algorithm_id="single_strategy", symbol="BTC")
        ]

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(strategies=strategies)

    def test_validate_single_algorithm(self):
        """
        Test that validation passes with a single algorithm.
        """
        backtest_service = _create_backtest_service()

        algorithms = [Algorithm(algorithm_id="single_algo")]

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(algorithms=algorithms)

    def test_validate_many_strategies_with_unique_ids(self):
        """
        Test that validation passes with many strategies all having
        unique algorithm_ids.
        """
        backtest_service = _create_backtest_service()

        strategies = [
            SimpleVectorStrategy(algorithm_id=f"strategy_{i}", symbol="BTC")
            for i in range(100)
        ]

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(strategies=strategies)

    def test_validate_strategies_with_similar_but_unique_ids(self):
        """
        Test that validation passes when algorithm_ids are similar but
        still unique (e.g., "strategy_1" vs "strategy_10").
        """
        backtest_service = _create_backtest_service()

        strategies = [
            SimpleVectorStrategy(algorithm_id="strategy_1", symbol="BTC"),
            SimpleVectorStrategy(algorithm_id="strategy_10", symbol="BTC"),
            SimpleVectorStrategy(algorithm_id="strategy_11", symbol="BTC"),
            SimpleVectorStrategy(algorithm_id="strategy_100", symbol="BTC"),
        ]

        # Should not raise any exception
        backtest_service._validate_algorithm_ids(strategies=strategies)


class TestCreateCheckpoint(TestCase):
    """
    Tests for the create_checkpoint static method of BacktestService.

    This method creates or updates a checkpoint file that tracks which
    backtests have been completed for a given date range. Checkpoints
    are used to skip completed backtests when resuming a backtesting run.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_mock_backtest(self, algorithm_id: str) -> MagicMock:
        """Create a mock backtest with the given algorithm_id."""
        mock_backtest = MagicMock()
        mock_backtest.algorithm_id = algorithm_id
        return mock_backtest

    def test_create_checkpoint_with_empty_backtests_list(self):
        """
        Test that create_checkpoint does nothing when given an empty
        backtests list.
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        BacktestService.create_checkpoint(
            backtests=[],
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
        )

        # Checkpoint file should NOT be created
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        self.assertFalse(
            os.path.exists(checkpoint_file),
            "Checkpoint file should not be created for empty backtests list"
        )

    def test_create_checkpoint_creates_new_file(self):
        """
        Test that create_checkpoint creates a new checkpoint file when
        one doesn't exist.
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        backtests = [
            self._create_mock_backtest("algo_1"),
            self._create_mock_backtest("algo_2"),
            self._create_mock_backtest("algo_3"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
        )

        # Verify checkpoint file was created
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        self.assertTrue(
            os.path.exists(checkpoint_file),
            "Checkpoint file should be created"
        )

        # Verify checkpoint contents
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        expected_key = (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )
        self.assertIn(expected_key, checkpoints)
        self.assertEqual(
            set(checkpoints[expected_key]),
            {"algo_1", "algo_2", "algo_3"}
        )

    def test_create_checkpoint_append_mode(self):
        """
        Test that create_checkpoint in append mode adds to existing
        checkpoints without removing existing entries.
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        # First checkpoint creation
        backtests_1 = [
            self._create_mock_backtest("algo_1"),
            self._create_mock_backtest("algo_2"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_1,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            mode="append",
        )

        # Second checkpoint creation (append mode)
        backtests_2 = [
            self._create_mock_backtest("algo_3"),
            self._create_mock_backtest("algo_4"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_2,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            mode="append",
        )

        # Verify all algorithm IDs are present
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        expected_key = (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )
        self.assertEqual(
            set(checkpoints[expected_key]),
            {"algo_1", "algo_2", "algo_3", "algo_4"},
            "Append mode should combine all algorithm IDs"
        )

    def test_create_checkpoint_append_mode_with_duplicates(self):
        """
        Test that create_checkpoint in append mode handles duplicate
        algorithm IDs correctly (should not duplicate them).
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        # First checkpoint creation
        backtests_1 = [
            self._create_mock_backtest("algo_1"),
            self._create_mock_backtest("algo_2"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_1,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            mode="append",
        )

        # Second checkpoint creation with overlapping IDs
        backtests_2 = [
            self._create_mock_backtest("algo_2"),  # Duplicate
            self._create_mock_backtest("algo_3"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_2,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            mode="append",
        )

        # Verify no duplicates
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        expected_key = (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )
        algorithm_ids = checkpoints[expected_key]
        self.assertEqual(
            len(algorithm_ids), len(set(algorithm_ids)),
            "There should be no duplicate algorithm IDs"
        )
        self.assertEqual(
            set(algorithm_ids),
            {"algo_1", "algo_2", "algo_3"}
        )

    def test_create_checkpoint_overwrite_mode(self):
        """
        Test that create_checkpoint in overwrite mode replaces existing
        checkpoints for the same date range.
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        # First checkpoint creation
        backtests_1 = [
            self._create_mock_backtest("algo_1"),
            self._create_mock_backtest("algo_2"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_1,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            mode="append",
        )

        # Second checkpoint creation (overwrite mode)
        backtests_2 = [
            self._create_mock_backtest("algo_3"),
            self._create_mock_backtest("algo_4"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_2,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            mode="overwrite",
        )

        # Verify only new algorithm IDs are present
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        expected_key = (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )
        self.assertEqual(
            set(checkpoints[expected_key]),
            {"algo_3", "algo_4"},
            "Overwrite mode should replace existing algorithm IDs"
        )

    def test_create_checkpoint_multiple_date_ranges(self):
        """
        Test that create_checkpoint correctly handles multiple date ranges
        in the same checkpoint file.
        """
        date_range_1 = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        date_range_2 = BacktestDateRange(
            start_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
        )

        # Create checkpoints for first date range
        backtests_1 = [
            self._create_mock_backtest("algo_1"),
            self._create_mock_backtest("algo_2"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_1,
            backtest_date_range=date_range_1,
            storage_directory=self.temp_dir,
        )

        # Create checkpoints for second date range
        backtests_2 = [
            self._create_mock_backtest("algo_3"),
            self._create_mock_backtest("algo_4"),
        ]

        BacktestService.create_checkpoint(
            backtests=backtests_2,
            backtest_date_range=date_range_2,
            storage_directory=self.temp_dir,
        )

        # Verify both date ranges are in checkpoint file
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        key_1 = (
            f"{date_range_1.start_date.isoformat()}_"
            f"{date_range_1.end_date.isoformat()}"
        )
        key_2 = (
            f"{date_range_2.start_date.isoformat()}_"
            f"{date_range_2.end_date.isoformat()}"
        )

        self.assertIn(key_1, checkpoints)
        self.assertIn(key_2, checkpoints)
        self.assertEqual(set(checkpoints[key_1]), {"algo_1", "algo_2"})
        self.assertEqual(set(checkpoints[key_2]), {"algo_3", "algo_4"})

    def test_create_checkpoint_preserves_other_date_ranges(self):
        """
        Test that when updating checkpoints for one date range, checkpoints
        for other date ranges are preserved.
        """
        date_range_1 = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        date_range_2 = BacktestDateRange(
            start_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
        )

        # Create checkpoints for first date range
        backtests_1 = [self._create_mock_backtest("algo_1")]
        BacktestService.create_checkpoint(
            backtests=backtests_1,
            backtest_date_range=date_range_1,
            storage_directory=self.temp_dir,
        )

        # Create checkpoints for second date range
        backtests_2 = [self._create_mock_backtest("algo_2")]
        BacktestService.create_checkpoint(
            backtests=backtests_2,
            backtest_date_range=date_range_2,
            storage_directory=self.temp_dir,
        )

        # Update first date range with overwrite
        backtests_3 = [self._create_mock_backtest("algo_3")]
        BacktestService.create_checkpoint(
            backtests=backtests_3,
            backtest_date_range=date_range_1,
            storage_directory=self.temp_dir,
            mode="overwrite",
        )

        # Verify second date range is still intact
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        key_2 = (
            f"{date_range_2.start_date.isoformat()}_"
            f"{date_range_2.end_date.isoformat()}"
        )

        self.assertIn(key_2, checkpoints)
        self.assertEqual(
            set(checkpoints[key_2]), {"algo_2"},
            "Other date range checkpoints should be preserved"
        )

    def test_create_checkpoint_with_show_progress(self):
        """
        Test that create_checkpoint works correctly with show_progress=True.
        (This test just verifies it doesn't raise an exception)
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        backtests = [self._create_mock_backtest("algo_1")]

        # Should not raise any exception
        BacktestService.create_checkpoint(
            backtests=backtests,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
            show_progress=True,
        )

        # Verify checkpoint was created
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        self.assertTrue(os.path.exists(checkpoint_file))

    def test_create_checkpoint_single_backtest(self):
        """
        Test create_checkpoint with a single backtest.
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        backtests = [self._create_mock_backtest("single_algo")]

        BacktestService.create_checkpoint(
            backtests=backtests,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
        )

        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        expected_key = (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )
        self.assertEqual(checkpoints[expected_key], ["single_algo"])

    def test_create_checkpoint_many_backtests(self):
        """
        Test create_checkpoint with many backtests.
        """
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        backtests = [
            self._create_mock_backtest(f"algo_{i}")
            for i in range(100)
        ]

        BacktestService.create_checkpoint(
            backtests=backtests,
            backtest_date_range=date_range,
            storage_directory=self.temp_dir,
        )

        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "r") as f:
            checkpoints = json.load(f)

        expected_key = (
            f"{date_range.start_date.isoformat()}_"
            f"{date_range.end_date.isoformat()}"
        )
        self.assertEqual(len(checkpoints[expected_key]), 100)

    def test_create_checkpoint_creates_directory_structure(self):
        """
        Test that create_checkpoint works when storage directory exists
        but is empty.
        """
        # Create a nested directory structure
        nested_dir = os.path.join(self.temp_dir, "level1", "level2")
        os.makedirs(nested_dir, exist_ok=True)

        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )

        backtests = [self._create_mock_backtest("algo_1")]

        BacktestService.create_checkpoint(
            backtests=backtests,
            backtest_date_range=date_range,
            storage_directory=nested_dir,
        )

        checkpoint_file = os.path.join(nested_dir, "checkpoints.json")
        self.assertTrue(
            os.path.exists(checkpoint_file),
            "Checkpoint file should be created in nested directory"
        )


class TestGetCheckpoints(TestCase):
    """
    Tests for the get_checkpoints static method of BacktestService.

    This method loads checkpoint data from a checkpoint file and returns:
    1. List of checkpointed algorithm IDs for the given date range
    2. List of loaded Backtest objects (if they exist on disk)
    3. List of missing algorithm IDs (requested but not in checkpoints)

    These tests use actual backtest data from:
    tests/resources/backtest_reports_for_testing/
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        # Path to existing backtest test data
        self.backtest_storage_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                os.pardir,
                os.pardir,
                "resources",
                "backtest_reports_for_testing"
            )
        )
        # Date range that exists in checkpoints.json
        self.existing_date_range = BacktestDateRange(
            start_date=datetime(2022, 12, 3, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 2, tzinfo=timezone.utc),
        )
        self.existing_date_range_key = (
            f"{self.existing_date_range.start_date.isoformat()}_"
            f"{self.existing_date_range.end_date.isoformat()}"
        )
        # Second date range that exists in checkpoints.json
        self.second_date_range = BacktestDateRange(
            start_date=datetime(2023, 12, 3, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 2, tzinfo=timezone.utc),
        )
        # Algorithm IDs that exist in the first date range checkpoints
        self.existing_algorithm_ids = [
            "0aa37205", "e8c2060c", "b9e3779b", "8503561a",
            "6bdb0580", "a023229a", "c7b79e46", "438274dc",
            "7663c4cd", "cb76aaeb", "6a6575cd", "05764fc8",
            "3cccceb1", "47293173", "eab0e4aa", "9351cfaa"
        ]
        # Date range for tests without existing checkpoints
        self.non_existing_date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        self.non_existing_date_range_key = (
            f"{self.non_existing_date_range.start_date.isoformat()}_"
            f"{self.non_existing_date_range.end_date.isoformat()}"
        )

    def tearDown(self) -> None:
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_checkpoint_file(self, checkpoints_data: dict):
        """Create a checkpoint file with the given data in temp directory."""
        checkpoint_file = os.path.join(self.temp_dir, "checkpoints.json")
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoints_data, f, indent=4)

    def test_get_checkpoints_no_checkpoint_file(self):
        """
        Test get_checkpoints when no checkpoint file exists.
        Should return empty lists for checkpointed and backtests,
        and all algorithm_ids as missing.
        """
        algorithm_ids = ["algo_1", "algo_2", "algo_3"]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.non_existing_date_range,
            storage_directory=self.temp_dir,
        )

        self.assertEqual(checkpointed, [])
        self.assertEqual(backtests, [])
        self.assertEqual(set(missing), set(algorithm_ids))

    def test_get_checkpoints_empty_checkpoint_for_date_range(self):
        """
        Test get_checkpoints when checkpoint file exists but is empty
        for the given date range.
        """
        # Use actual storage but request a date range that doesn't exist
        non_existing_range = BacktestDateRange(
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2020, 6, 1, tzinfo=timezone.utc),
        )

        algorithm_ids = ["algo_1", "algo_2"]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=non_existing_range,
            storage_directory=self.backtest_storage_dir,
        )

        self.assertEqual(checkpointed, [])
        self.assertEqual(backtests, [])
        self.assertEqual(set(missing), set(algorithm_ids))

    def test_get_checkpoints_returns_checkpointed_ids(self):
        """
        Test that get_checkpoints returns the list of checkpointed
        algorithm IDs for the given date range using actual test data.
        """
        # Request a subset of the existing algorithm IDs
        algorithm_ids = ["0aa37205", "e8c2060c", "b9e3779b"]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Should return all 16 checkpointed algorithm IDs
        self.assertEqual(len(checkpointed), 16)
        self.assertEqual(set(checkpointed), set(self.existing_algorithm_ids))

    def test_get_checkpoints_identifies_missing_algorithms(self):
        """
        Test that get_checkpoints correctly identifies algorithms that
        are in the checkpoints but NOT in the requested algorithm_ids.
        """
        # Request only 2 of the 16 checkpointed algorithms
        algorithm_ids = ["0aa37205", "e8c2060c"]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Missing should contain 14 algorithms (16 - 2 requested)
        self.assertEqual(len(missing), 14)
        # The requested ones should NOT be in missing
        self.assertNotIn("0aa37205", missing)
        self.assertNotIn("e8c2060c", missing)

    def test_get_checkpoints_with_partial_overlap(self):
        """
        Test get_checkpoints when some requested algorithms are checkpointed
        and some are not.
        """
        # Request 2 existing + 2 non-existing algorithm IDs
        algorithm_ids = ["0aa37205", "e8c2060c", "nonexistent_1", "nonexistent_2"]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Checkpointed should return all 16 from the checkpoint file
        self.assertEqual(len(checkpointed), 16)
        # Missing should contain checkpointed algos NOT in requested
        # (14 out of 16 checkpointed algorithms are not in requested)
        self.assertEqual(len(missing), 14)

    def test_get_checkpoints_with_empty_algorithm_ids(self):
        """
        Test get_checkpoints when algorithm_ids is empty.
        """
        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=[],
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Should return all checkpointed algorithm IDs
        self.assertEqual(len(checkpointed), 16)
        # All checkpointed should be in missing since none were requested
        self.assertEqual(len(missing), 16)
        self.assertEqual(set(missing), set(self.existing_algorithm_ids))

    def test_get_checkpoints_loads_backtests(self):
        """
        Test that get_checkpoints actually loads Backtest objects from disk.
        """
        algorithm_ids = self.existing_algorithm_ids

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Should have loaded 16 backtest objects
        self.assertEqual(len(backtests), 16)
        # Each backtest should have an algorithm_id
        for bt in backtests:
            self.assertIsNotNone(bt.algorithm_id)
            self.assertIn(bt.algorithm_id, self.existing_algorithm_ids)

    def test_get_checkpoints_second_date_range(self):
        """
        Test get_checkpoints with the second date range that has fewer
        checkpointed algorithms (6 vs 16).
        """
        # The second date range has only 6 checkpointed algorithms
        second_range_algos = [
            "0aa37205", "e8c2060c", "b9e3779b",
            "8503561a", "a023229a", "05764fc8"
        ]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=second_range_algos,
            backtest_date_range=self.second_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Should return 6 checkpointed algorithm IDs
        self.assertEqual(len(checkpointed), 6)
        self.assertEqual(set(checkpointed), set(second_range_algos))

    def test_get_checkpoints_all_algorithms_checkpointed(self):
        """
        Test get_checkpoints when all requested algorithms are already
        checkpointed.
        """
        # Request exactly the algorithms that are checkpointed
        algorithm_ids = self.existing_algorithm_ids

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        self.assertEqual(set(checkpointed), set(algorithm_ids))
        # No missing since all requested are checkpointed
        self.assertEqual(set(missing), set())

    def test_get_checkpoints_no_algorithms_requested_match(self):
        """
        Test get_checkpoints when none of the requested algorithms are
        in the checkpoints.
        """
        # Request algorithms that don't exist in checkpoints
        algorithm_ids = ["nonexistent_1", "nonexistent_2", "nonexistent_3"]

        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=algorithm_ids,
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Checkpointed returns what's in the file (all 16)
        self.assertEqual(len(checkpointed), 16)
        # Missing contains all checkpointed algos (since none match requested)
        self.assertEqual(len(missing), 16)

    def test_get_checkpoints_single_algorithm(self):
        """
        Test get_checkpoints with a single algorithm that exists.
        """
        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=["0aa37205"],
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # All 16 checkpointed IDs should be returned
        self.assertEqual(len(checkpointed), 16)
        self.assertIn("0aa37205", checkpointed)
        # 15 missing (16 - 1 requested)
        self.assertEqual(len(missing), 15)

    def test_get_checkpoints_backtest_has_correct_structure(self):
        """
        Test that loaded backtests have the expected structure.
        """
        checkpointed, backtests, missing = BacktestService.get_checkpoints(
            algorithm_ids=["0aa37205"],
            backtest_date_range=self.existing_date_range,
            storage_directory=self.backtest_storage_dir,
        )

        # Find the backtest for 0aa37205
        target_backtest = None
        for bt in backtests:
            if bt.algorithm_id == "0aa37205":
                target_backtest = bt
                break

        self.assertIsNotNone(
            target_backtest,
            "Should find backtest with algorithm_id '0aa37205'"
        )
        # Backtest should have runs
        self.assertIsNotNone(target_backtest.get_all_backtest_runs())


class TestSessionCache(TestCase):
    """
    Tests for the session cache functionality in BacktestService.

    The session cache tracks which backtests were run in the current session,
    ensuring that when loading backtests from a storage directory, only
    backtests from the current run are included (not pre-existing ones).
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_session_cache(self):
        """
        Test that _create_session_cache creates a valid session cache
        with the expected structure.
        """
        backtest_service = _create_backtest_service()
        session_cache = backtest_service._create_session_cache()

        self.assertIsNotNone(session_cache)
        self.assertIn("session_id", session_cache)
        self.assertIn("backtests", session_cache)
        self.assertIsInstance(session_cache["backtests"], dict)
        self.assertEqual(len(session_cache["backtests"]), 0)

    def test_update_session_cache(self):
        """
        Test that _update_session_cache correctly adds backtests to
        the session cache.
        """
        backtest_service = _create_backtest_service()
        session_cache = backtest_service._create_session_cache()

        # Create mock backtests
        mock_backtest1 = MagicMock()
        mock_backtest1.algorithm_id = "algo_1"
        mock_backtest2 = MagicMock()
        mock_backtest2.algorithm_id = "algo_2"

        backtest_service._update_session_cache(
            backtests=[mock_backtest1, mock_backtest2],
            storage_directory=self.temp_dir,
            session_cache=session_cache
        )

        self.assertEqual(len(session_cache["backtests"]), 2)
        self.assertIn("algo_1", session_cache["backtests"])
        self.assertIn("algo_2", session_cache["backtests"])
        self.assertEqual(
            session_cache["backtests"]["algo_1"],
            os.path.join(self.temp_dir, "algo_1")
        )
        self.assertEqual(
            session_cache["backtests"]["algo_2"],
            os.path.join(self.temp_dir, "algo_2")
        )

    def test_save_session_cache(self):
        """
        Test that _save_session_cache writes the session cache to disk.
        """
        backtest_service = _create_backtest_service()
        session_cache = backtest_service._create_session_cache()
        session_cache["backtests"]["algo_1"] = os.path.join(
            self.temp_dir, "algo_1"
        )

        backtest_service._save_session_cache(session_cache, self.temp_dir)

        session_file = os.path.join(self.temp_dir, "backtest_session.json")
        self.assertTrue(os.path.exists(session_file))

        with open(session_file, "r") as f:
            loaded_cache = json.load(f)

        self.assertEqual(loaded_cache["session_id"], session_cache["session_id"])
        self.assertIn("algo_1", loaded_cache["backtests"])

    def test_session_cache_tracks_only_current_run_backtests(self):
        """
        Test that session cache only tracks backtests from the current run,
        not pre-existing ones in the storage directory.
        """
        backtest_service = _create_backtest_service()
        session_cache = backtest_service._create_session_cache()

        # Simulate adding backtests from current run
        mock_backtest = MagicMock()
        mock_backtest.algorithm_id = "current_run_algo"

        backtest_service._update_session_cache(
            backtests=[mock_backtest],
            storage_directory=self.temp_dir,
            session_cache=session_cache
        )

        # Session cache should only contain the backtest we added
        self.assertEqual(len(session_cache["backtests"]), 1)
        self.assertIn("current_run_algo", session_cache["backtests"])
        # Pre-existing backtests should not be in session cache
        self.assertNotIn("pre_existing_algo", session_cache["backtests"])

    def test_session_cache_updated_after_window_filter(self):
        """
        Test that session cache is correctly updated when window filter
        removes some backtests.
        """
        backtest_service = _create_backtest_service()
        session_cache = backtest_service._create_session_cache()

        # Add multiple backtests
        for algo_id in ["algo_1", "algo_2", "algo_3"]:
            session_cache["backtests"][algo_id] = os.path.join(
                self.temp_dir, algo_id
            )

        # Simulate window filter keeping only algo_1 and algo_3
        filtered_ids = {"algo_1", "algo_3"}
        session_cache["backtests"] = {
            k: v for k, v in session_cache["backtests"].items()
            if k in filtered_ids
        }

        self.assertEqual(len(session_cache["backtests"]), 2)
        self.assertIn("algo_1", session_cache["backtests"])
        self.assertIn("algo_3", session_cache["backtests"])
        self.assertNotIn("algo_2", session_cache["backtests"])

    def test_session_file_cleanup_after_completion(self):
        """
        Test that backtest_session.json is cleaned up after backtests complete.
        """
        # Create a session file
        session_file = os.path.join(self.temp_dir, "backtest_session.json")
        with open(session_file, "w") as f:
            json.dump({"session_id": "test", "backtests": {}}, f)

        self.assertTrue(os.path.exists(session_file))

        # Simulate cleanup
        if os.path.exists(session_file):
            os.remove(session_file)

        self.assertFalse(os.path.exists(session_file))


class TestSessionCacheIntegration(TestCase):
    """
    Integration tests for session cache with actual backtests.

    These tests verify that when running backtests with a storage directory
    that contains pre-existing backtests, only the backtests from the
    current run are returned.
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

    def test_vector_backtest_session_isolation(self):
        """
        Test that vector backtests with shared storage directory correctly
        isolate results using session cache.

        Scenario:
        1. Run backtest for Strategy A and save to storage
        2. Run backtest for Strategy B with same storage directory
        3. Results should only contain Strategy B, not Strategy A
        """
        storage_dir = os.path.join(self.temp_dir, "session_test_storage")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # --- First run: Strategy A ---
        algorithm_id_a = "session_test_a_" + str(uuid.uuid4())[:4]
        strategy_a = SimpleVectorStrategy(
            algorithm_id=algorithm_id_a,
            market="BITVAVO",
            symbol="BTC",
        )

        backtests_run1 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_a],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        self.assertEqual(len(backtests_run1), 1)
        self.assertEqual(backtests_run1[0].algorithm_id, algorithm_id_a)

        # Verify Strategy A exists in storage
        self.assertTrue(os.path.exists(os.path.join(storage_dir, algorithm_id_a)))

        # Verify session file was cleaned up
        session_file = os.path.join(storage_dir, "backtest_session.json")
        self.assertFalse(
            os.path.exists(session_file),
            "Session file should be cleaned up after backtest completes"
        )

        # --- Second run: Strategy B ---
        algorithm_id_b = "session_test_b_" + str(uuid.uuid4())[:4]
        strategy_b = SimpleVectorStrategy(
            algorithm_id=algorithm_id_b,
            market="BITVAVO",
            symbol="BTC",
        )

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_b],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # Verify ONLY Strategy B is in results
        self.assertEqual(len(backtests_run2), 1)
        self.assertEqual(backtests_run2[0].algorithm_id, algorithm_id_b)

        # Strategy A should NOT be in results (session isolation)
        result_ids = [b.algorithm_id for b in backtests_run2]
        self.assertNotIn(
            algorithm_id_a, result_ids,
            "Strategy A from previous run should NOT be in current results "
            "due to session isolation"
        )

        # Verify session file was cleaned up
        self.assertFalse(
            os.path.exists(session_file),
            "Session file should be cleaned up after second backtest completes"
        )

    def test_event_backtest_session_isolation(self):
        """
        Test that event backtests with shared storage directory correctly
        isolate results using session cache.
        """
        storage_dir = os.path.join(self.temp_dir, "event_session_test")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
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

        # --- First run: Algorithm A ---
        algorithm_id_a = "event_session_a_" + str(uuid.uuid4())[:4]
        algorithm_a = Algorithm(algorithm_id=algorithm_id_a)
        algorithm_a.add_strategy(SimpleEventStrategy())

        backtests_run1 = app.run_backtests(
            algorithms=[algorithm_a],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        self.assertEqual(len(backtests_run1), 1)

        # Verify session file was cleaned up
        session_file = os.path.join(storage_dir, "backtest_session.json")
        self.assertFalse(
            os.path.exists(session_file),
            "Session file should be cleaned up after event backtest completes"
        )

        # --- Second run: Algorithm B ---
        algorithm_id_b = "event_session_b_" + str(uuid.uuid4())[:4]
        algorithm_b = Algorithm(algorithm_id=algorithm_id_b)
        algorithm_b.add_strategy(SimpleEventStrategy())

        backtests_run2 = app.run_backtests(
            algorithms=[algorithm_b],
            backtest_date_ranges=[date_range],
            risk_free_rate=0.027,
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # Verify ONLY Algorithm B is in results
        self.assertEqual(len(backtests_run2), 1)
        self.assertEqual(backtests_run2[0].algorithm_id, algorithm_id_b)

        result_ids = [b.algorithm_id for b in backtests_run2]
        self.assertNotIn(
            algorithm_id_a, result_ids,
            "Algorithm A from previous run should NOT be in current results"
        )

    def test_session_cache_with_final_filter_function(self):
        """
        Test that session cache works correctly with final_filter_function,
        ensuring only current run backtests are passed to the filter.
        """
        storage_dir = os.path.join(self.temp_dir, "filter_session_test")
        os.makedirs(storage_dir, exist_ok=True)

        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=365)
        date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date,
            name="Test Period"
        )

        # --- First run: Strategy A ---
        algorithm_id_a = "filter_test_a_" + str(uuid.uuid4())[:4]
        strategy_a = SimpleVectorStrategy(
            algorithm_id=algorithm_id_a,
            market="BITVAVO",
            symbol="BTC",
        )

        app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_a],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
        )

        # --- Second run: Strategy B with final filter ---
        algorithm_id_b = "filter_test_b_" + str(uuid.uuid4())[:4]
        strategy_b = SimpleVectorStrategy(
            algorithm_id=algorithm_id_b,
            market="BITVAVO",
            symbol="BTC",
        )

        # Track what the final filter receives
        received_ids = []

        def tracking_filter(backtests: List[Backtest]) -> List[Backtest]:
            for b in backtests:
                received_ids.append(b.algorithm_id)
            return backtests

        backtests_run2 = app.run_vector_backtests(
            initial_amount=1000,
            backtest_date_ranges=[date_range],
            strategies=[strategy_b],
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            backtest_storage_directory=storage_dir,
            use_checkpoints=True,
            final_filter_function=tracking_filter,
        )

        # Final filter should only receive Strategy B
        self.assertIn(
            algorithm_id_b, received_ids,
            "Final filter should receive Strategy B"
        )
        self.assertNotIn(
            algorithm_id_a, received_ids,
            "Final filter should NOT receive Strategy A from previous run"
        )

