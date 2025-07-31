import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import numpy as np

from investing_algorithm_framework import get_sortino_ratio

# Mock Snapshot class
class Snapshot:
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at


class TestGetSortinoRatio(unittest.TestCase):

    def create_report(self, prices, start_date):
        """ Helper to create a mocked BacktestReport from a price list """
        snapshots = [
            Snapshot(net_size, start_date + timedelta(weeks=i))
            for i, net_size in enumerate(prices)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        return report

    def test_no_snapshots(self):
        report = MagicMock()
        report.get_snapshots.return_value = []
        self.assertEqual(get_sortino_ratio(report.get_snapshots()), float("inf"))

    # def test_single_snapshot(self):
    #     report = MagicMock()
    #     report.get_snapshots.return_value = [Snapshot(1000, datetime.now())]
    #     self.assertEqual(get_sortino_ratio(report.get_snapshots()), float("inf"))

    # def test_all_returns_above_risk_free(self):
    #     now = datetime.now()
    #     snapshots = [
    #         Snapshot(100, now),
    #         Snapshot(110, now + timedelta(days=1)),
    #         Snapshot(121, now + timedelta(days=2)),  # +10% twice
    #     ]
    #     report = MagicMock()
    #     report.get_snapshots.return_value = snapshots
    #     result = get_sortino_ratio(report.get_snapshots(), risk_free_rate=0.01)
    #     self.assertEqual(result, float('inf'))

    def test_mixed_returns(self):
        now = datetime.now()
        snapshots = [
            Snapshot(100, now),
            Snapshot(90, now + timedelta(days=1)),  # -10%
            Snapshot(99, now + timedelta(days=2)),  # +10%
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots

        ratio = get_sortino_ratio(report.get_snapshots())
        self.assertEqual(ratio, 0.0)

    # def test_constant_returns(self):
    #     now = datetime.now()
    #     snapshots = [
    #         Snapshot(100, now),
    #         Snapshot(100, now + timedelta(days=1)),
    #         Snapshot(100, now + timedelta(days=2)),
    #     ]
    #     report = MagicMock()
    #     report.get_snapshots.return_value = snapshots
    #     self.assertEqual(get_sortino_ratio(report.get_snapshots()), float('inf'))
