import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import numpy as np

from investing_algorithm_framework import \
    get_standard_deviation_downside_returns

class Snapshot:
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at


class TestStandardDeviationDownside(unittest.TestCase):

    def test_empty_snapshots(self):
        report = MagicMock()
        report.get_snapshots.return_value = []
        self.assertEqual(get_standard_deviation_downside_returns(report), 0.0)

    def test_single_snapshot(self):
        now = datetime.now()
        snapshots = [Snapshot(100, now)]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        self.assertEqual(get_standard_deviation_downside_returns(report), 0.0)

    def test_all_positive_returns(self):
        now = datetime.now()
        snapshots = [
            Snapshot(100, now),
            Snapshot(110, now + timedelta(days=1)),
            Snapshot(121, now + timedelta(days=2)),
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        self.assertEqual(get_standard_deviation_downside_returns(report), 0.0)

    def test_all_negative_returns(self):
        now = datetime.now()
        snapshots = [
            Snapshot(100, now),
            Snapshot(90, now + timedelta(days=1)),
            Snapshot(81, now + timedelta(days=2)),
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        # Returns: -10%, -10%
        expected_std = np.std([-0.1, -0.1], ddof=1)
        self.assertAlmostEqual(get_standard_deviation_downside_returns(report), expected_std, places=6)

    def test_mixed_returns(self):
        now = datetime.now()
        snapshots = [
            Snapshot(100, now),
            Snapshot(90, now + timedelta(days=1)),   # -10%
            Snapshot(99, now + timedelta(days=2)),   # +10%
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        # Downside returns: [-0.1]
        expected_std = np.std([-0.1], ddof=1)
        self.assertTrue(np.isnan(expected_std) or expected_std == 0.0)
        self.assertEqual(get_standard_deviation_downside_returns(report), 0.0)

    def test_nan_handling(self):
        now = datetime.now()
        snapshots = [
            Snapshot(100, now),
            Snapshot(100, now + timedelta(days=1)),
            Snapshot(100, now + timedelta(days=2)),
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        self.assertEqual(get_standard_deviation_downside_returns(report), 0.0)
