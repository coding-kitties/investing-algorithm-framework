import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from investing_algorithm_framework.domain import BacktestRun

from investing_algorithm_framework import get_calmar_ratio


class TestGetCalmarRatio(unittest.TestCase):

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
        self.backtest_report.snapshots = self.snapshots

    def _create_report(self, total_size_series, timestamps):
        report = MagicMock(spec=BacktestRun)
        report.portfolio_snapshots = [
            MagicMock(created_at=ts, total_value=size)
            for ts, size in zip(timestamps, total_size_series)
        ]
        return report

    def test_typical_case(self):
        # Create a report with total sizes for a whole year, with intervals of 31 days.
        report = self._create_report(
            [1000, 1200, 900, 1100, 1300],
            [datetime(2024, i, 1) for i in range(1, 6)]
        )
        ratio = get_calmar_ratio(report.portfolio_snapshots)
        self.assertEqual(ratio, 4.8261927891975365)  # Expected ratio based on the mock data

    def test_calmar_ratio_zero_drawdown(self):
        # Create a report with total sizes for a whole year, with intervals of 31 days, and no drawdowns.
        report = self._create_report(
            [1000, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000],
            [datetime(2024, 1, i) for i in range(1, 11)]
        )
        ratio = get_calmar_ratio(report.portfolio_snapshots)
        self.assertEqual(ratio, 0.0)

    def test_calmar_ratio_with_only_drawdown(self):
        # Create a report with total sizes for a whole year, with intervals of 31 days, and no drawdowns.
        report = self._create_report(
            [1000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
            [datetime(2024, 1, i) for i in range(1, 11)]
        )
        ratio = get_calmar_ratio(report.portfolio_snapshots)
        self.assertEqual(ratio, -1.1111111111111112)
