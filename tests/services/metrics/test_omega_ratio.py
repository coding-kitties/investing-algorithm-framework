import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework.services.metrics import get_omega_ratio


class MockSnapshot:
    def __init__(self, total_value, created_at, cash_flow=0.0):
        self.total_value = total_value
        self.created_at = created_at
        self.cash_flow = cash_flow


class TestOmegaRatio(unittest.TestCase):

    def setUp(self):
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def _seq(self, values):
        return [
            MockSnapshot(v, self.start + timedelta(days=i))
            for i, v in enumerate(values)
        ]

    def test_empty_snapshots_returns_zero(self):
        self.assertEqual(get_omega_ratio([]), 0.0)

    def test_all_gains_returns_inf(self):
        snaps = self._seq([100, 110, 121, 133.1])
        self.assertEqual(get_omega_ratio(snaps), float("inf"))

    def test_balanced_gains_and_losses(self):
        # +10%, -10%, +10%, -10% -> symmetric gains/losses around 0
        snaps = self._seq([100, 110, 99, 108.9, 98.01])
        omega = get_omega_ratio(snaps, threshold=0.0)
        self.assertGreater(omega, 0.0)
        self.assertNotEqual(omega, float("inf"))

    def test_losing_strategy_has_omega_below_one(self):
        snaps = self._seq([100, 90, 81, 72.9])
        omega = get_omega_ratio(snaps)
        self.assertEqual(omega, 0.0)
