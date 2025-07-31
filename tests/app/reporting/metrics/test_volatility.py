import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import numpy as np

from investing_algorithm_framework import get_annual_volatility

# Mock snapshot class
class Snapshot:
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at

class TestGetVolatility(unittest.TestCase):

    def test_no_snapshots(self):
        report = MagicMock()
        report.get_snapshots.return_value = []
        report.number_of_days = 10
        self.assertEqual(get_annual_volatility(report.get_snapshots()), 0.0)

    def test_single_snapshot(self):
        report = MagicMock()
        snapshot = Snapshot(1000, datetime.now())
        report.get_snapshots.return_value = [snapshot]
        report.number_of_days = 10
        self.assertEqual(get_annual_volatility(report.get_snapshots()), 0.0)

    def test_constant_net_size(self):
        now = datetime.now()
        snapshots = [
            Snapshot(1000, now + timedelta(days=i)) for i in range(10)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        report.number_of_days = 9
        self.assertAlmostEqual(get_annual_volatility(report.get_snapshots()), 0.0, places=6)

    def test_increasing_net_size(self):
        now = datetime.now()
        net_sizes = [1000 + i * 10 for i in range(10)]
        snapshots = [
            Snapshot(size, now + timedelta(days=i)) for i, size in enumerate(net_sizes)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        report.number_of_days = 9

        vol = get_annual_volatility(report.get_snapshots())
        self.assertGreater(vol, 0.0)

    def test_zero_days_fallback(self):
        now = datetime.now()
        net_sizes = [1000, 1020, 1010, 1040]
        snapshots = [
            Snapshot(size, now + timedelta(days=i)) for i, size in enumerate(net_sizes)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        report.number_of_days = 0  # Should trigger fallback to 252

        vol = get_annual_volatility(report.get_snapshots())
        self.assertGreater(vol, 0.0)

    def test_known_volatility_zero(self):
        """Test case with known identical log returns (std = 0)"""
        now = datetime.now()
        net_sizes = [100, 110, 121]  # +10% each day
        snapshots = [
            Snapshot(size, now + timedelta(days=i)) for i, size in enumerate(net_sizes)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        report.number_of_days = 2  # span = 2 days

        # Two log returns: ln(1.1), ln(1.1), std = 0
        vol = get_annual_volatility(report.get_snapshots())
        self.assertAlmostEqual(vol, 0.0, places=6)

    def test_known_nonzero_volatility(self):
        """Test case with alternating returns to yield known std dev"""
        now = datetime.now()
        net_sizes = [100, 110, 100]  # +10%, -9.09%
        snapshots = [
            Snapshot(size, now + timedelta(days=i)) for i, size in enumerate(net_sizes)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        report.number_of_days = 2

        # log returns: ln(110/100), ln(100/110)
        log_returns = np.log([110/100, 100/110])
        expected_std = np.std(log_returns, ddof=1)
        expected_vol = expected_std * np.sqrt((2 / 2) * 365)  # 2 returns in 2 days

        vol = get_annual_volatility(report.get_snapshots())
        self.assertAlmostEqual(vol, expected_vol, places=6)
