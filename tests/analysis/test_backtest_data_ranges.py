import unittest
from datetime import datetime, timezone

from investing_algorithm_framework.analysis.backtest_data_ranges import (
    generate_rolling_backtest_windows
)
from investing_algorithm_framework.domain import BacktestDateRange


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


if __name__ == "__main__":
    unittest.main()

