from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.domain import (
    BacktestDateRange,
    BacktestWindow,
)


class TestBacktestWindowDurationValidation(TestCase):

    def test_accepts_positive_intraday_training_range(self):
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, 10, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
        )

        window = BacktestWindow(train_range=date_range)

        self.assertEqual(window.train_range, date_range)

    def test_rejects_zero_length_training_range(self):
        instant = datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
        date_range = BacktestDateRange(
            start_date=instant,
            end_date=instant,
        )

        with self.assertRaises(ValueError):
            BacktestWindow(train_range=date_range)

    def test_rejects_warmup_equal_to_training_duration(self):
        date_range = BacktestDateRange(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        with self.assertRaises(ValueError):
            BacktestWindow(train_range=date_range, warmup_days=1)