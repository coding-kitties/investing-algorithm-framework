import unittest
from datetime import datetime, timezone

import pandas as pd

from investing_algorithm_framework.analysis.backtest_data_ranges import (
    generate_rolling_backtest_windows,
    select_backtest_date_ranges
)
from investing_algorithm_framework.domain import BacktestDateRange, \
    OperationalException


class TestGenerateRollingBacktestWindows(unittest.TestCase):
    """Tests for the generate_rolling_backtest_windows function."""

    def test_basic_window_generation(self):
        """Test basic window generation with default parameters."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90
        )

        self.assertGreater(len(windows), 0)

        # Check structure of first window
        first_window = windows[0]
        self.assertIn("train_range", first_window)
        self.assertIn("test_range", first_window)
        self.assertIsInstance(first_window["train_range"], BacktestDateRange)
        self.assertIsInstance(first_window["test_range"], BacktestDateRange)

    def test_train_range_duration(self):
        """Test that train ranges have correct duration."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        train_days = 365

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=train_days,
            test_days=90,
            step_days=90
        )

        for window in windows:
            train_range = window["train_range"]
            duration = (train_range.end_date - train_range.start_date).days
            self.assertEqual(duration, train_days)

    def test_test_range_duration(self):
        """Test that test ranges have correct duration."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        test_days = 90

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=test_days,
            step_days=90
        )

        for window in windows:
            test_range = window["test_range"]
            duration = (test_range.end_date - test_range.start_date).days
            self.assertEqual(duration, test_days)

    def test_gap_days_applied(self):
        """Test that gap_days creates space between train and test."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        gap_days = 30

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90,
            gap_days=gap_days
        )

        for window in windows:
            train_end = window["train_range"].end_date
            test_start = window["test_range"].start_date
            gap = (test_start - train_end).days
            self.assertEqual(gap, gap_days)

    def test_no_gap_days(self):
        """Test that test starts immediately after train when gap_days=0."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90,
            gap_days=0
        )

        for window in windows:
            train_end = window["train_range"].end_date
            test_start = window["test_range"].start_date
            self.assertEqual(train_end, test_start)

    def test_step_days_progression(self):
        """Test that windows progress by step_days."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        step_days = 90

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=step_days
        )

        for i in range(1, len(windows)):
            prev_train_start = windows[i - 1]["train_range"].start_date
            curr_train_start = windows[i]["train_range"].start_date
            step = (curr_train_start - prev_train_start).days
            self.assertEqual(step, step_days)

    def test_window_names_are_unique(self):
        """Test that each window has unique names."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90
        )

        train_names = [w["train_range"].name for w in windows]
        test_names = [w["test_range"].name for w in windows]

        # All names should be unique
        self.assertEqual(len(train_names), len(set(train_names)))
        self.assertEqual(len(test_names), len(set(test_names)))

    def test_window_names_contain_window_number(self):
        """Test that window names contain the window number."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90
        )

        for i, window in enumerate(windows, 1):
            self.assertIn(str(i), window["train_range"].name)
            self.assertIn(str(i), window["test_range"].name)

    def test_test_does_not_exceed_end_date(self):
        """Test that no test window exceeds end_date."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90
        )

        for window in windows:
            self.assertLessEqual(window["test_range"].end_date, end_date)

    def test_empty_result_when_range_too_short(self):
        """Test that empty list is returned when date range is too short."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2021, 6, 1, tzinfo=timezone.utc)  # Only ~150 days

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,  # Needs 365 + 90 = 455 days minimum
            test_days=90,
            step_days=90
        )

        self.assertEqual(len(windows), 0)

    def test_single_window_exact_fit(self):
        """Test generation of exactly one window."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        # 365 train + 90 test = 455 days, end just after that
        end_date = datetime(2022, 5, 1, tzinfo=timezone.utc)  # ~485 days

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90
        )

        self.assertEqual(len(windows), 1)

    def test_custom_train_test_days(self):
        """Test with custom train and test day values."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2022, 12, 31, tzinfo=timezone.utc)
        train_days = 180
        test_days = 30

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=train_days,
            test_days=test_days,
            step_days=30
        )

        self.assertGreater(len(windows), 0)

        # Verify durations
        for window in windows:
            train_duration = (
                window["train_range"].end_date -
                window["train_range"].start_date
            ).days
            test_duration = (
                window["test_range"].end_date -
                window["test_range"].start_date
            ).days
            self.assertEqual(train_duration, train_days)
            self.assertEqual(test_duration, test_days)

    def test_small_step_days_creates_more_windows(self):
        """Test that smaller step_days creates more overlapping windows."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows_large_step = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=180
        )

        windows_small_step = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=30
        )

        self.assertGreater(len(windows_small_step), len(windows_large_step))

    def test_first_train_starts_at_start_date(self):
        """Test that the first train window starts at start_date."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90
        )

        first_train_start = windows[0]["train_range"].start_date
        self.assertEqual(first_train_start, start_date)

    def test_train_ends_before_test_starts(self):
        """Test that train always ends before or when test starts."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90,
            gap_days=0
        )

        for window in windows:
            self.assertLessEqual(
                window["train_range"].end_date,
                window["test_range"].start_date
            )

    def test_with_large_gap_days(self):
        """Test with a large gap between train and test."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        gap_days = 90

        windows = generate_rolling_backtest_windows(
            start_date=start_date,
            end_date=end_date,
            train_days=365,
            test_days=90,
            step_days=90,
            gap_days=gap_days
        )

        self.assertGreater(len(windows), 0)

        for window in windows:
            gap = (
                window["test_range"].start_date -
                window["train_range"].end_date
            ).days
            self.assertEqual(gap, gap_days)

    def test_returns_list_type(self):
        """Test that the return type is always a list."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        result = generate_rolling_backtest_windows(
            start_date=start_date, end_date=end_date,
            train_days=365, test_days=90, step_days=90
        )
        self.assertIsInstance(result, list)

    def test_all_dates_are_timezone_aware(self):
        """Test that returned dates carry timezone info."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        windows = generate_rolling_backtest_windows(
            start_date=start_date, end_date=end_date,
            train_days=180, test_days=30, step_days=30
        )
        for w in windows:
            self.assertIsNotNone(w["train_range"].start_date.tzinfo)
            self.assertIsNotNone(w["test_range"].end_date.tzinfo)

    def test_step_days_equals_one(self):
        """Test with step_days=1 (maximum overlap)."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2021, 9, 1, tzinfo=timezone.utc)
        windows = generate_rolling_backtest_windows(
            start_date=start_date, end_date=end_date,
            train_days=90, test_days=30, step_days=1
        )
        # Should produce many overlapping windows
        self.assertGreater(len(windows), 100)


class TestSelectBacktestDateRanges(unittest.TestCase):
    """Tests for the select_backtest_date_ranges function."""

    @staticmethod
    def _make_trending_up_df():
        """Create a DataFrame with a clear uptrend."""
        dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
        prices = [100 + i * 0.05 for i in range(len(dates))]
        return pd.DataFrame({"Close": prices}, index=dates)

    @staticmethod
    def _make_mixed_df():
        """Create a DataFrame with upturn, downturn and sideways phases."""
        import numpy as np
        dates = pd.date_range("2019-01-01", "2023-12-31", freq="D")
        n = len(dates)
        # Up first year, down second, sideways third, up again fourth+
        prices = []
        price = 100.0
        for i in range(n):
            frac = i / n
            if frac < 0.25:
                price += 0.3  # upturn
            elif frac < 0.50:
                price -= 0.25  # downturn
            elif frac < 0.75:
                price += 0.005 * np.sin(i * 0.5)  # sideways
            else:
                price += 0.15  # mild upturn
            prices.append(price)
        return pd.DataFrame({"Close": prices}, index=dates)

    def test_returns_three_date_ranges(self):
        """select_backtest_date_ranges should return exactly 3 ranges."""
        df = self._make_trending_up_df()
        result = select_backtest_date_ranges(df, window="365D")
        self.assertEqual(len(result), 3)

    def test_returns_backtest_date_range_instances(self):
        """Each returned item should be a BacktestDateRange."""
        df = self._make_trending_up_df()
        result = select_backtest_date_ranges(df, window="365D")
        for item in result:
            self.assertIsInstance(item, BacktestDateRange)

    def test_range_names(self):
        """The three ranges should be named UpTurn, DownTurn, SideWays."""
        df = self._make_mixed_df()
        result = select_backtest_date_ranges(df, window="180D")
        names = [r.name for r in result]
        self.assertIn("UpTurn", names)
        self.assertIn("DownTurn", names)
        self.assertIn("SideWays", names)

    def test_integer_window_parameter(self):
        """Window can be specified as an integer (days)."""
        df = self._make_trending_up_df()
        result = select_backtest_date_ranges(df, window=180)
        self.assertEqual(len(result), 3)

    def test_raises_on_empty_dataframe(self):
        """Should raise OperationalException on empty DataFrame."""
        df = pd.DataFrame({"Close": []})
        df.index = pd.to_datetime([])
        with self.assertRaises(OperationalException):
            select_backtest_date_ranges(df, window="365D")

    def test_raises_when_window_too_large(self):
        """Should raise when window exceeds available data span."""
        dates = pd.date_range("2021-01-01", "2021-06-01", freq="D")
        df = pd.DataFrame(
            {"Close": range(len(dates))}, index=dates
        )
        with self.assertRaises(OperationalException):
            select_backtest_date_ranges(df, window="365D")

    def test_dates_are_timezone_aware(self):
        """Returned date ranges should have timezone-aware dates."""
        df = self._make_trending_up_df()
        result = select_backtest_date_ranges(df, window="180D")
        for r in result:
            self.assertIsNotNone(r.start_date.tzinfo)
            self.assertIsNotNone(r.end_date.tzinfo)

    def test_upturn_has_positive_return(self):
        """The upturn period should have a positive return in the data."""
        df = self._make_mixed_df()
        result = select_backtest_date_ranges(df, window="90D")
        upturn = next(r for r in result if r.name == "UpTurn")
        # The upturn window should have a rising price
        window_df = df[
            (df.index >= upturn.start_date.replace(tzinfo=None))
            & (df.index <= upturn.end_date.replace(tzinfo=None))
        ]
        self.assertGreater(
            window_df["Close"].iloc[-1], window_df["Close"].iloc[0]
        )

    def test_downturn_has_negative_return(self):
        """The downturn period should have a negative return in the data."""
        df = self._make_mixed_df()
        result = select_backtest_date_ranges(df, window="90D")
        downturn = next(r for r in result if r.name == "DownTurn")
        window_df = df[
            (df.index >= downturn.start_date.replace(tzinfo=None))
            & (df.index <= downturn.end_date.replace(tzinfo=None))
        ]
        self.assertLess(
            window_df["Close"].iloc[-1], window_df["Close"].iloc[0]
        )


if __name__ == "__main__":
    unittest.main()

