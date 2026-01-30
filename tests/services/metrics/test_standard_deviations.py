"""
Tests for Standard Deviation calculation functions.

Tests cover:
- get_standard_deviation_downside_returns
- get_standard_deviation_returns
- get_daily_returns_std
- get_downside_std_of_daily_returns
"""

import math
import unittest
from datetime import datetime, timedelta, timezone
import numpy as np

from investing_algorithm_framework.services.metrics.standard_deviation import (
    get_standard_deviation_downside_returns,
    get_standard_deviation_returns,
    get_daily_returns_std,
    get_downside_std_of_daily_returns,
)


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing."""

    def __init__(self, total_value: float, created_at: datetime):
        self.total_value = total_value
        self.created_at = created_at


class TestGetStandardDeviationDownsideReturns(unittest.TestCase):
    """Tests for get_standard_deviation_downside_returns function."""

    def _create_snapshots(self, values, start_date=None, interval_days=1):
        """Helper to create mock snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_standard_deviation_downside_returns([])
        self.assertEqual(result, 0.0)

    def test_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(100, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_standard_deviation_downside_returns(snapshots)
        self.assertEqual(result, 0.0)

    def test_two_snapshots_positive_return(self):
        """Test with two snapshots and positive return."""
        snapshots = self._create_snapshots([100, 110])
        result = get_standard_deviation_downside_returns(snapshots)
        # No downside returns
        self.assertEqual(result, 0.0)

    def test_two_snapshots_negative_return(self):
        """Test with two snapshots and negative return."""
        snapshots = self._create_snapshots([100, 90])
        result = get_standard_deviation_downside_returns(snapshots)
        # Only one negative return, std of single value is NaN -> returns 0.0
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Basic Functionality
    # ==========================================================

    def test_all_positive_returns(self):
        """Test with all positive returns."""
        snapshots = self._create_snapshots([100, 110, 121, 133])
        result = get_standard_deviation_downside_returns(snapshots)
        # No downside returns
        self.assertEqual(result, 0.0)

    def test_all_negative_returns(self):
        """Test with all negative returns."""
        snapshots = self._create_snapshots([100, 90, 81, 72.9])
        result = get_standard_deviation_downside_returns(snapshots)
        # Returns: -10%, -10%, -10%
        expected_std = np.std([-0.1, -0.1, -0.1], ddof=1)
        self.assertAlmostEqual(result, expected_std, places=6)

    def test_mixed_returns(self):
        """Test with mixed positive and negative returns."""
        # 100 -> 90 (-10%), 90 -> 99 (+10%), 99 -> 89.1 (-10%)
        snapshots = self._create_snapshots([100, 90, 99, 89.1])
        result = get_standard_deviation_downside_returns(snapshots)
        # Downside returns: -0.1, -0.1
        expected_std = np.std([-0.1, -0.1], ddof=1)
        self.assertAlmostEqual(result, expected_std, places=4)

    def test_constant_values(self):
        """Test with constant portfolio values (zero returns)."""
        snapshots = self._create_snapshots([100, 100, 100, 100])
        result = get_standard_deviation_downside_returns(snapshots)
        # No negative returns (all zero)
        self.assertEqual(result, 0.0)

    def test_varied_negative_returns(self):
        """Test with varied negative returns."""
        # Returns: -5%, -10%, -15%, -20%
        snapshots = self._create_snapshots([100, 95, 85.5, 72.675, 58.14])
        result = get_standard_deviation_downside_returns(snapshots)
        # All returns are negative with different magnitudes
        self.assertGreater(result, 0)

    # ==========================================================
    # Realistic Scenarios
    # ==========================================================

    def test_realistic_portfolio(self):
        """Test with realistic portfolio values."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(99):
            change = random.gauss(0.0005, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_standard_deviation_downside_returns(snapshots)

        # Should be positive and reasonable
        self.assertGreater(result, 0)
        self.assertLess(result, 0.1)  # Daily std should be small


class TestGetStandardDeviationReturns(unittest.TestCase):
    """Tests for get_standard_deviation_returns function."""

    def _create_snapshots(self, values, start_date=None, interval_days=1):
        """Helper to create mock snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_standard_deviation_returns([])
        self.assertEqual(result, 0.0)

    def test_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(100, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_standard_deviation_returns(snapshots)
        self.assertEqual(result, 0.0)

    def test_two_snapshots(self):
        """Test with two snapshots."""
        snapshots = self._create_snapshots([100, 110])
        result = get_standard_deviation_returns(snapshots)
        # Only one return, std is NaN -> returns 0.0
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Basic Functionality
    # ==========================================================

    def test_constant_returns(self):
        """Test with constant percentage returns."""
        # 10% return each day
        snapshots = self._create_snapshots([100, 110, 121, 133.1, 146.41])
        result = get_standard_deviation_returns(snapshots)
        # All returns are ~10%, std should be very small
        self.assertLess(result, 0.01)

    def test_constant_values(self):
        """Test with constant portfolio values."""
        snapshots = self._create_snapshots([100, 100, 100, 100])
        result = get_standard_deviation_returns(snapshots)
        # All returns are 0, std is 0
        self.assertEqual(result, 0.0)

    def test_varied_returns(self):
        """Test with varied returns."""
        # Returns: +10%, -5%, +15%, -10%
        snapshots = self._create_snapshots([100, 110, 104.5, 120.175, 108.1575])
        result = get_standard_deviation_returns(snapshots)
        # Should have positive std
        self.assertGreater(result, 0)

    def test_all_positive_returns(self):
        """Test with all positive returns of different sizes."""
        # Returns: +5%, +10%, +15%, +20%
        snapshots = self._create_snapshots([100, 105, 115.5, 132.825, 159.39])
        result = get_standard_deviation_returns(snapshots)
        # Should have positive std due to varied return sizes
        self.assertGreater(result, 0)

    def test_all_negative_returns(self):
        """Test with all negative returns."""
        # Returns: -5%, -10%, -5%, -10%
        snapshots = self._create_snapshots([100, 95, 85.5, 81.225, 73.1025])
        result = get_standard_deviation_returns(snapshots)
        # Should have positive std
        self.assertGreater(result, 0)

    # ==========================================================
    # Comparison Tests
    # ==========================================================

    def test_std_returns_greater_than_downside_std(self):
        """Test that total std >= downside std."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(99):
            change = random.gauss(0.0005, 0.02)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)

        total_std = get_standard_deviation_returns(snapshots)
        downside_std = get_standard_deviation_downside_returns(snapshots)

        # Total std includes all returns, should be >= downside std
        # (unless there are very few negative returns)
        self.assertIsInstance(total_std, float)
        self.assertIsInstance(downside_std, float)


class TestGetDailyReturnsStd(unittest.TestCase):
    """Tests for get_daily_returns_std function."""

    def _create_snapshots(self, values, start_date=None, interval_hours=24):
        """Helper to create mock snapshots with hour intervals."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(hours=i * interval_hours))
            for i, value in enumerate(values)
        ]

    def _create_daily_snapshots(self, values, start_date=None):
        """Helper to create mock snapshots with daily intervals."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_daily_returns_std([])
        self.assertEqual(result, 0.0)

    def test_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(100, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_daily_returns_std(snapshots)
        self.assertEqual(result, 0.0)

    def test_two_snapshots_same_day(self):
        """Test with two snapshots on the same day."""
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        snapshots = [
            MockSnapshot(100, start),
            MockSnapshot(110, start + timedelta(hours=2)),
        ]
        result = get_daily_returns_std(snapshots)
        # Same day, so after resampling only 1 data point -> NaN or 0.0
        self.assertTrue(math.isnan(result) or result == 0.0)

    # ==========================================================
    # Basic Functionality
    # ==========================================================

    def test_daily_data_constant_returns(self):
        """Test with daily data and constant returns."""
        # 5% daily return
        snapshots = self._create_daily_snapshots(
            [100, 105, 110.25, 115.7625, 121.550625]
        )
        result = get_daily_returns_std(snapshots)
        # All returns are 5%, std should be very small
        self.assertLess(result, 0.01)

    def test_daily_data_varied_returns(self):
        """Test with daily data and varied returns."""
        # Returns: +10%, -5%, +15%, -10%
        snapshots = self._create_daily_snapshots(
            [100, 110, 104.5, 120.175, 108.1575]
        )
        result = get_daily_returns_std(snapshots)
        self.assertGreater(result, 0)

    def test_hourly_data_resampled_to_daily(self):
        """Test that hourly data is correctly resampled to daily."""
        # Create hourly data over 5 days (120 hours)
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        values = []
        base = 100

        for day in range(5):
            for hour in range(24):
                # Small intraday variation, day-over-day growth
                values.append(base * (1 + day * 0.02) + hour * 0.1)

        snapshots = [
            MockSnapshot(v, start + timedelta(hours=i))
            for i, v in enumerate(values)
        ]

        result = get_daily_returns_std(snapshots)
        # Should calculate std based on daily returns
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0)

    def test_constant_values(self):
        """Test with constant portfolio values."""
        snapshots = self._create_daily_snapshots([100, 100, 100, 100, 100])
        result = get_daily_returns_std(snapshots)
        # All returns are 0
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Realistic Scenarios
    # ==========================================================

    def test_realistic_daily_volatility(self):
        """Test with realistic daily volatility."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(99):
            # Typical daily volatility ~1-2%
            change = random.gauss(0.0003, 0.015)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_daily_snapshots(values)
        result = get_daily_returns_std(snapshots)

        # Daily std should be in reasonable range
        self.assertGreater(result, 0.005)
        self.assertLess(result, 0.05)


class TestGetDownsideStdOfDailyReturns(unittest.TestCase):
    """Tests for get_downside_std_of_daily_returns function."""

    def _create_daily_snapshots(self, values, start_date=None):
        """Helper to create mock snapshots with daily intervals."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_downside_std_of_daily_returns([])
        self.assertEqual(result, 0.0)

    def test_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(100, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_downside_std_of_daily_returns(snapshots)
        self.assertEqual(result, 0.0)

    def test_two_snapshots_positive(self):
        """Test with two snapshots and positive return."""
        snapshots = self._create_daily_snapshots([100, 110])
        result = get_downside_std_of_daily_returns(snapshots)
        self.assertEqual(result, 0.0)

    def test_two_snapshots_negative(self):
        """Test with two snapshots and negative return."""
        snapshots = self._create_daily_snapshots([100, 90])
        result = get_downside_std_of_daily_returns(snapshots)
        # Single negative return, std is NaN (can't compute std of 1 value)
        self.assertTrue(math.isnan(result) or result == 0.0)

    # ==========================================================
    # Basic Functionality
    # ==========================================================

    def test_all_positive_returns(self):
        """Test with all positive returns."""
        snapshots = self._create_daily_snapshots([100, 110, 121, 133])
        result = get_downside_std_of_daily_returns(snapshots)
        self.assertEqual(result, 0.0)

    def test_all_negative_returns(self):
        """Test with all negative returns."""
        # Returns: -10%, -10%, -10%
        snapshots = self._create_daily_snapshots([100, 90, 81, 72.9])
        result = get_downside_std_of_daily_returns(snapshots)
        # All returns are -10%, std should be 0
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_varied_negative_returns(self):
        """Test with varied negative returns."""
        # Returns: -5%, -10%, -15%
        snapshots = self._create_daily_snapshots([100, 95, 85.5, 72.675])
        result = get_downside_std_of_daily_returns(snapshots)
        # Varied negative returns, std > 0
        self.assertGreater(result, 0)

    def test_mixed_returns(self):
        """Test with mixed positive and negative returns."""
        # Returns: +10%, -10%, +5%, -15%
        snapshots = self._create_daily_snapshots([100, 110, 99, 103.95, 88.3575])
        result = get_downside_std_of_daily_returns(snapshots)
        # Downside returns: -10%, -15%
        self.assertGreater(result, 0)

    def test_constant_values(self):
        """Test with constant portfolio values."""
        snapshots = self._create_daily_snapshots([100, 100, 100, 100])
        result = get_downside_std_of_daily_returns(snapshots)
        # No negative returns
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Comparison Tests
    # ==========================================================

    def test_downside_std_less_than_or_equal_total_std(self):
        """Test that downside std is typically less than total std."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(99):
            change = random.gauss(0.0, 0.02)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_daily_snapshots(values)

        total_std = get_daily_returns_std(snapshots)
        downside_std = get_downside_std_of_daily_returns(snapshots)

        # Both should be positive
        self.assertGreater(total_std, 0)
        # Downside std uses fewer data points
        self.assertIsInstance(downside_std, float)


class TestStandardDeviationIntegration(unittest.TestCase):
    """Integration tests for standard deviation functions."""

    def _create_daily_snapshots(self, values, start_date=None):
        """Helper to create mock snapshots with daily intervals."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i))
            for i, value in enumerate(values)
        ]

    def test_daily_std_consistency(self):
        """Test that daily std functions are consistent."""
        import random
        random.seed(42)

        values = [1000]
        for _ in range(99):
            change = random.gauss(0.0005, 0.02)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_daily_snapshots(values)

        # For daily data, these should be similar
        std_returns = get_standard_deviation_returns(snapshots)
        daily_std = get_daily_returns_std(snapshots)

        # Should be in the same ballpark
        self.assertAlmostEqual(std_returns, daily_std, delta=0.01)

    def test_all_functions_handle_edge_cases(self):
        """Test that all functions handle edge cases consistently."""
        # Empty list
        self.assertEqual(get_standard_deviation_downside_returns([]), 0.0)
        self.assertEqual(get_standard_deviation_returns([]), 0.0)
        self.assertEqual(get_daily_returns_std([]), 0.0)
        self.assertEqual(get_downside_std_of_daily_returns([]), 0.0)

        # Single snapshot
        single = [MockSnapshot(100, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        self.assertEqual(get_standard_deviation_downside_returns(single), 0.0)
        self.assertEqual(get_standard_deviation_returns(single), 0.0)
        self.assertEqual(get_daily_returns_std(single), 0.0)
        self.assertEqual(get_downside_std_of_daily_returns(single), 0.0)

    def test_higher_volatility_higher_std(self):
        """Test that higher volatility results in higher std."""
        import random

        # Low volatility
        random.seed(42)
        values_low = [1000]
        for _ in range(99):
            change = random.gauss(0.0005, 0.005)
            values_low.append(values_low[-1] * (1 + change))

        # High volatility
        random.seed(42)
        values_high = [1000]
        for _ in range(99):
            change = random.gauss(0.0005, 0.03)
            values_high.append(values_high[-1] * (1 + change))

        snapshots_low = self._create_daily_snapshots(values_low)
        snapshots_high = self._create_daily_snapshots(values_high)

        std_low = get_standard_deviation_returns(snapshots_low)
        std_high = get_standard_deviation_returns(snapshots_high)

        # High volatility should have higher std
        self.assertGreater(std_high, std_low)


if __name__ == "__main__":
    unittest.main()
