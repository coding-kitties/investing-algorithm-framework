from unittest import TestCase

from investing_algorithm_framework.domain.models.data.data_source import (
    DataSource,
)
from investing_algorithm_framework.domain.models.data.data_type import (
    DataType,
)
from investing_algorithm_framework.domain.models.time_frame import TimeFrame
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_backtest_service import VectorBacktestService


class TestGetMostGranularOhlcvDataSource(TestCase):
    """Test that get_most_granular_ohlcv_data_source handles all TimeFrame
    members, including SIX_HOUR, EIGHT_HOUR, THREE_DAY that were previously
    missing (GitHub issue #417)."""

    def _make_source(self, time_frame):
        return DataSource(
            identifier=f"TEST/{time_frame.value}",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame=time_frame,
            market="BITVAVO",
        )

    def test_six_hour_does_not_raise(self):
        sources = [
            self._make_source(TimeFrame.ONE_DAY),
            self._make_source(TimeFrame.SIX_HOUR),
        ]
        result = VectorBacktestService.get_most_granular_ohlcv_data_source(
            sources
        )
        self.assertEqual(result.time_frame, TimeFrame.SIX_HOUR)

    def test_eight_hour_does_not_raise(self):
        sources = [
            self._make_source(TimeFrame.ONE_DAY),
            self._make_source(TimeFrame.EIGHT_HOUR),
        ]
        result = VectorBacktestService.get_most_granular_ohlcv_data_source(
            sources
        )
        self.assertEqual(result.time_frame, TimeFrame.EIGHT_HOUR)

    def test_three_day_does_not_raise(self):
        sources = [
            self._make_source(TimeFrame.ONE_WEEK),
            self._make_source(TimeFrame.THREE_DAY),
        ]
        result = VectorBacktestService.get_most_granular_ohlcv_data_source(
            sources
        )
        self.assertEqual(result.time_frame, TimeFrame.THREE_DAY)

    def test_thirty_minute_does_not_raise(self):
        sources = [
            self._make_source(TimeFrame.ONE_HOUR),
            self._make_source(TimeFrame.THIRTY_MINUTE),
        ]
        result = VectorBacktestService.get_most_granular_ohlcv_data_source(
            sources
        )
        self.assertEqual(result.time_frame, TimeFrame.THIRTY_MINUTE)

    def test_most_granular_among_all_new_timeframes(self):
        """SIX_HOUR < EIGHT_HOUR < TWELVE_HOUR in granularity rank."""
        sources = [
            self._make_source(TimeFrame.TWELVE_HOUR),
            self._make_source(TimeFrame.EIGHT_HOUR),
            self._make_source(TimeFrame.SIX_HOUR),
        ]
        result = VectorBacktestService.get_most_granular_ohlcv_data_source(
            sources
        )
        self.assertEqual(result.time_frame, TimeFrame.SIX_HOUR)

    def test_ordering_preserved(self):
        """Verify 4h is more granular than 6h which is more granular
        than 8h."""
        sources = [
            self._make_source(TimeFrame.EIGHT_HOUR),
            self._make_source(TimeFrame.SIX_HOUR),
            self._make_source(TimeFrame.FOUR_HOUR),
        ]
        result = VectorBacktestService.get_most_granular_ohlcv_data_source(
            sources
        )
        self.assertEqual(result.time_frame, TimeFrame.FOUR_HOUR)
