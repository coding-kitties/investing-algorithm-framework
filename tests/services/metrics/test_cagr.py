import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework.services.metrics import get_cagr


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing"""
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at


class TestGetCagr(unittest.TestCase):

    def create_snapshots(self, prices, start_date, interval_days=7):
        """
        Helper to create a list of mock snapshots from a price list.

        Args:
            prices: List of portfolio values
            start_date: Start datetime
            interval_days: Days between each snapshot (default: 7 for weekly)

        Returns:
            List of MockSnapshot objects
        """
        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(prices)
        ]

    def test_cagr_for_return_less_than_a_year(self):
        """
        Test CAGR calculation for a period less than a year (3 months).
        Given a portfolio with 12% annualized return,
        the CAGR should be approximately 12% when annualized.
        """
        # Convert annualized return to approximate weekly returns
        weekly_return = (1 + 0.12) ** (1 / 52) - 1  # ≈ 0.22%
        weeks = 13  # 3 months ≈ 13 weeks

        # Generate weekly prices (cumulative compounding)
        start_price = 100
        prices = [
            start_price * ((1 + weekly_return) ** i)
            for i in range(weeks + 1)
        ]

        start_date = datetime(2022, 1, 1)
        snapshots = self.create_snapshots(prices, start_date)

        cagr = get_cagr(snapshots)
        # CAGR should be approximately 12% annualized
        self.assertAlmostEqual(cagr, 0.12, delta=0.01)

    def test_cagr_for_return_exactly_a_year(self):
        """
        Test CAGR calculation for exactly one year.
        Given a portfolio with 12% annualized return over 52 weeks,
        the CAGR should be approximately 12%.
        """
        # Convert annualized return to approximate weekly returns
        weekly_return = (1 + 0.12) ** (1 / 52) - 1
        weeks = 52

        # Generate weekly prices (cumulative compounding)
        start_price = 100
        prices = [
            start_price * ((1 + weekly_return) ** i)
            for i in range(weeks + 1)
        ]

        start_date = datetime(2022, 1, 1)
        snapshots = self.create_snapshots(prices, start_date)

        cagr = get_cagr(snapshots)
        # CAGR should be approximately 12% annualized
        self.assertAlmostEqual(cagr, 0.12, delta=0.01)

    def test_cagr_for_return_more_than_a_year(self):
        """
        Test CAGR calculation for a period more than a year (18 months).
        Given a portfolio with 12% annualized return over 73 weeks,
        the CAGR should be approximately 12%.
        """
        # Convert annualized return to approximate weekly returns
        weekly_return = (1 + 0.12) ** (1 / 52) - 1
        weeks = 73  # ~18 months

        # Generate weekly prices (cumulative compounding)
        start_price = 100
        prices = [
            start_price * ((1 + weekly_return) ** i)
            for i in range(weeks + 1)
        ]

        start_date = datetime(2022, 1, 1)
        snapshots = self.create_snapshots(prices, start_date)

        cagr = get_cagr(snapshots)
        # CAGR should be approximately 12% annualized
        self.assertAlmostEqual(cagr, 0.12, delta=0.01)

    def test_cagr_empty_snapshots(self):
        """Test CAGR returns 0.0 for empty snapshot list."""
        cagr = get_cagr([])
        self.assertEqual(cagr, 0.0)

    def test_cagr_single_snapshot(self):
        """Test CAGR returns 0.0 when only one snapshot is provided."""
        snapshots = [MockSnapshot(1000, datetime(2022, 1, 1))]
        cagr = get_cagr(snapshots)
        self.assertEqual(cagr, 0.0)

    def test_cagr_same_day_snapshots(self):
        """Test CAGR returns 0.0 when all snapshots are on the same day."""
        same_day = datetime(2022, 1, 1)
        snapshots = [
            MockSnapshot(1000, same_day),
            MockSnapshot(1100, same_day),
        ]
        cagr = get_cagr(snapshots)
        self.assertEqual(cagr, 0.0)

    def test_cagr_zero_start_value(self):
        """Test CAGR returns 0.0 when start value is zero."""
        snapshots = [
            MockSnapshot(0, datetime(2022, 1, 1)),
            MockSnapshot(1000, datetime(2022, 6, 1)),
        ]
        cagr = get_cagr(snapshots)
        self.assertEqual(cagr, 0.0)

    def test_cagr_positive_return(self):
        """Test CAGR for a simple positive return scenario."""
        # Start with 1000, end with 1500 after 1 year = 50% return
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(1500, datetime(2023, 1, 1)),
        ]
        cagr = get_cagr(snapshots)
        self.assertAlmostEqual(cagr, 0.5, delta=0.01)

    def test_cagr_negative_return(self):
        """Test CAGR for a negative return scenario."""
        # Start with 1000, end with 800 after 1 year = -20% return
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(800, datetime(2023, 1, 1)),
        ]
        cagr = get_cagr(snapshots)
        self.assertAlmostEqual(cagr, -0.2, delta=0.01)

    def test_cagr_no_change(self):
        """Test CAGR for no change in portfolio value."""
        # Start with 1000, end with 1000 after 1 year = 0% return
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(1000, datetime(2023, 1, 1)),
        ]
        cagr = get_cagr(snapshots)
        self.assertAlmostEqual(cagr, 0.0, delta=0.001)

    def test_cagr_two_year_doubling(self):
        """
        Test CAGR for doubling value over 2 years.
        If 1000 -> 2000 in 2 years, CAGR = (2000/1000)^(1/2) - 1 ≈ 41.4%
        """
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(2000, datetime(2024, 1, 1)),
        ]
        cagr = get_cagr(snapshots)
        expected_cagr = (2000 / 1000) ** (1 / 2) - 1  # ≈ 0.414
        self.assertAlmostEqual(cagr, expected_cagr, delta=0.01)

    def test_cagr_half_year_period(self):
        """
        Test CAGR for 6 months period.
        If 1000 -> 1050 in 6 months (~183 days), annualized should be higher.
        """
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(1050, datetime(2022, 7, 1)),  # ~6 months later
        ]
        cagr = get_cagr(snapshots)
        # 5% in ~6 months should annualize to approximately 10.25%
        self.assertGreater(cagr, 0.09)
        self.assertLess(cagr, 0.12)

    def test_cagr_unordered_snapshots(self):
        """Test that CAGR correctly handles unordered snapshots."""
        # Snapshots provided in wrong order
        snapshots = [
            MockSnapshot(1500, datetime(2023, 1, 1)),  # End
            MockSnapshot(1000, datetime(2022, 1, 1)),  # Start
        ]
        cagr = get_cagr(snapshots)
        # Should still calculate correctly after sorting
        self.assertAlmostEqual(cagr, 0.5, delta=0.01)

    def test_cagr_multiple_snapshots(self):
        """
        Test CAGR with multiple intermediate snapshots.
        Only start and end values matter for CAGR.
        """
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(900, datetime(2022, 4, 1)),   # Dip
            MockSnapshot(1100, datetime(2022, 7, 1)),  # Recovery
            MockSnapshot(800, datetime(2022, 10, 1)),  # Another dip
            MockSnapshot(1200, datetime(2023, 1, 1)),  # End higher
        ]
        cagr = get_cagr(snapshots)
        # Only start (1000) and end (1200) matter: 20% return
        self.assertAlmostEqual(cagr, 0.2, delta=0.01)

    def test_cagr_with_timezone_aware_dates(self):
        """Test CAGR works with timezone-aware datetime objects."""
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1, tzinfo=timezone.utc)),
            MockSnapshot(1500, datetime(2023, 1, 1, tzinfo=timezone.utc)),
        ]
        cagr = get_cagr(snapshots)
        self.assertAlmostEqual(cagr, 0.5, delta=0.01)

    def test_cagr_very_short_period(self):
        """Test CAGR for a very short period (7 days)."""
        # 1% gain in 7 days should annualize to a large number
        snapshots = [
            MockSnapshot(1000, datetime(2022, 1, 1)),
            MockSnapshot(1010, datetime(2022, 1, 8)),  # 7 days, 1% gain
        ]
        cagr = get_cagr(snapshots)
        # 1% in 7 days annualized = (1.01)^(365/7) - 1 ≈ 68%
        expected = (1.01) ** (365 / 7) - 1
        self.assertAlmostEqual(cagr, expected, delta=0.05)

    def test_cagr_very_long_period(self):
        """Test CAGR for a very long period (5 years)."""
        # Doubling in 5 years
        snapshots = [
            MockSnapshot(1000, datetime(2020, 1, 1)),
            MockSnapshot(2000, datetime(2025, 1, 1)),
        ]
        cagr = get_cagr(snapshots)
        # (2000/1000)^(1/5) - 1 ≈ 14.87%
        expected = (2000 / 1000) ** (1 / 5) - 1
        self.assertAlmostEqual(cagr, expected, delta=0.01)


if __name__ == "__main__":
    unittest.main()
