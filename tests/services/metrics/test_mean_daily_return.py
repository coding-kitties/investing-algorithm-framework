from datetime import datetime, timezone, date, timedelta
from unittest import TestCase

from investing_algorithm_framework.domain import PortfolioSnapshot
from investing_algorithm_framework.services import (
    get_mean_daily_return,
    get_mean_yearly_return
)


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing"""
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at


class TestGetMeanDailyReturn(TestCase):

    def _create_snapshots(self, values, start_date, interval_days=1):
        """
        Helper to create a list of mock snapshots from a value list.

        Args:
            values: List of portfolio values
            start_date: Start datetime
            interval_days: Days between each snapshot (default: 1)

        Returns:
            List of MockSnapshot objects
        """
        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_mean_daily_return_calculation(self):
        """Test mean daily return with real-world-like data."""
        total_values = [
            100000, 101154, 102949, 101090, 99487, 99936, 101026,
            103974, 105320, 105384, 103333, 106602, 108397, 107243,
            107373, 106666, 107756, 107307, 109615, 108846, 108589,
            107372
        ]

        dates = [
            date(year=2010, month=9, day=10),
            date(year=2010, month=9, day=13),
            date(year=2010, month=9, day=14),
            date(year=2010, month=9, day=15),
            date(year=2010, month=9, day=16),
            date(year=2010, month=9, day=17),
            date(year=2010, month=9, day=20),
            date(year=2010, month=9, day=21),
            date(year=2010, month=9, day=22),
            date(year=2010, month=9, day=23),
            date(year=2010, month=9, day=24),
            date(year=2010, month=9, day=27),
            date(year=2010, month=9, day=28),
            date(year=2010, month=9, day=29),
            date(year=2010, month=9, day=30),
            date(year=2010, month=10, day=1),
            date(year=2010, month=10, day=4),
            date(year=2010, month=10, day=5),
            date(year=2010, month=10, day=6),
            date(year=2010, month=10, day=7),
            date(year=2010, month=10, day=8),
            date(year=2010, month=10, day=12)
        ]

        snapshots = [
            PortfolioSnapshot(
                portfolio_id="test_portfolio",
                total_value=val,
                created_at=datetime.combine(
                    d, datetime.min.time()
                ).replace(tzinfo=timezone.utc)
            )
            for d, val in zip(dates, total_values)
        ]

        mean_daily_return = get_mean_daily_return(snapshots)
        self.assertAlmostEqual(mean_daily_return, 0.002225, places=3)

    def test_mean_daily_return_positive_returns(self):
        """Test with consistently positive daily returns."""
        # 1% daily growth over 30 days
        start_value = 1000
        daily_growth = 1.01
        values = [start_value * (daily_growth ** i) for i in range(31)]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Mean daily return should be close to 1%
        self.assertAlmostEqual(mean_return, 0.01, delta=0.002)

    def test_mean_daily_return_negative_returns(self):
        """Test with consistently negative daily returns."""
        # 1% daily decline over 30 days
        start_value = 1000
        daily_decline = 0.99
        values = [start_value * (daily_decline ** i) for i in range(31)]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Mean daily return should be close to -1%
        self.assertAlmostEqual(mean_return, -0.01, delta=0.002)

    def test_mean_daily_return_mixed_returns(self):
        """Test with alternating positive and negative returns."""
        # Alternates between +5% and -5%
        values = [1000, 1050, 997.5, 1047.375, 994.01, 1043.71]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Mean should be close to zero (slightly positive due to compounding)
        self.assertAlmostEqual(mean_return, 0.0, delta=0.01)

    def test_mean_daily_return_no_change(self):
        """Test with no change in portfolio value."""
        values = [1000, 1000, 1000, 1000, 1000]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        self.assertEqual(mean_return, 0.0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_mean_daily_return_empty_snapshots(self):
        """Test with empty snapshot list."""
        mean_return = get_mean_daily_return([])
        self.assertEqual(mean_return, 0.0)

    def test_mean_daily_return_single_snapshot(self):
        """Test with only one snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        mean_return = get_mean_daily_return(snapshots)
        self.assertEqual(mean_return, 0.0)

    def test_mean_daily_return_two_snapshots(self):
        """Test with exactly two snapshots."""
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc)),
            MockSnapshot(1100, datetime(2024, 1, 2, tzinfo=timezone.utc)),
        ]
        mean_return = get_mean_daily_return(snapshots)
        # 10% return in one day, short period so uses CAGR-based calculation
        self.assertGreater(mean_return, 0)

    def test_mean_daily_return_same_day_snapshots(self):
        """Test with multiple snapshots on the same day."""
        same_day = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = [
            MockSnapshot(1000, same_day),
            MockSnapshot(1100, same_day),
            MockSnapshot(1200, same_day),
        ]
        mean_return = get_mean_daily_return(snapshots)
        # After deduplication, only one unique day remains
        self.assertEqual(mean_return, 0.0)

    # ==========================================================
    # Time Period Tests
    # ==========================================================

    def test_mean_daily_return_less_than_year(self):
        """Test with data spanning less than a year (uses CAGR method)."""
        # 6 months of data with 20% total return
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 7, 1, tzinfo=timezone.utc)
        days = (end_date - start_date).days

        # Linear growth from 1000 to 1200 over 6 months
        values = [1000 + (200 * i / days) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Should use CAGR method and return annualized daily return
        self.assertGreater(mean_return, 0)
        self.assertLess(mean_return, 0.01)  # Should be small daily return

    def test_mean_daily_return_exactly_one_year(self):
        """Test with data spanning exactly one year."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        days = 365

        # 10% annual return distributed evenly
        daily_return = (1.10) ** (1/365) - 1
        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Should calculate actual mean daily return
        self.assertGreater(mean_return, 0)
        self.assertAlmostEqual(mean_return, daily_return, delta=0.0001)

    def test_mean_daily_return_more_than_year(self):
        """Test with data spanning more than one year."""
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 500  # ~1.37 years

        # Consistent 0.05% daily return
        daily_return = 0.0005
        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Should calculate actual mean daily return
        self.assertAlmostEqual(mean_return, daily_return, delta=0.0001)

    # ==========================================================
    # Resampling Tests
    # ==========================================================

    def test_mean_daily_return_hourly_data(self):
        """Test with hourly snapshots (should resample to daily)."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # 48 hours of data (2 days)
        values = []
        for day in range(2):
            for hour in range(24):
                # Day 1: starts at 1000, Day 2: starts at 1010
                base = 1000 + (day * 10)
                values.append(base + hour * 0.1)

        snapshots = [
            MockSnapshot(val, start_date + timedelta(hours=i))
            for i, val in enumerate(values)
        ]

        mean_return = get_mean_daily_return(snapshots)
        # After resampling to daily, should get ~1% return
        self.assertIsNotNone(mean_return)

    def test_mean_daily_return_weekly_data(self):
        """Test with weekly snapshots."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # 52 weeks of data with 1% weekly growth
        weekly_return = 0.01
        values = [1000 * ((1 + weekly_return) ** i) for i in range(53)]
        snapshots = self._create_snapshots(values, start_date, interval_days=7)

        mean_return = get_mean_daily_return(snapshots)
        # Mean daily return should be derived from weekly data
        self.assertGreater(mean_return, 0)

    # ==========================================================
    # Volatility Tests
    # ==========================================================

    def test_mean_daily_return_high_volatility(self):
        """Test with high volatility (large swings)."""
        # Large daily swings: +10%, -8%, +12%, -6%, etc.
        values = [1000, 1100, 1012, 1133.44, 1065.43, 1182.63]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        # Should still calculate mean correctly despite volatility
        self.assertIsNotNone(mean_return)
        self.assertGreater(mean_return, 0)  # Overall positive trend

    def test_mean_daily_return_low_volatility(self):
        """Test with very low volatility (small changes)."""
        # 0.01% daily change
        daily_return = 0.0001
        values = [1000 * ((1 + daily_return) ** i) for i in range(31)]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        mean_return = get_mean_daily_return(snapshots)
        self.assertAlmostEqual(mean_return, daily_return, delta=0.00005)


class TestGetMeanYearlyReturn(TestCase):

    def _create_snapshots(self, values, start_date, interval_days=1):
        """Helper to create mock snapshots."""
        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_mean_yearly_return_positive(self):
        """Test mean yearly return with positive daily returns."""
        # 0.05% daily return ≈ 20% annual return
        daily_return = 0.0005
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 400

        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        yearly_return = get_mean_yearly_return(snapshots)
        # (1 + 0.0005)^365 - 1 ≈ 0.20 (20%)
        expected = (1 + daily_return) ** 365 - 1
        self.assertAlmostEqual(yearly_return, expected, delta=0.01)

    def test_mean_yearly_return_negative(self):
        """Test mean yearly return with negative daily returns."""
        # -0.05% daily return ≈ -17% annual return
        daily_return = -0.0005
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 400

        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        yearly_return = get_mean_yearly_return(snapshots)
        # (1 - 0.0005)^365 - 1 ≈ -0.17 (-17%)
        expected = (1 + daily_return) ** 365 - 1
        self.assertAlmostEqual(yearly_return, expected, delta=0.01)

    def test_mean_yearly_return_zero(self):
        """Test mean yearly return when daily return is zero."""
        values = [1000, 1000, 1000, 1000, 1000]

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = self._create_snapshots(values, start_date)

        yearly_return = get_mean_yearly_return(snapshots)
        self.assertEqual(yearly_return, 0.0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_mean_yearly_return_empty_snapshots(self):
        """Test with empty snapshot list."""
        yearly_return = get_mean_yearly_return([])
        self.assertEqual(yearly_return, 0.0)

    def test_mean_yearly_return_single_snapshot(self):
        """Test with only one snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        yearly_return = get_mean_yearly_return(snapshots)
        self.assertEqual(yearly_return, 0.0)

    # ==========================================================
    # Custom Periods Per Year
    # ==========================================================

    def test_mean_yearly_return_custom_periods(self):
        """Test with custom periods_per_year parameter."""
        # 0.1% daily return
        daily_return = 0.001
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 400

        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        # Test with 252 trading days instead of 365 calendar days
        yearly_return = get_mean_yearly_return(snapshots, periods_per_year=252)
        expected = (1 + daily_return) ** 252 - 1
        self.assertAlmostEqual(yearly_return, expected, delta=0.02)

    # ==========================================================
    # Annualization Tests
    # ==========================================================

    def test_mean_yearly_return_annualization_accuracy(self):
        """Test that annualization correctly compounds daily returns."""
        # Exact 1% daily return
        daily_return = 0.01
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 400

        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        yearly_return = get_mean_yearly_return(snapshots)
        # (1.01)^365 - 1 ≈ 3678% (very high due to compounding)
        expected = (1 + daily_return) ** 365 - 1
        self.assertAlmostEqual(yearly_return, expected, delta=0.5)

    def test_mean_yearly_return_realistic_scenario(self):
        """Test with realistic annual return (~10%)."""
        # Daily return for ~10% annual
        daily_return = (1.10) ** (1/365) - 1  # ≈ 0.026%
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 400

        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        yearly_return = get_mean_yearly_return(snapshots)
        # Should be close to 10% annual return
        self.assertAlmostEqual(yearly_return, 0.10, delta=0.01)

    # ==========================================================
    # Integration Tests
    # ==========================================================

    def test_mean_yearly_return_matches_daily_compounded(self):
        """Test that yearly return matches compounded daily return."""
        # Use real-world-like data
        daily_return = 0.0003  # 0.03% daily
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        days = 500

        values = [1000 * ((1 + daily_return) ** i) for i in range(days + 1)]
        snapshots = self._create_snapshots(values, start_date)

        mean_daily = get_mean_daily_return(snapshots)
        mean_yearly = get_mean_yearly_return(snapshots)

        # Yearly should be approximately (1 + daily)^365 - 1
        expected_yearly = (1 + mean_daily) ** 365 - 1
        self.assertAlmostEqual(mean_yearly, expected_yearly, delta=0.001)

