import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework.services.metrics import get_ulcer_index


class MockSnapshot:
    def __init__(self, total_value, created_at, cash_flow=0.0):
        self.total_value = total_value
        self.created_at = created_at
        self.cash_flow = cash_flow


class TestUlcerIndex(unittest.TestCase):

    def setUp(self):
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def _seq(self, values):
        return [
            MockSnapshot(v, self.start + timedelta(days=i))
            for i, v in enumerate(values)
        ]

    def test_empty_snapshots_returns_zero(self):
        self.assertEqual(get_ulcer_index([]), 0.0)

    def test_no_drawdown_is_zero(self):
        snaps = self._seq([100, 110, 120, 130])
        self.assertAlmostEqual(get_ulcer_index(snaps), 0.0, places=6)

    def test_matches_manual_rms_of_drawdowns(self):
        # 1000 -> 1200 (peak) -> 900 (25% dd) -> 1100 (partial recovery,
        # still ~8.33% dd) -> 1300 (new peak)
        snaps = self._seq([1000, 1200, 900, 1100, 1300])
        expected_drawdowns = [
            0.0,
            0.0,
            (900 - 1200) / 1200,
            (1100 - 1200) / 1200,
            0.0,
        ]
        expected = (
            sum(d ** 2 for d in expected_drawdowns)
            / len(expected_drawdowns)
        ) ** 0.5
        self.assertAlmostEqual(get_ulcer_index(snaps), expected, places=6)

    def test_deeper_drawdown_increases_ulcer_index(self):
        shallow = self._seq([1000, 950, 1000])
        deep = self._seq([1000, 700, 1000])
        self.assertGreater(get_ulcer_index(deep), get_ulcer_index(shallow))
