import unittest
from datetime import datetime, timedelta

from investing_algorithm_framework import get_exposure_ratio

# Mock classes to simulate report and trades
class MockTrade:
    def __init__(self, created_at, closed_at=None):
        self.opened_at = created_at
        self.closed_at = closed_at

class MockReport:
    def __init__(self, trades, backtest_start_date, backtest_end_date):
        self._trades = trades
        self.backtest_start_date = backtest_start_date
        self.backtest_end_date = backtest_end_date

    def get_trades(self):
        return self._trades


class TestGetExposureTime(unittest.TestCase):

    def test_no_trades(self):
        report = MockReport(trades=[],
                            backtest_start_date=datetime(2023,1,1),
                            backtest_end_date=datetime(2023,1,10))
        self.assertEqual(get_exposure_ratio(report.get_trades(), report.backtest_start_date, report.backtest_end_date), 0.0)

    def test_no_backtest_duration(self):
        # start and end date are the same
        report = MockReport(trades=[MockTrade(datetime(2023,1,1))],
                            backtest_start_date=datetime(2023,1,1),
                            backtest_end_date=datetime(2023,1,1))
        self.assertEqual(get_exposure_ratio(report.get_trades(), report.backtest_start_date, report.backtest_end_date), 0.0)

    def test_single_trade_within_backtest(self):
        start = datetime(2023,1,1)
        end = datetime(2023,1,10)
        trade_start = datetime(2023,1,2)
        trade_end = datetime(2023,1,5)
        trade = MockTrade(created_at=trade_start, closed_at=trade_end)
        report = MockReport(trades=[trade], backtest_start_date=start, backtest_end_date=end)

        expected = (trade_end - trade_start).total_seconds() / (end - start).total_seconds()
        self.assertAlmostEqual(get_exposure_ratio(report.get_trades(), start, end), expected)

    def test_multiple_trades(self):
        start = datetime(2023,1,1)
        end = datetime(2023,1,11)
        trades = [
            MockTrade(datetime(2023,1,2), datetime(2023,1,3)),
            MockTrade(datetime(2023,1,4), datetime(2023,1,6)),
            MockTrade(datetime(2023,1,8), datetime(2023,1,9)),
        ]
        report = MockReport(trades=trades, backtest_start_date=start, backtest_end_date=end)

        total_duration = timedelta(days=1) + timedelta(days=2) + timedelta(days=1)
        expected = total_duration.total_seconds() / (end - start).total_seconds()
        self.assertAlmostEqual(get_exposure_ratio(report.get_trades(), start, end), expected)

    def test_open_trade_counts_to_backtest_end(self):
        start = datetime(2023,1,1)
        end = datetime(2023,1,10)
        trade_start = datetime(2023,1,8)
        trade = MockTrade(created_at=trade_start, closed_at=None)  # open trade
        report = MockReport(trades=[trade], backtest_start_date=start, backtest_end_date=end)

        expected = (end - trade_start).total_seconds() / (end - start).total_seconds()
        self.assertAlmostEqual(get_exposure_ratio(report.get_trades(), start, end), expected)

    def test_trade_exit_before_entry_ignored(self):
        # Trade closed before it started (bad data), should ignore this trade duration
        start = datetime(2023,1,1)
        end = datetime(2023,1,10)
        trade_start = datetime(2023,1,5)
        trade_end = datetime(2023,1,4)  # closed before created
        trade = MockTrade(created_at=trade_start, closed_at=trade_end)
        report = MockReport(trades=[trade], backtest_start_date=start, backtest_end_date=end)
        self.assertEqual(get_exposure_ratio(report.get_trades(), start, end), 0.0)
