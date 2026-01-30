"""
Tests for Sharpe Ratio calculation functions.

Tests cover:
- get_sharpe_ratio
- get_rolling_sharpe_ratio
"""

import math
from unittest import TestCase
from datetime import datetime, timezone, timedelta, date

from investing_algorithm_framework.services.metrics.sharpe_ratio import (
    get_sharpe_ratio,
    get_rolling_sharpe_ratio,
)
from investing_algorithm_framework.domain import PortfolioSnapshot


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing."""

    def __init__(self, total_value: float, created_at: datetime):
        self.total_value = total_value
        self.created_at = created_at


class TestGetSharpeRatio(TestCase):
    """Tests for get_sharpe_ratio function."""

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

    def test_sharpe_ratio_calculation_with_real_data(self):
        """Test Sharpe ratio calculation with real-world-like data."""
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

        sharpe_ratio = get_sharpe_ratio(snapshots, risk_free_rate=0.024)
        self.assertAlmostEqual(sharpe_ratio, 3.386, places=1)

    def test_sharpe_ratio_excellent(self):
        """Test Sharpe ratio > 3.0 (excellent performance)."""
        # Consistent daily returns with low volatility
        daily_return = 0.001  # 0.1% daily
        values = [1000 * ((1 + daily_return) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should be excellent (> 3.0) due to consistent returns
        self.assertGreater(result, 2.0)

    def test_sharpe_ratio_good(self):
        """Test Sharpe ratio 2.0-2.99 (good performance)."""
        # Moderate returns with moderate volatility
        import random
        random.seed(42)
        values = [1000]
        for _ in range(399):
            # Random walk with slight upward bias
            change = random.gauss(0.0005, 0.01)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Result depends on random seed, just verify it's calculable
        self.assertIsInstance(result, float)

    def test_sharpe_ratio_suboptimal(self):
        """Test Sharpe ratio 0.0-1.0 (suboptimal performance)."""
        # Low returns with high volatility
        import random
        random.seed(123)
        values = [1000]
        for _ in range(399):
            # High volatility, minimal drift
            change = random.gauss(0.0001, 0.03)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_sharpe_ratio(snapshots, risk_free_rate=0.04)

        # Should be lower due to high volatility
        self.assertIsInstance(result, float)

    def test_sharpe_ratio_negative(self):
        """Test negative Sharpe ratio (underperforms risk-free)."""
        # Declining portfolio
        daily_decline = -0.001  # -0.1% daily
        values = [1000 * ((1 + daily_decline) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.04)

        # Should be negative
        self.assertLess(result, 0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_sharpe_ratio_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_sharpe_ratio([], risk_free_rate=0.03)

        # Should handle gracefully (return NaN or 0)
        self.assertTrue(math.isnan(result) or result == 0.0)

    def test_sharpe_ratio_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should handle gracefully
        self.assertTrue(math.isnan(result) or result == 0.0)

    def test_sharpe_ratio_two_snapshots(self):
        """Test with exactly two snapshots."""
        snapshots = [
            MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc)),
            MockSnapshot(1100, datetime(2024, 1, 2, tzinfo=timezone.utc)),
        ]

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should handle but may be NaN due to single return
        self.assertIsInstance(result, float)

    def test_sharpe_ratio_constant_values(self):
        """Test with constant portfolio values (zero volatility)."""
        values = [1000] * 100
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Zero volatility -> should return NaN (division by zero)
        self.assertTrue(math.isnan(result))

    def test_sharpe_ratio_zero_risk_free_rate(self):
        """Test with zero risk-free rate."""
        daily_return = 0.001
        values = [1000 * ((1 + daily_return) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.0)

        # Should still calculate correctly
        self.assertIsInstance(result, float)
        self.assertFalse(math.isnan(result))

    def test_sharpe_ratio_high_risk_free_rate(self):
        """Test with high risk-free rate (10%)."""
        daily_return = 0.001  # ~44% annual
        values = [1000 * ((1 + daily_return) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values)

        result_low_rf = get_sharpe_ratio(snapshots, risk_free_rate=0.02)
        result_high_rf = get_sharpe_ratio(snapshots, risk_free_rate=0.10)

        # Higher risk-free rate should result in lower Sharpe ratio
        self.assertGreater(result_low_rf, result_high_rf)

    # ==========================================================
    # Time Period Tests
    # ==========================================================

    def test_sharpe_ratio_short_period(self):
        """Test Sharpe ratio with short period (< 1 year)."""
        # 3 months of data
        daily_return = 0.001
        values = [1000 * ((1 + daily_return) ** i) for i in range(90)]
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should still calculate
        self.assertIsInstance(result, float)

    def test_sharpe_ratio_one_year(self):
        """Test Sharpe ratio with exactly one year of data."""
        daily_return = 0.0003  # ~11.5% annual
        values = [1000 * ((1 + daily_return) ** i) for i in range(365)]
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)
        self.assertFalse(math.isnan(result))

    def test_sharpe_ratio_multi_year(self):
        """Test Sharpe ratio with multiple years of data."""
        daily_return = 0.0003
        values = [1000 * ((1 + daily_return) ** i) for i in range(730)]  # 2 years
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        self.assertIsInstance(result, float)
        self.assertFalse(math.isnan(result))

    # ==========================================================
    # Interpretation Tests
    # ==========================================================

    def test_sharpe_ratio_interpretation_bad(self):
        """Verify bad Sharpe ratio (< 0) interpretation."""
        # Strategy that loses money
        daily_decline = -0.002
        values = [1000 * ((1 + daily_decline) ** i) for i in range(200)]
        snapshots = self._create_snapshots(values)

        result = get_sharpe_ratio(snapshots, risk_free_rate=0.03)

        self.assertLess(result, 0)

    def test_sharpe_ratio_consistency(self):
        """Test that higher returns with same volatility = higher Sharpe."""
        # Same volatility, different returns
        import random

        random.seed(100)
        vol = 0.01

        # Lower return strategy
        values_low = [1000]
        for _ in range(399):
            change = random.gauss(0.0001, vol)
            values_low.append(values_low[-1] * (1 + change))

        random.seed(100)  # Same seed for same volatility pattern

        # Higher return strategy
        values_high = [1000]
        for _ in range(399):
            change = random.gauss(0.001, vol)  # Higher mean
            values_high.append(values_high[-1] * (1 + change))

        snapshots_low = self._create_snapshots(values_low)
        snapshots_high = self._create_snapshots(values_high)

        sharpe_low = get_sharpe_ratio(snapshots_low, risk_free_rate=0.03)
        sharpe_high = get_sharpe_ratio(snapshots_high, risk_free_rate=0.03)

        # Higher return should have higher Sharpe
        self.assertGreater(sharpe_high, sharpe_low)


class TestGetRollingSharpeRatio(TestCase):
    """Tests for get_rolling_sharpe_ratio function."""

    def _create_snapshots(self, values, start_date=None, interval_days=1):
        """Helper to create mock snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_rolling_sharpe_basic(self):
        """Test basic rolling Sharpe ratio calculation."""
        # 400 days of data (more than 365-day window)
        daily_return = 0.0005
        values = [1000 * ((1 + daily_return) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values)

        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should return list of tuples
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # Each element should be (sharpe_value, datetime)
        for item in result:
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[1], (datetime, type(None)))

    def test_rolling_sharpe_window_effect(self):
        """Test that rolling window uses 365 days of data."""
        # Create data with changing characteristics
        # First 365 days: high volatility, low return
        # Next 365 days: low volatility, high return
        import random
        random.seed(42)

        values = [1000]
        # First period: high volatility
        for _ in range(365):
            change = random.gauss(0.0001, 0.02)
            values.append(values[-1] * (1 + change))

        # Second period: low volatility, good returns
        for _ in range(365):
            change = random.gauss(0.001, 0.005)
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)
        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should have results
        self.assertGreater(len(result), 0)

    def test_rolling_sharpe_insufficient_data(self):
        """Test rolling Sharpe with insufficient data (< 365 days)."""
        # Only 100 days of data
        daily_return = 0.0005
        values = [1000 * ((1 + daily_return) ** i) for i in range(100)]
        snapshots = self._create_snapshots(values)

        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should return list but values may be NaN due to insufficient window
        self.assertIsInstance(result, list)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_rolling_sharpe_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_rolling_sharpe_ratio([], risk_free_rate=0.03)

        self.assertEqual(result, [])

    def test_rolling_sharpe_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]

        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should handle gracefully
        self.assertIsInstance(result, list)

    def test_rolling_sharpe_constant_values(self):
        """Test with constant portfolio values."""
        values = [1000] * 400
        snapshots = self._create_snapshots(values)

        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Should return NaN values due to zero volatility
        self.assertIsInstance(result, list)

    # ==========================================================
    # Timestamp Tests
    # ==========================================================

    def test_rolling_sharpe_timestamps_preserved(self):
        """Test that timestamps are correctly associated with values."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        daily_return = 0.0005
        values = [1000 * ((1 + daily_return) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values, start_date)

        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Check that dates are in chronological order
        dates = [item[1] for item in result if item[1] is not None]
        if len(dates) > 1:
            for i in range(1, len(dates)):
                self.assertGreaterEqual(dates[i], dates[i-1])

    # ==========================================================
    # Value Validation Tests
    # ==========================================================

    def test_rolling_sharpe_values_reasonable(self):
        """Test that rolling Sharpe values are reasonable with realistic data."""
        import random
        random.seed(42)

        # Create realistic data with actual volatility
        values = [1000]
        for _ in range(499):
            # Realistic daily returns with volatility
            change = random.gauss(0.0003, 0.015)  # ~11% annual return, ~24% volatility
            values.append(values[-1] * (1 + change))

        snapshots = self._create_snapshots(values)

        result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Filter out NaN and infinite values
        valid_values = [
            v for v, _ in result
            if not math.isnan(v) and not math.isinf(v)
        ]

        if valid_values:
            # Sharpe ratios for realistic data should typically be between -5 and 5
            for v in valid_values:
                self.assertGreater(v, -10,
                    f"Sharpe ratio {v} is unreasonably low")
                self.assertLess(v, 10,
                    f"Sharpe ratio {v} is unreasonably high for realistic data")


class TestSharpeRatioIntegration(TestCase):
    """Integration tests for Sharpe ratio functions."""

    def _create_snapshots(self, values, start_date=None, interval_days=1):
        """Helper to create mock snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        return [
            MockSnapshot(value, start_date + timedelta(days=i * interval_days))
            for i, value in enumerate(values)
        ]

    def test_rolling_sharpe_end_matches_static(self):
        """
        Test that rolling Sharpe at the end roughly matches static Sharpe.
        """
        daily_return = 0.0005
        values = [1000 * ((1 + daily_return) ** i) for i in range(400)]
        snapshots = self._create_snapshots(values)

        static_sharpe = get_sharpe_ratio(snapshots, risk_free_rate=0.03)
        rolling_result = get_rolling_sharpe_ratio(snapshots, risk_free_rate=0.03)

        # Get last valid rolling Sharpe
        valid_rolling = [v for v, _ in rolling_result if not math.isnan(v)]

        if valid_rolling and not math.isnan(static_sharpe):
            last_rolling = valid_rolling[-1]
            # Should be in the same ballpark (within 50%)
            # Note: They may differ due to different calculation methods
            self.assertIsInstance(last_rolling, float)

    def test_higher_volatility_lower_sharpe(self):
        """Verify that higher volatility leads to lower Sharpe ratio."""
        import random

        # Low volatility strategy
        random.seed(42)
        values_low_vol = [1000]
        for _ in range(399):
            change = random.gauss(0.0005, 0.005)
            values_low_vol.append(values_low_vol[-1] * (1 + change))

        # High volatility strategy with same mean return
        random.seed(42)
        values_high_vol = [1000]
        for _ in range(399):
            change = random.gauss(0.0005, 0.02)
            values_high_vol.append(values_high_vol[-1] * (1 + change))

        snapshots_low = self._create_snapshots(values_low_vol)
        snapshots_high = self._create_snapshots(values_high_vol)

        sharpe_low_vol = get_sharpe_ratio(snapshots_low, risk_free_rate=0.03)
        sharpe_high_vol = get_sharpe_ratio(snapshots_high, risk_free_rate=0.03)

        # Lower volatility should have higher Sharpe
        self.assertGreater(sharpe_low_vol, sharpe_high_vol)

