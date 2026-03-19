"""
Tests for the scheduling interval vs OHLCV data timeframe validation
added in TradingStrategy.__init__ (issue #396).

The validation raises OperationalException when the strategy's scheduling
interval (time_unit.amount_of_minutes * interval) is strictly less than
the smallest OHLCV data source timeframe.
"""
from unittest import TestCase

from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.domain import (
    OperationalException, TimeUnit, DataType, TimeFrame,
)
from investing_algorithm_framework.domain.models.data.data_source import (
    DataSource,
)


class _ConcreteStrategy(TradingStrategy):
    """Minimal concrete subclass for testing __init__ validation."""

    def run_strategy(self, context, data):
        pass


class TestStrategyIntervalValidation(TestCase):

    # ------------------------------------------------------------------
    # 1. Should raise when interval is faster than the OHLCV timeframe
    # ------------------------------------------------------------------
    def test_raises_when_interval_faster_than_ohlcv_timeframe(self):
        """1 minute interval < 60 minute (1h) OHLCV → must raise."""
        with self.assertRaises(OperationalException):
            _ConcreteStrategy(
                time_unit=TimeUnit.MINUTE,
                interval=1,
                data_sources=[
                    DataSource(
                        symbol="BTC/EUR",
                        data_type=DataType.OHLCV,
                        time_frame=TimeFrame.ONE_HOUR,
                        market="BITVAVO",
                        warmup_window=100,
                    )
                ],
            )

    # ------------------------------------------------------------------
    # 2. No error when interval exactly matches the OHLCV timeframe
    # ------------------------------------------------------------------
    def test_no_error_when_interval_matches_ohlcv_timeframe(self):
        """1 hour interval == 60 min == 1h OHLCV → should NOT raise."""
        strategy = _ConcreteStrategy(
            time_unit=TimeUnit.HOUR,
            interval=1,
            data_sources=[
                DataSource(
                    symbol="BTC/EUR",
                    data_type=DataType.OHLCV,
                    time_frame=TimeFrame.ONE_HOUR,
                    market="BITVAVO",
                    warmup_window=100,
                )
            ],
        )
        self.assertIsNotNone(strategy)

    # ------------------------------------------------------------------
    # 3. No error when interval is slower than the OHLCV timeframe
    # ------------------------------------------------------------------
    def test_no_error_when_interval_slower_than_ohlcv_timeframe(self):
        """1 day interval (1440 min) > 60 min (1h) OHLCV → should NOT raise."""
        strategy = _ConcreteStrategy(
            time_unit=TimeUnit.DAY,
            interval=1,
            data_sources=[
                DataSource(
                    symbol="BTC/EUR",
                    data_type=DataType.OHLCV,
                    time_frame=TimeFrame.ONE_HOUR,
                    market="BITVAVO",
                    warmup_window=100,
                )
            ],
        )
        self.assertIsNotNone(strategy)

    # ------------------------------------------------------------------
    # 4. Validation uses the *smallest* OHLCV timeframe among sources
    # ------------------------------------------------------------------
    def test_uses_smallest_ohlcv_timeframe_for_validation(self):
        """5 min interval < 15 min (smallest OHLCV) → must raise."""
        with self.assertRaises(OperationalException):
            _ConcreteStrategy(
                time_unit=TimeUnit.MINUTE,
                interval=5,
                data_sources=[
                    DataSource(
                        symbol="BTC/EUR",
                        data_type=DataType.OHLCV,
                        time_frame=TimeFrame.ONE_HOUR,
                        market="BITVAVO",
                        warmup_window=100,
                    ),
                    DataSource(
                        symbol="ETH/EUR",
                        data_type=DataType.OHLCV,
                        time_frame=TimeFrame.FIFTEEN_MINUTE,
                        market="BITVAVO",
                        warmup_window=100,
                    ),
                ],
            )

    # ------------------------------------------------------------------
    # 5. No validation when there are no OHLCV data sources at all
    # ------------------------------------------------------------------
    def test_no_validation_when_no_ohlcv_data_sources(self):
        """No OHLCV sources → nothing to compare → should NOT raise."""
        strategy = _ConcreteStrategy(
            time_unit=TimeUnit.MINUTE,
            interval=1,
            data_sources=[],
        )
        self.assertIsNotNone(strategy)

    # ------------------------------------------------------------------
    # 6. Non-OHLCV sources (no time_frame) are skipped
    # ------------------------------------------------------------------
    def test_skips_data_sources_without_timeframe(self):
        """Ticker source has no time_frame → should NOT raise."""
        strategy = _ConcreteStrategy(
            time_unit=TimeUnit.MINUTE,
            interval=1,
            data_sources=[
                DataSource(
                    symbol="BTC/EUR",
                    data_type=DataType.TICKER,
                    market="BITVAVO",
                )
            ],
        )
        self.assertIsNotNone(strategy)

    # ------------------------------------------------------------------
    # 7. Error message is descriptive
    # ------------------------------------------------------------------
    def test_raises_with_descriptive_error_message(self):
        """Exception message should mention interval and timeframe."""
        with self.assertRaises(OperationalException) as cm:
            _ConcreteStrategy(
                time_unit=TimeUnit.MINUTE,
                interval=1,
                data_sources=[
                    DataSource(
                        symbol="BTC/EUR",
                        data_type=DataType.OHLCV,
                        time_frame=TimeFrame.ONE_HOUR,
                        market="BITVAVO",
                        warmup_window=100,
                    )
                ],
            )

        msg = str(cm.exception)
        # Verify scheduling interval info is present
        self.assertIn("1 min", msg)
        # Verify OHLCV timeframe info is present
        self.assertIn("60 min", msg)
