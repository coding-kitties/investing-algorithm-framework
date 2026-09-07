"""Regression tests for issue #602 / PR #607.

``OHLCVDataProviderBase.get_backtest_data`` used to crash with

    TypeError: unsupported operand type(s) for -: 'NoneType'
    and 'datetime.timedelta'

whenever the vectorized backtest path called it without a
``backtest_index_date`` while ``window_size`` was set.

The vectorized path (``DataProviderService.get_vectorized_backtest_data``)
only passes ``start_date`` / ``end_date``. It already applies warmup
padding upstream via ``DataSource.create_start_date_data``, so no trailing
window should be applied there; the event-driven path always passes a
concrete ``backtest_index_date`` and keeps its trailing-window behavior.

These tests exercise the real ``OHLCVDataProviderBase`` implementation
through a minimal concrete subclass and pin the slicing behavior of both
paths.
"""
from datetime import datetime, timedelta, timezone
from unittest import TestCase

import polars as pl

from investing_algorithm_framework.infrastructure import (
    OHLCVDataProviderBase,
)


def _make_data(rows: int = 10) -> pl.DataFrame:
    """Create 10 daily OHLCV bars from 2024-01-01 to 2024-01-10."""
    return pl.DataFrame(
        {
            "Datetime": [
                datetime(2024, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=i)
                for i in range(rows)
            ],
            "Open": [100.0 + i for i in range(rows)],
            "High": [105.0 + i for i in range(rows)],
            "Low": [95.0 + i for i in range(rows)],
            "Close": [102.0 + i for i in range(rows)],
            "Volume": [1000000 + i for i in range(rows)],
        }
    )


def _utc_naive(dt: datetime) -> datetime:
    """Normalize to naive UTC so comparisons are polars-version agnostic."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _expected_dates(start_day: int, end_day: int) -> list:
    return [
        datetime(2024, 1, day) for day in range(start_day, end_day + 1)
    ]


class _StubOHLCVProvider(OHLCVDataProviderBase):
    """Minimal concrete subclass to exercise the real base-class logic."""

    market_name = "STUB"
    data_provider_identifier = "stub_ohlcv"
    timeframe_map = {"1d": "1d"}

    def _download_ohlcv(self, symbol, time_frame, start_date, end_date):
        raise AssertionError("_download_ohlcv must not be called")


class TestGetBacktestDataMissingIndexDate(TestCase):
    """Regression tests for #602 / #607."""

    def _provider(self, window_size=None) -> _StubOHLCVProvider:
        provider = _StubOHLCVProvider(
            time_frame="1d", window_size=window_size
        )
        provider.data = _make_data()
        return provider

    def _dates(self, data) -> list:
        return [_utc_naive(dt) for dt in data["Datetime"].to_list()]

    # -- vectorized path: backtest_index_date is None ---------------

    def test_vectorized_path_with_window_size_returns_full_range(self):
        """No trailing window is applied when the index date is missing.

        Previously this raised ``TypeError: unsupported operand
        type(s) for -: 'NoneType' and 'datetime.timedelta'``.
        """
        provider = self._provider(window_size=3)

        data = provider.get_backtest_data(
            backtest_index_date=None,
            backtest_start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            backtest_end_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(self._dates(data), _expected_dates(1, 10))

    def test_vectorized_path_without_window_size_returns_rows(self):
        provider = self._provider(window_size=None)

        data = provider.get_backtest_data(
            backtest_index_date=None,
            backtest_start_date=datetime(2024, 1, 4, tzinfo=timezone.utc),
            backtest_end_date=datetime(2024, 1, 7, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(self._dates(data), _expected_dates(4, 7))

    def test_vectorized_path_falls_back_to_latest_data_point(self):
        """Without an end date, the upper bound is the latest data point."""
        provider = self._provider(window_size=3)

        data = provider.get_backtest_data(
            backtest_index_date=None,
            backtest_start_date=datetime(2024, 1, 8, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(self._dates(data), _expected_dates(8, 10))

    # -- event-driven path: backtest_index_date is set --------------

    def test_event_driven_path_with_window_size_is_unchanged(self):
        """Trailing-window slicing still applies on the event path."""
        provider = self._provider(window_size=3)

        data = provider.get_backtest_data(
            backtest_index_date=datetime(2024, 1, 6, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(self._dates(data), _expected_dates(3, 6))

    def test_event_driven_path_without_window_size_is_unchanged(self):
        """Event path without a window slices [start, index date]."""
        provider = self._provider(window_size=None)

        data = provider.get_backtest_data(
            backtest_index_date=datetime(2024, 1, 5, tzinfo=timezone.utc),
            backtest_start_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        self.assertIsInstance(data, pl.DataFrame)
        self.assertEqual(self._dates(data), _expected_dates(2, 5))
