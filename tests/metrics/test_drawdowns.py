import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from investing_algorithm_framework import get_drawdown_series, \
    get_max_drawdown, get_max_drawdown_absolute


class TestDrawdownFunctions(unittest.TestCase):

    def setUp(self):
        # Generate mocked equity curve: net_size over time
        self.timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
        ]

        self.net_sizes = [1000, 1200, 900, 1100, 1300]  # Simulates rise, fall, recovery, new high

        # Create mock snapshot objects
        self.snapshots = []
        for ts, net_size in zip(self.timestamps, self.net_sizes):
            snapshot = MagicMock()
            snapshot.created_at = ts
            snapshot.total_value = net_size
            self.snapshots.append(snapshot)

        # Create a mocked BacktestReport
        self.backtest_report = MagicMock()
        self.backtest_report.get_snapshots.return_value = self.snapshots

    def test_drawdown_series(self):
        drawdown_series = get_drawdown_series(self.backtest_report)

        expected_drawdowns = [
            0.0,                                # baseline
            0.0,                                # new high
            (900 - 1200) / 1200,                # drop from peak
            (1100 - 1200) / 1200,               # partial recovery
            0.0                                 # new peak again
        ]

        self.assertEqual(len(drawdown_series), len(expected_drawdowns))

        for i, (_, drawdown) in enumerate(drawdown_series):
            self.assertAlmostEqual(drawdown, expected_drawdowns[i], places=6)

    def test_max_drawdown(self):
        max_drawdown = get_max_drawdown(self.backtest_report)
        print(max_drawdown)
        expected_max = ((900 - 1200) / 1200) * 100# -0.25
        self.assertAlmostEqual(max_drawdown, expected_max, places=6)

    def test_max_drawdown_absolute(self):
        max_drawdown = get_max_drawdown_absolute(self.backtest_report)
        self.assertEqual(max_drawdown, 300)  # 1200 - 900 = 300
