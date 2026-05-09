"""Tests that TWR-aware metrics neutralize external deposits.

The contract: a portfolio that earns 10%/yr and receives no deposits
should report the same CAGR (and similar Sharpe/std) as an otherwise
identical portfolio that received external deposits along the way —
provided the snapshots correctly populate ``cash_flow``.
"""
import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework.services.metrics import (
    get_cagr,
    get_daily_returns_std,
    get_sharpe_ratio,
)


class MockSnapshot:
    def __init__(self, total_value, created_at, cash_flow=0.0):
        self.total_value = total_value
        self.created_at = created_at
        self.cash_flow = cash_flow


def _organic_growth_series(start_value, daily_rate, days, start_date):
    """Build a snapshot list with pure organic growth, no deposits."""
    snapshots = []
    value = start_value
    for i in range(days + 1):
        snapshots.append(
            MockSnapshot(
                total_value=value,
                created_at=start_date + timedelta(days=i),
                cash_flow=0.0,
            )
        )
        value *= 1 + daily_rate
    return snapshots


def _organic_with_deposits(
    start_value, daily_rate, days, start_date, deposits
):
    """Same daily growth as ``_organic_growth_series`` but with extra
    deposits injected on specific days. Each deposit increases the
    end-of-day value AND records ``cash_flow`` for that day."""
    deposit_lookup = dict(deposits)  # day_index -> amount
    snapshots = []
    value = start_value
    snapshots.append(
        MockSnapshot(
            total_value=value, created_at=start_date, cash_flow=0.0
        )
    )
    for i in range(1, days + 1):
        # Organic growth on yesterday's value
        value *= 1 + daily_rate
        cash_flow = float(deposit_lookup.get(i, 0.0))
        # Deposit lands at end of day, after market action
        value += cash_flow
        snapshots.append(
            MockSnapshot(
                total_value=value,
                created_at=start_date + timedelta(days=i),
                cash_flow=cash_flow,
            )
        )
    return snapshots


class TestCagrWithCashFlow(unittest.TestCase):

    def setUp(self):
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        # ~10% annual organic growth
        self.daily_rate = (1 + 0.10) ** (1 / 365) - 1
        self.days = 365

    def test_cagr_matches_no_deposit_equivalent(self):
        organic = _organic_growth_series(
            10000, self.daily_rate, self.days, self.start
        )
        # Inject 4 quarterly $1,000 deposits — these should NOT inflate CAGR
        with_deposits = _organic_with_deposits(
            10000,
            self.daily_rate,
            self.days,
            self.start,
            deposits=[(90, 1000), (180, 1000), (270, 1000), (360, 1000)],
        )

        cagr_organic = get_cagr(organic)
        cagr_with_dep = get_cagr(with_deposits)

        # Both should be ~10% — within 0.5pp
        self.assertAlmostEqual(cagr_organic, 0.10, places=2)
        self.assertAlmostEqual(cagr_with_dep, cagr_organic, places=2)

    def test_naive_cagr_would_be_inflated_without_twr(self):
        """Sanity check: if we ignored cash_flow, raw end/start ratio
        would falsely report a much higher CAGR. This protects the test
        intent: the TWR fix is what makes the parity above hold."""
        with_deposits = _organic_with_deposits(
            10000,
            self.daily_rate,
            self.days,
            self.start,
            deposits=[(90, 1000), (180, 1000), (270, 1000), (360, 1000)],
        )
        start_v = with_deposits[0].total_value
        end_v = with_deposits[-1].total_value
        naive_cagr = (end_v / start_v) ** (1 / 1) - 1
        # Raw ratio inflates well above 10% because $4k deposits
        # masquerade as P&L
        self.assertGreater(naive_cagr, 0.40)

    def test_daily_returns_std_unaffected_by_deposits(self):
        organic = _organic_growth_series(
            10000, self.daily_rate, self.days, self.start
        )
        with_deposits = _organic_with_deposits(
            10000,
            self.daily_rate,
            self.days,
            self.start,
            deposits=[(90, 1000), (180, 1000), (270, 1000), (360, 1000)],
        )
        std_organic = get_daily_returns_std(organic)
        std_with = get_daily_returns_std(with_deposits)
        # Constant-growth series — std is essentially 0 in both cases.
        self.assertAlmostEqual(std_organic, std_with, places=4)

    def test_sharpe_unaffected_by_deposits(self):
        organic = _organic_growth_series(
            10000, self.daily_rate, self.days, self.start
        )
        with_deposits = _organic_with_deposits(
            10000,
            self.daily_rate,
            self.days,
            self.start,
            deposits=[(90, 1000), (180, 1000), (270, 1000), (360, 1000)],
        )
        # Sharpe of a constant-growth series is undefined (std=0 -> nan).
        # Use varying growth instead.
        import random
        rng = random.Random(42)
        organic2 = []
        with_dep2 = []
        v1 = v2 = 10000
        deposits = {90: 1000, 180: 1000, 270: 1000, 360: 1000}
        for i in range(self.days + 1):
            r = self.daily_rate + rng.gauss(0, 0.005)
            if i > 0:
                v1 *= 1 + r
                v2 *= 1 + r
                cf = float(deposits.get(i, 0.0))
                v2 += cf
            else:
                cf = 0.0
            d = self.start + timedelta(days=i)
            organic2.append(MockSnapshot(v1, d, 0.0))
            with_dep2.append(MockSnapshot(v2, d, cf))

        sh_organic = get_sharpe_ratio(organic2, risk_free_rate=0.02)
        sh_with = get_sharpe_ratio(with_dep2, risk_free_rate=0.02)
        # Should match within rounding — same return path, just $4k extra
        # capital on the side
        self.assertAlmostEqual(sh_organic, sh_with, places=2)


if __name__ == "__main__":
    unittest.main()
