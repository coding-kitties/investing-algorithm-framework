"""
Tests for recovery factor and recovery time calculation functions.

Tests cover:
- get_recovery_factor
- get_recovery_time
"""

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework.services.metrics.recovery import (
    get_recovery_factor,
    get_recovery_time,
)


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing."""

    def __init__(self, total_value: float, created_at: datetime, net_size: float = None):
        self.total_value = total_value
        self.created_at = created_at
        # net_size defaults to total_value if not specified
        self.net_size = net_size if net_size is not None else total_value


class TestGetRecoveryFactor(TestCase):
    """Tests for get_recovery_factor function."""

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

    def test_recovery_factor_basic(self):
        """Test basic recovery factor calculation."""
        # Start 1000, peak 1500, trough 1200, end 1800
        # Net profit = 1800 - 1000 = 800
        # Max drawdown = 1500 - 1200 = 300
        # Recovery factor = 800 / 300 = 2.67
        values = [1000, 1200, 1500, 1200, 1400, 1800]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Verify result is in expected range
        self.assertGreater(result, 2.0)
        self.assertLess(result, 3.0)

    def test_recovery_factor_excellent(self):
        """Test excellent recovery factor (> 5.0)."""
        # Small drawdown relative to large profit
        # Start 1000, slight dip to 980, end 1600
        # Net profit = 600, Max drawdown = 20
        # Recovery factor = 30
        values = [1000, 1020, 980, 1100, 1300, 1600]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        self.assertGreater(result, 5.0)

    def test_recovery_factor_poor(self):
        """Test poor recovery factor (< 1.0)."""
        # Large drawdown relative to small profit
        # Start 1000, peak 1500, trough 900, end 1100
        # Net profit = 100, Max drawdown = 600
        # Recovery factor = 0.167
        values = [1000, 1500, 900, 1000, 1100]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        self.assertLess(result, 1.0)

    def test_recovery_factor_moderate(self):
        """Test moderate recovery factor (1.5 - 2.0)."""
        # Start 1000, peak 1200, trough 1000, end 1300
        # Net profit = 300, Max drawdown = 200
        # Recovery factor = 1.5
        values = [1000, 1200, 1000, 1150, 1300]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        self.assertGreaterEqual(result, 1.0)
        self.assertLessEqual(result, 3.0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_recovery_factor_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_recovery_factor([])
        self.assertEqual(result, 0.0)

    def test_recovery_factor_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_recovery_factor(snapshots)
        # No profit, no drawdown
        self.assertEqual(result, 0.0)

    def test_recovery_factor_no_drawdown_with_profit(self):
        """Test with no drawdown but positive profit (returns infinity)."""
        # Monotonically increasing - no drawdown
        values = [1000, 1100, 1200, 1300, 1400]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # No drawdown, positive profit -> infinity
        self.assertEqual(result, float('inf'))

    def test_recovery_factor_no_drawdown_no_profit(self):
        """Test with no drawdown and no profit."""
        # Constant values
        values = [1000, 1000, 1000, 1000]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # No drawdown, no profit -> 0.0
        self.assertEqual(result, 0.0)

    def test_recovery_factor_negative_return(self):
        """Test with negative total return (overall loss)."""
        # Start 1000, peak 1200, end 800
        # Net profit = -200, Max drawdown = 400
        values = [1000, 1200, 1000, 800]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Negative profit / positive drawdown = negative factor
        self.assertLess(result, 0)

    def test_recovery_factor_breakeven(self):
        """Test when portfolio ends at starting value."""
        # Start 1000, peak 1200, trough 800, end 1000
        # Net profit = 0, Max drawdown = 400
        values = [1000, 1200, 800, 1000]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Zero profit -> 0.0
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Interpretation Tests
    # ==========================================================

    def test_recovery_factor_interpretation_poor(self):
        """Verify poor recovery factor interpretation (< 1.0)."""
        # Large drawdown, small profit
        values = [1000, 1500, 800, 1100]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        self.assertLess(result, 1.0)

    def test_recovery_factor_interpretation_weak(self):
        """Verify weak recovery factor interpretation (1.0 - 1.5)."""
        # Drawdown roughly equals profit
        values = [1000, 1300, 1000, 1300]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        self.assertGreaterEqual(result, 0.8)
        self.assertLessEqual(result, 1.6)

    def test_recovery_factor_interpretation_good(self):
        """Verify good recovery factor interpretation (2.0 - 3.0)."""
        # Profit is 2-3x the max drawdown
        values = [1000, 1200, 1100, 1400]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        self.assertGreater(result, 1.5)
        self.assertLess(result, 5.0)

    # ==========================================================
    # Value Range Tests
    # ==========================================================

    def test_recovery_factor_small_values(self):
        """Test with very small portfolio values."""
        values = [1.0, 1.2, 0.9, 1.5]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Should still calculate correctly
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_recovery_factor_large_values(self):
        """Test with very large portfolio values."""
        values = [1000000, 1200000, 900000, 1500000]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Should still calculate correctly
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    # ==========================================================
    # Drawdown Scenario Tests
    # ==========================================================

    def test_recovery_factor_multiple_drawdowns(self):
        """Test with multiple drawdown periods."""
        # Multiple dips, uses max drawdown
        values = [1000, 1100, 1000, 1200, 1000, 1300, 1100, 1500]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Net profit = 500, Max drawdown = 200 (from 1300 to 1100)
        self.assertGreater(result, 0)

    def test_recovery_factor_early_drawdown(self):
        """Test when max drawdown happens early."""
        values = [1000, 600, 800, 1000, 1200, 1400, 1600]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Net profit = 600, Max drawdown = 400
        # Recovery factor = 1.5
        self.assertGreater(result, 1.0)

    def test_recovery_factor_late_drawdown(self):
        """Test when max drawdown happens late."""
        values = [1000, 1200, 1400, 1600, 1100, 1300]
        snapshots = self._create_snapshots(values)

        result = get_recovery_factor(snapshots)

        # Net profit = 300, Max drawdown = 500
        self.assertLess(result, 1.0)


class TestGetRecoveryTime(TestCase):
    """Tests for get_recovery_time function."""

    def _create_snapshots(self, values, start_date=None, interval_days=1, net_sizes=None):
        """
        Helper to create a list of mock snapshots.

        Args:
            values: List of total_value
            start_date: Start datetime
            interval_days: Days between snapshots
            net_sizes: Optional list of net_size values (defaults to values)

        Returns:
            List of MockSnapshot objects
        """
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        if net_sizes is None:
            net_sizes = values

        return [
            MockSnapshot(
                total_value=value,
                created_at=start_date + timedelta(days=i * interval_days),
                net_size=net_size
            )
            for i, (value, net_size) in enumerate(zip(values, net_sizes))
        ]

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_recovery_time_basic(self):
        """Test basic recovery time calculation."""
        # Drawdown at day 2-3, recovery by day 5
        values = [1000, 1200, 900, 950, 1000, 1200]
        net_sizes = [1000, 1200, 900, 950, 1000, 1200]
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # Should return time to first recovery
        self.assertIsNotNone(result)

    def test_recovery_time_quick_recovery(self):
        """Test quick recovery (small drawdown, fast recovery)."""
        values = [1000, 950, 1000, 1100]
        net_sizes = [1000, 950, 1000, 1100]
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # Recovery should be fast
        self.assertGreaterEqual(result, 0)

    def test_recovery_time_slow_recovery(self):
        """Test slow recovery (long time to recover)."""
        # Drop and gradual recovery over many periods
        values = [1000, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # Recovery should take multiple periods
        self.assertGreater(result, 0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_recovery_time_empty_snapshots(self):
        """Test with empty snapshot list."""
        result = get_recovery_time([])
        self.assertEqual(result, 0.0)

    def test_recovery_time_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_recovery_time(snapshots)
        self.assertEqual(result, 0.0)

    def test_recovery_time_no_drawdown(self):
        """Test with no drawdown (monotonically increasing)."""
        values = [1000, 1100, 1200, 1300, 1400]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # No drawdown -> 0.0
        self.assertEqual(result, 0.0)

    def test_recovery_time_never_recovers(self):
        """Test when portfolio never recovers from drawdown."""
        # Drop and never fully recover
        values = [1000, 1200, 800, 850, 900, 950]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # May return 0.0 if no full recovery found
        self.assertIsNotNone(result)

    def test_recovery_time_constant_values(self):
        """Test with constant portfolio values."""
        values = [1000, 1000, 1000, 1000]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # No drawdown -> 0.0
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Time Interval Tests
    # ==========================================================

    def test_recovery_time_daily_intervals(self):
        """Test recovery time with daily intervals."""
        values = [1000, 800, 900, 1000, 1100]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(
            values, net_sizes=net_sizes, interval_days=1
        )

        result = get_recovery_time(snapshots)

        # Should be measured in days
        self.assertIsInstance(result, (int, float))

    def test_recovery_time_weekly_intervals(self):
        """Test recovery time with weekly intervals."""
        values = [1000, 800, 900, 1000, 1100]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(
            values, net_sizes=net_sizes, interval_days=7
        )

        result = get_recovery_time(snapshots)

        # Should be in days (weeks * 7)
        self.assertIsInstance(result, (int, float))

    def test_recovery_time_monthly_intervals(self):
        """Test recovery time with monthly intervals."""
        values = [1000, 800, 900, 1000, 1100]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(
            values, net_sizes=net_sizes, interval_days=30
        )

        result = get_recovery_time(snapshots)

        # Should be in days
        self.assertIsInstance(result, (int, float))

    # ==========================================================
    # Scenario Tests
    # ==========================================================

    def test_recovery_time_v_shaped_recovery(self):
        """Test V-shaped recovery (quick drop, quick recovery)."""
        values = [1000, 700, 1000, 1200]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # V-shape should have defined recovery time
        self.assertIsNotNone(result)

    def test_recovery_time_u_shaped_recovery(self):
        """Test U-shaped recovery (drop, flat, then recovery)."""
        values = [1000, 700, 700, 700, 700, 1000]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # U-shape should take longer
        self.assertIsNotNone(result)

    def test_recovery_time_w_shaped_recovery(self):
        """Test W-shaped recovery (double dip before recovery)."""
        values = [1000, 700, 900, 600, 800, 1000]
        net_sizes = values.copy()
        snapshots = self._create_snapshots(values, net_sizes=net_sizes)

        result = get_recovery_time(snapshots)

        # W-shape should have defined recovery time
        self.assertIsNotNone(result)


class TestRecoveryFactorAndTimeIntegration(TestCase):
    """Integration tests for recovery factor and recovery time together."""

    def _create_snapshots(self, values, start_date=None, interval_days=1):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        return [
            MockSnapshot(
                total_value=value,
                created_at=start_date + timedelta(days=i * interval_days),
                net_size=value
            )
            for i, value in enumerate(values)
        ]

    def test_high_recovery_factor_quick_recovery(self):
        """
        Test that high recovery factor often correlates with
        quick recovery time.
        """
        # Small drawdown, quick recovery, good profit
        values = [1000, 1100, 1050, 1200, 1400, 1600]
        snapshots = self._create_snapshots(values)

        recovery_factor = get_recovery_factor(snapshots)
        recovery_time = get_recovery_time(snapshots)

        # High recovery factor
        self.assertGreater(recovery_factor, 3.0)

    def test_low_recovery_factor_slow_recovery(self):
        """
        Test that low recovery factor may correlate with
        slow or no recovery.
        """
        # Large drawdown, partial recovery only
        values = [1000, 1500, 700, 800, 900, 950]
        snapshots = self._create_snapshots(values)

        recovery_factor = get_recovery_factor(snapshots)

        # Low recovery factor due to large drawdown
        self.assertLess(recovery_factor, 1.0)

    def test_both_metrics_handle_same_edge_cases(self):
        """Test that both functions handle edge cases consistently."""
        # Empty list
        self.assertEqual(get_recovery_factor([]), 0.0)
        self.assertEqual(get_recovery_time([]), 0.0)

        # Single snapshot
        single_snapshot = [
            MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))
        ]
        # Both should handle gracefully
        get_recovery_factor(single_snapshot)
        get_recovery_time(single_snapshot)

        # Constant values
        constant_values = [1000, 1000, 1000]
        constant_snapshots = self._create_snapshots(constant_values)
        self.assertEqual(get_recovery_factor(constant_snapshots), 0.0)
        self.assertEqual(get_recovery_time(constant_snapshots), 0.0)

