from unittest import TestCase
from datetime import datetime, timedelta

from investing_algorithm_framework.domain import BacktestDateRange


class Test(TestCase):

    def test_with_datetime(self):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=10)
        date_range = BacktestDateRange(
            name="test",
            start_date=start_date,
            end_date=end_date
        )
        self.assertEqual(start_date, date_range.start_date)
        self.assertEqual(end_date, date_range.end_date)
        self.assertEqual("test", date_range.name)

    def test_with_string(self):
        date_range = BacktestDateRange(
            name="string based",
            start_date="2022-01-01",
            end_date="2022-03-01"
        )
        self.assertEqual(
            datetime(year=2022, day=1, month=1), date_range.start_date
        )
        self.assertEqual(
            datetime(year=2022, day=1, month=3), date_range.end_date
        )
        self.assertEqual("string based", date_range.name)
