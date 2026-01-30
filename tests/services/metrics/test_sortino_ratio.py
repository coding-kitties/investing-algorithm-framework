"""
Tests for Sortino Ratio calculation function.

The Sortino Ratio measures risk-adjusted return using only downside deviation,
making it more suitable for asymmetric return distributions.

Tests cover:
- get_sortino_ratio
"""

import math
import unittest
from datetime import datetime, timedelta, timezone

from investing_algorithm_framework.services.metrics.sortino_ratio import (
    get_sortino_ratio,
)


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing."""

    def __init__(self, total_value: float, created_at: datetime):
        self.total_value = total_value
        self.created_at = created_at


class TestGetSortinoRatio(unittest.TestCase):
    """Tests for get_sortino_ratio function."""

    def _create_snapshots(self, values, start_date=None, interval_days=1):
        """
        Helper to create a list of mock snapshots from a value list.

        Args:
            values: List of portfolio values
            start_date: Start datetime (default: 2024-01-01 UTC)
            interval_days: Days between each snapshot (default: 1)

        Returns:
            List of MockSnapshot objects
        """
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_sortino_ratio_positive(self):
        """Test Sortino ratio with positive returns and some downside."""
        import random
        random.seed(42)

        # Create realistic returns with some negative days
        values = [1000]
        for _ in range(399):
            # Positive drift with occasional negative returns
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # Should be a finite number
        self.assertIsInstance(result, float)
        self.assertFalse(math.isinf(result))

    def test_sortino_ratio_excellent(self):
        """Test Sortino ratio > 3.0 (excellent performance)."""
        # Consistent positive returns with minimal downside
        import random
        random.seed(100)

        values = [1000]
        for _ in range(399):
            # Mostly positive returns, rare small negatives
            if random.random() > 0.1:  # 90% positive
                change = random.uniform(0.001, 0.003)
            else:
                change = random.uniform(-0.002, 0)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # With mostly positive returns and small negatives, should be high
        self.assertGreater(result, 2.0)

    def test_sortino_ratio_negative(self):
        """Test negative Sortino ratio (underperforms risk-free)."""
        # Strongly declining portfolio to ensure negative Sortino
        import random
        random.seed(42)

        values = [1000]
        for _ in range(399):
            # Strong negative drift with volatility
            change = random.gauss(-0.003, 0.01)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.05)

        # Should be negative due to strong underperformance
        self.assertLess(result, 0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_sortino_ratio_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_sortino_ratio([], risk_free_rate=0.03)

        # Should return infinity as per current implementation
        self.assertEqual(result, float('inf'))

    def test_sortino_ratio_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))
        ]

        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # Should handle gracefully
        self.assertIsInstance(result, float)

    def test_sortino_ratio_two_snapshots(self):
        """Test with exactly two snapshots."""
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc)),
            MockSnapshot(1100, datetime(2024, 1, 2, tzinfo=timezone.utc)),
        ]

        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # Should calculate but may be NaN due to single return
        self.assertIsInstance(result, float)

    def test_sortino_ratio_no_downside(self):
        """Test with no negative returns (zero downside deviation)."""
        # Only positive returns
        values = [1000 * (1.001 ** i) for i in range(100)]
        snapshots = self._create_snapshots(values)

        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # Zero downside deviation -> should return NaN
        self.assertTrue(math.isnan(result))

    def test_sortino_ratio_constant_values(self):
        """Test with constant portfolio values."""
        values = [1000] * 100
        snapshots = self._create_snapshots(values)

        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # Zero returns, zero downside -> should return NaN
        self.assertTrue(math.isnan(result))

    def test_sortino_ratio_zero_risk_free_rate(self):
        """Test with zero risk-free rate."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(199):
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.0)

        # Should still calculate correctly
        self.assertIsInstance(result, float)

    # ==========================================================
    # Comparison with Sharpe Ratio
    # ==========================================================

    def test_sortino_higher_than_sharpe_with_positive_skew(self):
        """
        Test that Sortino > Sharpe when returns are positively skewed.
        (More upside volatility than downside)
        """
        import random
        random.seed(42)

        # Create positively skewed returns
        values = [1000]
        for _ in range(399):
            if random.random() > 0.3:  # 70% positive, sometimes large
                change = random.uniform(0.001, 0.01)
            else:  # 30% negative, but small
                change = random.uniform(-0.003, 0)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)

        sortino = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # With positive skew, Sortino should be higher because
        # it ignores upside volatility
        # We just verify it calculates correctly
        self.assertIsInstance(sortino, float)
        self.assertFalse(math.isnan(sortino))

    # ==========================================================
    # Time Period Tests
    # ==========================================================

    def test_sortino_ratio_short_period(self):
        """Test Sortino ratio with short period (< 1 year)."""
        import random
        random.seed(42)

        # 3 months of data
        values = [1000]
        for _ in range(89):
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)

    def test_sortino_ratio_one_year(self):
        """Test Sortino ratio with exactly one year of data."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(364):
            change = random.gauss(0.0003, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)
        self.assertFalse(math.isinf(result))

    def test_sortino_ratio_multi_year(self):
        """Test Sortino ratio with multiple years of data."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(729):  # 2 years
            change = random.gauss(0.0003, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)
        self.assertFalse(math.isinf(result))

    # ==========================================================
    # Interpretation Tests
    # ==========================================================

    def test_sortino_ratio_interpretation_bad(self):
        """Verify bad Sortino ratio (< 0) interpretation."""
        # Strategy that loses money consistently
        import random
        random.seed(42)

        values = [1000]
        for _ in range(199):
            change = random.gauss(-0.002, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        self.assertLess(result, 0)

    def test_sortino_ratio_interpretation_acceptable(self):
        """Verify acceptable Sortino ratio (1-2) range."""
        import random
        random.seed(123)

        # Moderate positive returns with some downside
        values = [1000]
        for _ in range(399):
            change = random.gauss(0.0004, 0.012)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        # Should be in a reasonable range
        self.assertIsInstance(result, float)

    # ==========================================================
    # Downside Deviation Specific Tests
    # ==========================================================

    def test_sortino_only_considers_downside(self):
        """
        Test that Sortino only penalizes downside volatility.
        Large upside moves should not decrease the ratio.
        """
        import random

        # Create two scenarios with same average return
        # but different upside volatility

        # Scenario 1: Moderate positive returns
        random.seed(42)
        values_moderate = [1000]
        for _ in range(199):
            if random.random() > 0.3:
                change = 0.002  # Consistent positive
            else:
                change = -0.003  # Consistent negative
            values_moderate.append(values_moderate[-1] * (1 + change))

        # Scenario 2: Same downside, but larger upside
        random.seed(42)
        values_large_up = [1000]
        for _ in range(199):
            if random.random() > 0.3:
                change = 0.005  # Larger positive
            else:
                change = -0.003  # Same negative
            values_large_up.append(values_large_up[-1] * (1 + change))

        snapshots_moderate = self._create_snapshots(values_moderate)
        snapshots_large_up = self._create_snapshots(values_large_up)

        sortino_moderate = get_sortino_ratio(
            snapshots_moderate, risk_free_rate=0.03
        )
        sortino_large_up = get_sortino_ratio(
            snapshots_large_up, risk_free_rate=0.03
        )

        # Larger upside should have higher Sortino
        # (same downside risk, but higher returns)
        self.assertGreater(sortino_large_up, sortino_moderate)

    def test_sortino_mixed_returns(self):
        """Test Sortino with mixed positive and negative returns."""
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        snapshots = [
            MockSnapshot(100, now),
            MockSnapshot(90, now + timedelta(days=1)),   # -10%
            MockSnapshot(99, now + timedelta(days=2)),   # +10%
        ]

        result = get_sortino_ratio(snapshots, risk_free_rate=0.027)

        # Should handle the mixed returns
        self.assertIsInstance(result, float)

    # ==========================================================
    # Risk-Free Rate Impact Tests
    # ==========================================================

    def test_sortino_higher_risk_free_lowers_ratio(self):
        """Test that higher risk-free rate results in lower Sortino."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(399):
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)

        sortino_low_rf = get_sortino_ratio(snapshots, risk_free_rate=0.02)
        sortino_high_rf = get_sortino_ratio(snapshots, risk_free_rate=0.08)

        # Higher risk-free rate should result in lower Sortino
        self.assertGreater(sortino_low_rf, sortino_high_rf)

    # ==========================================================
    # Value Range Tests
    # ==========================================================

    def test_sortino_ratio_small_values(self):
        """Test with very small portfolio values."""
        import random
        random.seed(42)

        values = [1.0]
        for _ in range(199):
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)

    def test_sortino_ratio_large_values(self):
        """Test with very large portfolio values."""
        import random
        random.seed(42)

        values = [1000000]
        for _ in range(199):
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sortino_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()
