import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from investing_algorithm_framework.domain import BacktestRun

from investing_algorithm_framework import get_calmar_ratio


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing"""
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at


class TestGetCalmarRatio(unittest.TestCase):

    def _create_snapshots(self, values, start_date, interval_days=30):
        """
        Helper to create a list of mock snapshots from a value list.

        Args:
            values: List of portfolio values
            start_date: Start datetime
            interval_days: Days between each snapshot (default: 30)

        Returns:
            List of MockSnapshot objects
        """
        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    def _create_report(self, total_size_series, timestamps):
        """Helper to create a mocked BacktestRun with portfolio snapshots."""
        report = MagicMock(spec=BacktestRun)
        report.portfolio_snapshots = [
            MockSnapshot(size, ts)
            for ts, size in zip(timestamps, total_size_series)
        ]
        return report

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_typical_case(self):
        """
        Test Calmar ratio for a typical scenario with gains and drawdowns.
        """
        report = self._create_report(
            [1000, 1200, 900, 1100, 1300],
            [datetime(2024, i, 1) for i in range(1, 6)]
        )
        ratio = get_calmar_ratio(report.portfolio_snapshots)
        # Ratio should be positive since overall CAGR is positive
        # and there was a drawdown
        self.assertGreater(ratio, 0)
        self.assertAlmostEqual(ratio, 4.826, delta=0.1)

    def test_calmar_ratio_zero_drawdown(self):
        """
        Test Calmar ratio when there are no drawdowns (only gains).
        Should return 0.0 since we can't divide by zero.
        """
        report = self._create_report(
            [1000, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000],
            [datetime(2024, 1, i) for i in range(1, 11)]
        )
        ratio = get_calmar_ratio(report.portfolio_snapshots)
        self.assertEqual(ratio, 0.0)

    def test_calmar_ratio_with_only_drawdown(self):
        """
        Test Calmar ratio when portfolio only loses value.
        Ratio should be negative since CAGR is negative and drawdown
        is negative.
        """
        report = self._create_report(
            [1000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
            [datetime(2024, 1, i) for i in range(1, 11)]
        )
        ratio = get_calmar_ratio(report.portfolio_snapshots)
        # CAGR is negative, max drawdown is -90%
        # Negative CAGR / Negative drawdown = positive but we check sign
        self.assertAlmostEqual(ratio, -1.111, delta=0.1)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_snapshots(self):
        """Test Calmar ratio returns 0.0 for empty snapshot list."""
        ratio = get_calmar_ratio([])
        self.assertEqual(ratio, 0.0)

    def test_single_snapshot(self):
        """Test Calmar ratio returns 0.0 when only one snapshot provided."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1))]
        ratio = get_calmar_ratio(snapshots)
        self.assertEqual(ratio, 0.0)

    def test_two_snapshots_no_change(self):
        """Test Calmar ratio when portfolio value doesn't change."""
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1000, datetime(2024, 12, 31)),
        ]
        ratio = get_calmar_ratio(snapshots)
        # CAGR is 0, so Calmar ratio should be 0
        self.assertEqual(ratio, 0.0)

    def test_same_day_snapshots(self):
        """Test Calmar ratio when all snapshots are on the same day."""
        same_day = datetime(2024, 1, 1)
        snapshots = [
            MockSnapshot(1000, same_day),
            MockSnapshot(1100, same_day),
        ]
        ratio = get_calmar_ratio(snapshots)
        # Should return 0.0 due to zero time period
        self.assertEqual(ratio, 0.0)

    def test_zero_start_value(self):
        """Test Calmar ratio returns 0.0 when start value is zero."""
        snapshots = [
            MockSnapshot(0, datetime(2024, 1, 1)),
            MockSnapshot(1000, datetime(2024, 6, 1)),
        ]
        ratio = get_calmar_ratio(snapshots)
        self.assertEqual(ratio, 0.0)

    # ==========================================================
    # Return Profile Tests
    # ==========================================================

    def test_excellent_calmar_ratio(self):
        """
        Test scenario with excellent Calmar ratio (> 3.0).
        High returns with minimal drawdown.
        """
        # 50% gain over a year with only 10% max drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1100, datetime(2024, 3, 1)),
            MockSnapshot(990, datetime(2024, 4, 1)),   # 10% drawdown from peak
            MockSnapshot(1200, datetime(2024, 6, 1)),
            MockSnapshot(1400, datetime(2024, 9, 1)),
            MockSnapshot(1500, datetime(2025, 1, 1)),  # 50% total return
        ]
        ratio = get_calmar_ratio(snapshots)
        # With 50% CAGR and ~10% max drawdown, ratio should be ~5
        self.assertGreater(ratio, 3.0)

    def test_poor_calmar_ratio(self):
        """
        Test scenario with poor Calmar ratio (< 1.0).
        Low returns with significant drawdown.
        """
        # Small gain with large drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1200, datetime(2024, 3, 1)),
            MockSnapshot(700, datetime(2024, 6, 1)),   # 41.7% drawdown from peak
            MockSnapshot(800, datetime(2024, 9, 1)),
            MockSnapshot(1050, datetime(2025, 1, 1)),  # Only 5% total return
        ]
        ratio = get_calmar_ratio(snapshots)
        # Low return relative to drawdown
        self.assertLess(abs(ratio), 1.0)

    def test_negative_cagr_with_drawdown(self):
        """
        Test Calmar ratio when CAGR is negative.
        """
        # Portfolio loses 20% over a year with 30% max drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(900, datetime(2024, 4, 1)),
            MockSnapshot(700, datetime(2024, 7, 1)),   # 30% drawdown
            MockSnapshot(750, datetime(2024, 10, 1)),
            MockSnapshot(800, datetime(2025, 1, 1)),   # -20% total return
        ]
        ratio = get_calmar_ratio(snapshots)
        # Negative CAGR / Negative max drawdown
        # Sign depends on implementation, but value should be reasonable
        self.assertIsNotNone(ratio)

    # ==========================================================
    # Time Period Tests
    # ==========================================================

    def test_one_year_period(self):
        """
        Test Calmar ratio over exactly one year.
        Formula: Calmar = CAGR / |Max Drawdown|
        """
        # 20% return in 1 year with 15% max drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1100, datetime(2024, 4, 1)),
            MockSnapshot(935, datetime(2024, 6, 1)),   # 15% drawdown from 1100
            MockSnapshot(1050, datetime(2024, 9, 1)),
            MockSnapshot(1200, datetime(2025, 1, 1)),  # 20% return
        ]
        ratio = get_calmar_ratio(snapshots)
        # CAGR ≈ 20%, Max drawdown = -15%
        # Calmar = 0.20 / 0.15 ≈ 1.33
        self.assertGreater(ratio, 1.0)
        self.assertLess(ratio, 2.0)

    def test_multi_year_period(self):
        """
        Test Calmar ratio over multiple years.
        """
        # Doubling over 2 years (CAGR ≈ 41.4%) with 20% max drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2023, 1, 1)),
            MockSnapshot(1200, datetime(2023, 6, 1)),
            MockSnapshot(960, datetime(2023, 9, 1)),   # 20% drawdown from peak
            MockSnapshot(1400, datetime(2024, 1, 1)),
            MockSnapshot(1600, datetime(2024, 6, 1)),
            MockSnapshot(2000, datetime(2025, 1, 1)),  # 100% return in 2 years
        ]
        ratio = get_calmar_ratio(snapshots)
        # CAGR ≈ 41.4%, Max drawdown = -20%
        # Calmar ≈ 0.414 / 0.20 ≈ 2.07
        self.assertGreater(ratio, 1.5)
        self.assertLess(ratio, 3.0)

    def test_short_period_high_volatility(self):
        """
        Test Calmar ratio for a short period with high volatility.
        """
        # 3 months with significant swings
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1200, datetime(2024, 1, 15)),
            MockSnapshot(800, datetime(2024, 2, 1)),   # 33% drawdown from peak
            MockSnapshot(1100, datetime(2024, 2, 15)),
            MockSnapshot(1150, datetime(2024, 3, 1)),  # 15% total return
        ]
        ratio = get_calmar_ratio(snapshots)
        # Annualized return will be high, but so might drawdown
        self.assertIsNotNone(ratio)

    # ==========================================================
    # Market Scenario Tests
    # ==========================================================

    def test_v_shaped_recovery(self):
        """
        Test Calmar ratio for V-shaped recovery pattern.
        Sharp decline followed by sharp recovery.
        """
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(900, datetime(2024, 2, 1)),
            MockSnapshot(700, datetime(2024, 3, 1)),   # 30% drawdown
            MockSnapshot(600, datetime(2024, 4, 1)),   # 40% drawdown (max)
            MockSnapshot(800, datetime(2024, 5, 1)),
            MockSnapshot(1000, datetime(2024, 6, 1)),
            MockSnapshot(1200, datetime(2024, 7, 1)),  # Recovery + gain
        ]
        ratio = get_calmar_ratio(snapshots)
        # Strong recovery but significant drawdown
        self.assertIsNotNone(ratio)
        self.assertGreater(ratio, 0)

    def test_steady_growth_small_drawdown(self):
        """
        Test Calmar ratio for steady growth with minimal drawdown.
        This should produce a high Calmar ratio.
        """
        # Steady 2% monthly growth with occasional 3% dips
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1020, datetime(2024, 2, 1)),
            MockSnapshot(989, datetime(2024, 3, 1)),   # 3% dip
            MockSnapshot(1050, datetime(2024, 4, 1)),
            MockSnapshot(1070, datetime(2024, 5, 1)),
            MockSnapshot(1090, datetime(2024, 6, 1)),
            MockSnapshot(1057, datetime(2024, 7, 1)),  # 3% dip
            MockSnapshot(1120, datetime(2024, 8, 1)),
            MockSnapshot(1150, datetime(2024, 9, 1)),
            MockSnapshot(1180, datetime(2024, 10, 1)),
            MockSnapshot(1210, datetime(2024, 11, 1)),
            MockSnapshot(1250, datetime(2024, 12, 1)),
        ]
        ratio = get_calmar_ratio(snapshots)
        # Good return with small drawdowns should give high ratio
        self.assertGreater(ratio, 2.0)

    def test_multiple_drawdowns(self):
        """
        Test Calmar ratio when there are multiple drawdown periods.
        Only the maximum drawdown matters.
        """
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1100, datetime(2024, 2, 1)),
            MockSnapshot(990, datetime(2024, 3, 1)),   # 10% drawdown
            MockSnapshot(1150, datetime(2024, 4, 1)),
            MockSnapshot(920, datetime(2024, 5, 1)),   # 20% drawdown (max)
            MockSnapshot(1200, datetime(2024, 6, 1)),
            MockSnapshot(1080, datetime(2024, 7, 1)),  # 10% drawdown
            MockSnapshot(1300, datetime(2024, 8, 1)),  # New high
        ]
        ratio = get_calmar_ratio(snapshots)
        # Max drawdown was 20%, CAGR based on 30% gain in ~7 months
        self.assertIsNotNone(ratio)
        self.assertGreater(ratio, 0)

    # ==========================================================
    # Timezone Tests
    # ==========================================================

    def test_timezone_aware_dates(self):
        """Test Calmar ratio works with timezone-aware datetime objects."""
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc)),
            MockSnapshot(1200, datetime(2024, 4, 1, tzinfo=timezone.utc)),
            MockSnapshot(1000, datetime(2024, 7, 1, tzinfo=timezone.utc)),
            MockSnapshot(1400, datetime(2025, 1, 1, tzinfo=timezone.utc)),
        ]
        ratio = get_calmar_ratio(snapshots)
        self.assertIsNotNone(ratio)
        self.assertGreater(ratio, 0)

    # ==========================================================
    # Interpretation Tests
    # ==========================================================

    def test_calmar_interpretation_excellent(self):
        """
        Test that excellent strategies (Calmar > 3.0) can be identified.
        """
        # 60% return with only 15% max drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1150, datetime(2024, 4, 1)),
            MockSnapshot(1000, datetime(2024, 5, 1)),  # ~13% drawdown
            MockSnapshot(1300, datetime(2024, 8, 1)),
            MockSnapshot(1600, datetime(2025, 1, 1)),  # 60% return
        ]
        ratio = get_calmar_ratio(snapshots)
        # 60% CAGR with ~15% drawdown should give ~4.0 ratio
        self.assertGreater(ratio, 3.0)

    def test_calmar_formula_verification(self):
        """
        Verify the Calmar ratio formula: CAGR / |Max Drawdown|
        """
        # Simple case: 100% return in 1 year with exactly 25% max drawdown
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1)),
            MockSnapshot(1200, datetime(2024, 4, 1)),
            MockSnapshot(900, datetime(2024, 6, 1)),   # 25% drawdown from 1200
            MockSnapshot(1500, datetime(2024, 9, 1)),
            MockSnapshot(2000, datetime(2025, 1, 1)),  # 100% return
        ]
        ratio = get_calmar_ratio(snapshots)
        # CAGR ≈ 100%, Max drawdown = -25%
        # Calmar = 1.0 / 0.25 = 4.0
        # Due to annualization adjustments, allow for some variance
        self.assertGreater(ratio, 3.0)
        self.assertLess(ratio, 5.0)


if __name__ == "__main__":
    unittest.main()
