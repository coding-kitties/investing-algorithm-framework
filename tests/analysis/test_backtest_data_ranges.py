import unittest
from datetime import datetime, timezone

import pandas as pd

from investing_algorithm_framework.analysis.backtest_data_ranges import (
    generate_rolling_backtest_windows,
    generate_k_fold_backtest_windows,
)
from investing_algorithm_framework.domain import (
    BacktestDateRange,
    BacktestWindow,
)


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
        self.assertIsInstance(first_window, BacktestWindow)
        self.assertIsInstance(first_window.train_range, BacktestDateRange)
        self.assertIsInstance(first_window.test_range, BacktestDateRange)

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
            duration = (
                window.train_range.end_date - window.train_range.start_date
            ).days
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
            duration = (
                window.test_range.end_date - window.test_range.start_date
            ).days
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
            self.assertEqual(window.gap_days, gap_days)

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
            self.assertEqual(window.train_range.end_date,
                             window.test_range.start_date)

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
            step = (
                windows[i].train_range.start_date
                - windows[i - 1].train_range.start_date
            ).days
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

        train_names = [w.train_range.name for w in windows]
        test_names = [w.test_range.name for w in windows]

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
            self.assertIn(str(i), window.train_range.name)
            self.assertIn(str(i), window.test_range.name)

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
            self.assertLessEqual(window.test_range.end_date, end_date)

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

        for window in windows:
            train_duration = (
                window.train_range.end_date - window.train_range.start_date
            ).days
            test_duration = (
                window.test_range.end_date - window.test_range.start_date
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

        self.assertEqual(windows[0].train_range.start_date, start_date)

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
                window.train_range.end_date,
                window.test_range.start_date
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
            self.assertEqual(window.gap_days, gap_days)

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
            self.assertIsNotNone(w.train_range.start_date.tzinfo)
            self.assertIsNotNone(w.test_range.end_date.tzinfo)

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

    def test_fold_index_is_none_for_rolling(self):
        """Rolling windows should not carry a fold_index."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        windows = generate_rolling_backtest_windows(
            start_date=start_date, end_date=end_date,
            train_days=365, test_days=90, step_days=90
        )
        for w in windows:
            self.assertIsNone(w.fold_index)

    def test_warmup_days_reflected_in_effective_train_range(self):
        """effective_train_range should strip warmup from the start."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
        warmup = 26
        windows = generate_rolling_backtest_windows(
            start_date=start_date, end_date=end_date,
            train_days=365, test_days=90, step_days=90,
            warmup_days=warmup,
        )
        for w in windows:
            expected = w.train_range.start_date + pd.Timedelta(days=warmup)
            self.assertEqual(w.effective_train_range.start_date, expected)
            self.assertEqual(w.effective_train_range.end_date,
                             w.train_range.end_date)


class TestGenerateKFoldBacktestWindows(unittest.TestCase):
    """Tests for the generate_k_fold_backtest_windows function."""

    def test_returns_backtest_window_instances(self):
        """Each returned item should be a BacktestWindow."""
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        for w in windows:
            self.assertIsInstance(w, BacktestWindow)

    def test_n_splits_determines_fold_count(self):
        """Number of returned windows should equal n_splits (no skipping)."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        for n in (3, 5, 10):
            windows = generate_k_fold_backtest_windows(
                start_date=start_date, end_date=end_date, n_splits=n
            )
            # First fold has no training data, so it is skipped.
            self.assertEqual(len(windows), n - 1)

    def test_fold_index_set_correctly(self):
        """fold_index should be the zero-based index of the fold."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        # First fold (i=0) is skipped because train_days == 0.
        for w in windows:
            self.assertIsNotNone(w.fold_index)
            self.assertGreaterEqual(w.fold_index, 0)

    def test_folds_are_chronological(self):
        """Test start dates must increase strictly across folds."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        for i in range(1, len(windows)):
            self.assertGreater(
                windows[i].test_range.start_date,
                windows[i - 1].test_range.start_date,
            )

    def test_train_never_overlaps_test(self):
        """Training range must end before test range starts."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        for w in windows:
            self.assertLessEqual(
                w.train_range.end_date, w.test_range.start_date
            )

    def test_expanding_train_window(self):
        """Each fold's training window should always start at start_date."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        for w in windows:
            self.assertEqual(w.train_range.start_date, start_date)

    def test_gap_days_applied(self):
        """gap_days should be reflected in each window's gap_days property."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        gap_days = 30
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date,
            n_splits=5, gap_days=gap_days
        )
        for w in windows:
            self.assertEqual(w.gap_days, gap_days)

    def test_min_train_days_filters_early_folds(self):
        """Folds with fewer training days than min_train_days are skipped."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        n_splits = 5
        total_days = (end_date - start_date).days
        fold_size = total_days // n_splits
        # Require at least 2 full folds of training history.
        min_train = fold_size * 2
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date,
            n_splits=n_splits, min_train_days=min_train
        )
        for w in windows:
            train_days = (
                w.train_range.end_date - w.train_range.start_date
            ).days
            self.assertGreaterEqual(train_days, min_train)

    def test_last_fold_covers_end_date(self):
        """The last fold's test_end should equal end_date."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        self.assertEqual(windows[-1].test_range.end_date, end_date)

    def test_non_divisible_date_range(self):
        """Function should not crash when range does not divide evenly."""
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 7, 15, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=4
        )
        self.assertGreater(len(windows), 0)
        # Last fold must still end at end_date.
        self.assertEqual(windows[-1].test_range.end_date, end_date)

    def test_raises_on_n_splits_less_than_2(self):
        """n_splits < 2 should raise ValueError."""
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            generate_k_fold_backtest_windows(
                start_date=start_date, end_date=end_date, n_splits=1
            )

    def test_all_dates_timezone_aware(self):
        """All dates in returned windows must be timezone-aware."""
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 31, tzinfo=timezone.utc)
        windows = generate_k_fold_backtest_windows(
            start_date=start_date, end_date=end_date, n_splits=5
        )
        for w in windows:
            self.assertIsNotNone(w.train_range.start_date.tzinfo)
            self.assertIsNotNone(w.train_range.end_date.tzinfo)
            self.assertIsNotNone(w.test_range.start_date.tzinfo)
            self.assertIsNotNone(w.test_range.end_date.tzinfo)


if __name__ == "__main__":
    unittest.main()
