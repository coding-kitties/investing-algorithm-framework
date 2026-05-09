"""Tests for the TWR (alpha-only) variants of equity curve and drawdown."""
import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework.services.metrics import (
    get_drawdown_series,
    get_equity_curve,
    get_max_drawdown,
    get_twr_drawdown_series,
    get_twr_equity_curve,
    get_twr_max_drawdown,
    get_twr_max_drawdown_duration,
)


class MockSnapshot:
    def __init__(self, total_value, created_at, cash_flow=0.0):
        self.total_value = total_value
        self.created_at = created_at
        self.cash_flow = cash_flow


class TestTwrEquityCurve(unittest.TestCase):

    def setUp(self):
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def _seq(self, points):
        return [
            MockSnapshot(v, self.start + timedelta(days=i), cf)
            for i, (v, cf) in enumerate(points)
        ]

    def test_no_cash_flow_matches_raw_growth(self):
        snaps = self._seq([(100, 0), (110, 0), (121, 0)])
        twr = get_twr_equity_curve(snaps, base=100)
        # 10% per step → 100, 110, 121
        values = [v for v, _ in twr]
        self.assertAlmostEqual(values[0], 100.0)
        self.assertAlmostEqual(values[1], 110.0)
        self.assertAlmostEqual(values[2], 121.0)

    def test_deposit_does_not_inflate_twr_curve(self):
        # Day 0: 100. Day 1: 110 (+10% organic). Day 2: 1121 (= 110*1.1
        # + 1000 deposit). Raw curve jumps to 1121; TWR curve stays at
        # 121 (= 100 * 1.1 * 1.1).
        snaps = self._seq([(100, 0), (110, 0), (1121, 1000)])
        twr = get_twr_equity_curve(snaps, base=100)
        values = [v for v, _ in twr]
        self.assertAlmostEqual(values[2], 121.0, places=4)

        # Raw curve does jump
        raw = get_equity_curve(snaps)
        self.assertAlmostEqual(raw[2][0], 1121.0)

    def test_growth_of_one_default_base(self):
        snaps = self._seq([(100, 0), (110, 0), (121, 0)])
        twr = get_twr_equity_curve(snaps)  # base=1.0
        values = [v for v, _ in twr]
        self.assertAlmostEqual(values[0], 1.0)
        self.assertAlmostEqual(values[2], 1.21)

    def test_empty(self):
        self.assertEqual([], get_twr_equity_curve([]))


class TestTwrDrawdown(unittest.TestCase):

    def setUp(self):
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def _seq(self, points):
        return [
            MockSnapshot(v, self.start + timedelta(days=i), cf)
            for i, (v, cf) in enumerate(points)
        ]

    def test_deposit_during_drawdown_does_not_mask_it(self):
        # Organic path: 100 → 80 (−20% dd) → 90 → 100 (recovered)
        # Add a +50 deposit on day 1 so raw values are
        # 100, 130, 140, 150 — raw drawdown == 0.
        # TWR drawdown should still surface the −20% dip on day 1.
        organic_returns = [None, -0.20, +0.125, +0.111111111]
        snaps = []
        v_raw = 100.0
        v_twr = 100.0
        deposits = {1: 50.0}
        for i, r in enumerate(organic_returns):
            cf = float(deposits.get(i, 0.0))
            if r is not None:
                v_twr *= 1 + r
                v_raw = v_raw * (1 + r) + cf
            snaps.append(
                MockSnapshot(v_raw, self.start + timedelta(days=i), cf)
            )

        # Raw drawdown is masked by the +50 deposit that immediately
        # followed the dip
        raw_dd = get_max_drawdown(snaps)
        # With the deposit, raw equity is 100, 130, 140, 150 → no DD
        self.assertAlmostEqual(raw_dd, 0.0, places=4)

        # TWR drawdown is unaffected by the deposit
        twr_dd = get_twr_max_drawdown(snaps)
        self.assertAlmostEqual(twr_dd, 0.20, places=2)

    def test_twr_drawdown_series_matches_no_deposit_case(self):
        # Without deposits, TWR series and raw series should yield the
        # same drawdown percentages.
        snaps = [
            MockSnapshot(v, self.start + timedelta(days=i), 0.0)
            for i, v in enumerate([100, 90, 80, 95, 100])
        ]
        raw = [d for d, _ in get_drawdown_series(snaps)]
        twr = [d for d, _ in get_twr_drawdown_series(snaps)]
        for r, t in zip(raw, twr):
            self.assertAlmostEqual(r, t, places=6)

    def test_twr_max_drawdown_duration(self):
        # Drawdown lasts 3 days then recovers
        snaps = [
            MockSnapshot(100, self.start + timedelta(days=0), 0.0),
            MockSnapshot(90, self.start + timedelta(days=1), 0.0),
            MockSnapshot(85, self.start + timedelta(days=2), 0.0),
            MockSnapshot(95, self.start + timedelta(days=3), 0.0),
            MockSnapshot(110, self.start + timedelta(days=4), 0.0),
        ]
        self.assertEqual(3, get_twr_max_drawdown_duration(snaps))

    def test_empty(self):
        self.assertEqual([], get_twr_drawdown_series([]))
        self.assertEqual(0.0, get_twr_max_drawdown([]))
        self.assertEqual(0, get_twr_max_drawdown_duration([]))


if __name__ == "__main__":
    unittest.main()
