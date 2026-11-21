import unittest
from datetime import datetime, timezone

from investing_algorithm_framework.services.metrics.value_at_risk import (
    get_conditional_value_at_risk,
    get_value_at_risk,
)


class MockSnapshot:
    def __init__(self, total_value, created_at, cash_flow=0.0):
        self.total_value = total_value
        self.created_at = created_at
        self.cash_flow = cash_flow


class TestValueAtRisk(unittest.TestCase):

    def test_includes_first_month(self):
        # -20% in January, then +10% each month
        snapshots = [
            MockSnapshot(value, datetime(2024, m, d, tzinfo=timezone.utc))
            for value, m, d in [
                (100, 1, 1), (80, 1, 31), (88, 2, 29), (96.8, 3, 31),
            ]
        ]
        self.assertLess(get_value_at_risk(snapshots), 0)
        self.assertAlmostEqual(
            get_conditional_value_at_risk(snapshots), -0.2
        )
