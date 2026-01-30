"""
Tests for profit factor calculation functions.

Tests cover:
- get_profit_factor
- get_gross_profit
- get_gross_loss
- get_cumulative_profit_factor_series
- get_rolling_profit_factor_series
"""

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework.services.metrics.profit_factor import (
    get_profit_factor,
    get_gross_profit,
    get_gross_loss,
    get_cumulative_profit_factor_series,
    get_rolling_profit_factor_series,
)


class MockTrade:
    """Mock Trade class for testing."""

    def __init__(self, net_gain: float, closed_at: datetime = None):
        self.net_gain = net_gain
        self.closed_at = closed_at or datetime.now(timezone.utc)


class TestGetProfitFactor(TestCase):
    """Tests for get_profit_factor function."""

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_profit_factor_basic(self):
        """Test basic profit factor calculation."""
        trades = [
            MockTrade(net_gain=100),   # Profit
            MockTrade(net_gain=-50),   # Loss
            MockTrade(net_gain=200),   # Profit
            MockTrade(net_gain=-100),  # Loss
        ]

        result = get_profit_factor(trades)

        # Gross profit = 100 + 200 = 300
        # Gross loss = 50 + 100 = 150
        # Profit factor = 300 / 150 = 2.0
        self.assertEqual(result, 2.0)

    def test_profit_factor_excellent(self):
        """Test excellent profit factor (> 3.0)."""
        trades = [
            MockTrade(net_gain=400),
            MockTrade(net_gain=-50),
            MockTrade(net_gain=300),
            MockTrade(net_gain=-50),
        ]

        result = get_profit_factor(trades)

        # Gross profit = 700, Gross loss = 100
        # Profit factor = 7.0
        self.assertEqual(result, 7.0)

    def test_profit_factor_losing_strategy(self):
        """Test losing strategy profit factor (< 1.0)."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-200),
            MockTrade(net_gain=50),
            MockTrade(net_gain=-150),
        ]

        result = get_profit_factor(trades)

        # Gross profit = 150, Gross loss = 350
        # Profit factor = 150 / 350 ≈ 0.428
        self.assertAlmostEqual(result, 0.428, delta=0.01)

    def test_profit_factor_breakeven(self):
        """Test breakeven profit factor (= 1.0)."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-100),
        ]

        result = get_profit_factor(trades)

        # Gross profit = 100, Gross loss = 100
        # Profit factor = 1.0
        self.assertEqual(result, 1.0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_profit_factor_empty_trades(self):
        """Test with empty trade list."""
        result = get_profit_factor([])

        # No profits, no losses -> 0.0
        self.assertEqual(result, 0.0)

    def test_profit_factor_no_losses(self):
        """Test with all winning trades (no losses)."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=200),
            MockTrade(net_gain=50),
        ]

        result = get_profit_factor(trades)

        # No losses -> infinity
        self.assertEqual(result, float('inf'))

    def test_profit_factor_no_profits(self):
        """Test with all losing trades (no profits)."""
        trades = [
            MockTrade(net_gain=-100),
            MockTrade(net_gain=-200),
            MockTrade(net_gain=-50),
        ]

        result = get_profit_factor(trades)

        # No profits -> 0.0
        self.assertEqual(result, 0.0)

    def test_profit_factor_single_winning_trade(self):
        """Test with single winning trade."""
        trades = [MockTrade(net_gain=100)]

        result = get_profit_factor(trades)

        self.assertEqual(result, float('inf'))

    def test_profit_factor_single_losing_trade(self):
        """Test with single losing trade."""
        trades = [MockTrade(net_gain=-100)]

        result = get_profit_factor(trades)

        self.assertEqual(result, 0.0)

    def test_profit_factor_zero_gain_trades(self):
        """Test with trades that have zero net gain."""
        trades = [
            MockTrade(net_gain=0),
            MockTrade(net_gain=100),
            MockTrade(net_gain=-50),
            MockTrade(net_gain=0),
        ]

        result = get_profit_factor(trades)

        # Zero gain trades are ignored
        # Gross profit = 100, Gross loss = 50
        # Profit factor = 2.0
        self.assertEqual(result, 2.0)

    def test_profit_factor_all_zero_gains(self):
        """Test with all zero net gain trades."""
        trades = [
            MockTrade(net_gain=0),
            MockTrade(net_gain=0),
            MockTrade(net_gain=0),
        ]

        result = get_profit_factor(trades)

        # No profits, no losses -> 0.0
        self.assertEqual(result, 0.0)

    # ==========================================================
    # Value Range Tests
    # ==========================================================

    def test_profit_factor_small_values(self):
        """Test with very small trade values."""
        trades = [
            MockTrade(net_gain=0.001),
            MockTrade(net_gain=-0.0005),
            MockTrade(net_gain=0.002),
        ]

        result = get_profit_factor(trades)

        # Gross profit = 0.003, Gross loss = 0.0005
        # Profit factor = 6.0
        self.assertEqual(result, 6.0)

    def test_profit_factor_large_values(self):
        """Test with very large trade values."""
        trades = [
            MockTrade(net_gain=1000000),
            MockTrade(net_gain=-500000),
            MockTrade(net_gain=2000000),
        ]

        result = get_profit_factor(trades)

        # Gross profit = 3000000, Gross loss = 500000
        # Profit factor = 6.0
        self.assertEqual(result, 6.0)

    def test_profit_factor_mixed_magnitudes(self):
        """Test with mixed magnitude trades."""
        trades = [
            MockTrade(net_gain=1000),
            MockTrade(net_gain=-1),
            MockTrade(net_gain=0.5),
            MockTrade(net_gain=-500),
        ]

        result = get_profit_factor(trades)

        # Gross profit = 1000.5, Gross loss = 501
        # Profit factor ≈ 1.997
        self.assertAlmostEqual(result, 1.997, delta=0.01)


class TestGetGrossProfit(TestCase):
    """Tests for get_gross_profit function."""

    def test_gross_profit_basic(self):
        """Test basic gross profit calculation."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-50),
            MockTrade(net_gain=200),
            MockTrade(net_gain=-100),
        ]

        result = get_gross_profit(trades)

        # Only positive trades: 100 + 200 = 300
        self.assertEqual(result, 300)

    def test_gross_profit_empty_trades(self):
        """Test with empty trade list."""
        result = get_gross_profit([])
        self.assertEqual(result, 0.0)

    def test_gross_profit_no_winners(self):
        """Test when all trades are losers."""
        trades = [
            MockTrade(net_gain=-100),
            MockTrade(net_gain=-200),
        ]

        result = get_gross_profit(trades)
        self.assertEqual(result, 0.0)

    def test_gross_profit_all_winners(self):
        """Test when all trades are winners."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=200),
            MockTrade(net_gain=50),
        ]

        result = get_gross_profit(trades)
        self.assertEqual(result, 350)

    def test_gross_profit_with_zero_gains(self):
        """Test that zero gains are not counted as profit."""
        trades = [
            MockTrade(net_gain=0),
            MockTrade(net_gain=100),
            MockTrade(net_gain=0),
        ]

        result = get_gross_profit(trades)
        self.assertEqual(result, 100)


class TestGetGrossLoss(TestCase):
    """Tests for get_gross_loss function."""

    def test_gross_loss_basic(self):
        """Test basic gross loss calculation."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-50),
            MockTrade(net_gain=200),
            MockTrade(net_gain=-100),
        ]

        result = get_gross_loss(trades)

        # Only negative trades (absolute values): 50 + 100 = 150
        self.assertEqual(result, 150)

    def test_gross_loss_empty_trades(self):
        """Test with empty trade list."""
        result = get_gross_loss([])
        self.assertEqual(result, 0.0)

    def test_gross_loss_no_losers(self):
        """Test when all trades are winners."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=200),
        ]

        result = get_gross_loss(trades)
        self.assertEqual(result, 0.0)

    def test_gross_loss_all_losers(self):
        """Test when all trades are losers."""
        trades = [
            MockTrade(net_gain=-100),
            MockTrade(net_gain=-200),
            MockTrade(net_gain=-50),
        ]

        result = get_gross_loss(trades)
        self.assertEqual(result, 350)

    def test_gross_loss_with_zero_gains(self):
        """Test that zero gains are not counted as loss."""
        trades = [
            MockTrade(net_gain=0),
            MockTrade(net_gain=-100),
            MockTrade(net_gain=0),
        ]

        result = get_gross_loss(trades)
        self.assertEqual(result, 100)

    def test_gross_loss_returns_absolute_value(self):
        """Test that gross loss returns positive (absolute) value."""
        trades = [
            MockTrade(net_gain=-100),
            MockTrade(net_gain=-200),
        ]

        result = get_gross_loss(trades)

        # Should be positive
        self.assertGreater(result, 0)
        self.assertEqual(result, 300)


class TestGetCumulativeProfitFactorSeries(TestCase):
    """Tests for get_cumulative_profit_factor_series function."""

    def _create_trades(self, gains, start_date=None):
        """Helper to create trades with sequential dates."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        return [
            MockTrade(
                net_gain=gain,
                closed_at=start_date + timedelta(days=i)
            )
            for i, gain in enumerate(gains)
        ]

    def test_cumulative_series_basic(self):
        """Test basic cumulative profit factor series."""
        trades = self._create_trades([100, -50, 200, -100])

        result = get_cumulative_profit_factor_series(trades)

        self.assertEqual(len(result), 4)

        # After trade 1: profit=100, loss=0 -> inf
        self.assertEqual(result[0][1], float('inf'))

        # After trade 2: profit=100, loss=50 -> 2.0
        self.assertEqual(result[1][1], 2.0)

        # After trade 3: profit=300, loss=50 -> 6.0
        self.assertEqual(result[2][1], 6.0)

        # After trade 4: profit=300, loss=150 -> 2.0
        self.assertEqual(result[3][1], 2.0)

    def test_cumulative_series_empty(self):
        """Test with empty trade list."""
        result = get_cumulative_profit_factor_series([])
        self.assertEqual(result, [])

    def test_cumulative_series_all_winners(self):
        """Test cumulative series with all winning trades."""
        trades = self._create_trades([100, 200, 150])

        result = get_cumulative_profit_factor_series(trades)

        # All should be infinity (no losses)
        for _, pf in result:
            self.assertEqual(pf, float('inf'))

    def test_cumulative_series_all_losers(self):
        """Test cumulative series with all losing trades."""
        trades = self._create_trades([-100, -200, -150])

        result = get_cumulative_profit_factor_series(trades)

        # All should be 0.0 (no profits)
        for _, pf in result:
            self.assertEqual(pf, 0.0)

    def test_cumulative_series_timestamps(self):
        """Test that timestamps are correctly preserved."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        trades = self._create_trades([100, -50, 200], start_date)

        result = get_cumulative_profit_factor_series(trades)

        self.assertEqual(result[0][0], start_date)
        self.assertEqual(result[1][0], start_date + timedelta(days=1))
        self.assertEqual(result[2][0], start_date + timedelta(days=2))

    def test_cumulative_series_monotonic_profit(self):
        """Test cumulative series with monotonically increasing profit factor."""
        # All wins after initial loss
        trades = self._create_trades([-100, 100, 100, 100, 100])

        result = get_cumulative_profit_factor_series(trades)

        # Profit factor should increase after first trade
        previous_pf = 0
        for i, (_, pf) in enumerate(result):
            if i > 0:  # Skip first (which is 0)
                self.assertGreaterEqual(pf, previous_pf)
            previous_pf = pf


class TestGetRollingProfitFactorSeries(TestCase):
    """Tests for get_rolling_profit_factor_series function."""

    def _create_trades(self, gains, start_date=None):
        """Helper to create trades with sequential dates."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        return [
            MockTrade(
                net_gain=gain,
                closed_at=start_date + timedelta(days=i)
            )
            for i, gain in enumerate(gains)
        ]

    def test_rolling_series_basic(self):
        """Test basic rolling profit factor series."""
        trades = self._create_trades([100, -50, 200, -100, 150])

        result = get_rolling_profit_factor_series(trades, window_size=3)

        self.assertEqual(len(result), 5)

        # Each result should be based on last 3 trades
        # After trade 3: window=[100, -50, 200], profit=300, loss=50 -> 6.0
        self.assertEqual(result[2][1], 6.0)

        # After trade 4: window=[-50, 200, -100], profit=200, loss=150 -> 1.33
        self.assertAlmostEqual(result[3][1], 1.333, delta=0.01)

        # After trade 5: window=[200, -100, 150], profit=350, loss=100 -> 3.5
        self.assertEqual(result[4][1], 3.5)

    def test_rolling_series_empty(self):
        """Test with empty trade list."""
        result = get_rolling_profit_factor_series([], window_size=20)
        self.assertEqual(result, [])

    def test_rolling_series_window_larger_than_trades(self):
        """Test when window size is larger than number of trades."""
        trades = self._create_trades([100, -50, 200])

        result = get_rolling_profit_factor_series(trades, window_size=10)

        # Should still work, using all available trades
        self.assertEqual(len(result), 3)

        # Final result should be same as cumulative
        # profit=300, loss=50 -> 6.0
        self.assertEqual(result[2][1], 6.0)

    def test_rolling_series_window_of_one(self):
        """Test with window size of 1."""
        trades = self._create_trades([100, -50, 200, -100])

        result = get_rolling_profit_factor_series(trades, window_size=1)

        # Each should be based on single trade
        self.assertEqual(result[0][1], float('inf'))  # 100 profit, 0 loss
        self.assertEqual(result[1][1], 0.0)           # 0 profit, 50 loss
        self.assertEqual(result[2][1], float('inf'))  # 200 profit, 0 loss
        self.assertEqual(result[3][1], 0.0)           # 0 profit, 100 loss

    def test_rolling_series_default_window(self):
        """Test with default window size (20)."""
        # Create 25 trades
        gains = [100, -50] * 12 + [100]
        trades = self._create_trades(gains)

        result = get_rolling_profit_factor_series(trades)

        # Should have 25 results
        self.assertEqual(len(result), 25)

    def test_rolling_series_all_winners_in_window(self):
        """Test when rolling window contains all winners."""
        # First 3 losers, then 5 winners
        gains = [-100, -100, -100, 100, 100, 100, 100, 100]
        trades = self._create_trades(gains)

        result = get_rolling_profit_factor_series(trades, window_size=3)

        # Last result: window=[100, 100, 100], all winners
        self.assertEqual(result[-1][1], float('inf'))

    def test_rolling_series_all_losers_in_window(self):
        """Test when rolling window contains all losers."""
        # First 3 winners, then 5 losers
        gains = [100, 100, 100, -100, -100, -100, -100, -100]
        trades = self._create_trades(gains)

        result = get_rolling_profit_factor_series(trades, window_size=3)

        # Last result: window=[-100, -100, -100], all losers
        self.assertEqual(result[-1][1], 0.0)

    def test_rolling_series_timestamps(self):
        """Test that timestamps are correctly preserved."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        trades = self._create_trades([100, -50, 200], start_date)

        result = get_rolling_profit_factor_series(trades, window_size=2)

        self.assertEqual(result[0][0], start_date)
        self.assertEqual(result[1][0], start_date + timedelta(days=1))
        self.assertEqual(result[2][0], start_date + timedelta(days=2))


class TestProfitFactorInterpretation(TestCase):
    """Tests to verify profit factor interpretation thresholds."""

    def test_losing_strategy_below_one(self):
        """Test that losing strategy has profit factor < 1.0."""
        # More losses than profits
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-200),
        ]

        result = get_profit_factor(trades)

        self.assertLess(result, 1.0)

    def test_breakeven_at_one(self):
        """Test breakeven strategy has profit factor = 1.0."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-100),
        ]

        result = get_profit_factor(trades)

        self.assertEqual(result, 1.0)

    def test_good_strategy_above_1_6(self):
        """Test good strategy has profit factor > 1.6."""
        # 2:1 profit to loss ratio
        trades = [
            MockTrade(net_gain=200),
            MockTrade(net_gain=-100),
        ]

        result = get_profit_factor(trades)

        self.assertGreater(result, 1.6)

    def test_excellent_strategy_above_3(self):
        """Test excellent strategy has profit factor > 3.0."""
        # 4:1 profit to loss ratio
        trades = [
            MockTrade(net_gain=400),
            MockTrade(net_gain=-100),
        ]

        result = get_profit_factor(trades)

        self.assertGreater(result, 3.0)


class TestGrossProfitLossConsistency(TestCase):
    """Tests to verify consistency between gross profit/loss and profit factor."""

    def test_profit_factor_equals_gross_profit_over_loss(self):
        """Verify profit factor = gross profit / gross loss."""
        trades = [
            MockTrade(net_gain=150),
            MockTrade(net_gain=-75),
            MockTrade(net_gain=225),
            MockTrade(net_gain=-100),
        ]

        profit_factor = get_profit_factor(trades)
        gross_profit = get_gross_profit(trades)
        gross_loss = get_gross_loss(trades)

        self.assertEqual(profit_factor, gross_profit / gross_loss)

    def test_gross_profit_plus_loss_covers_all_magnitude(self):
        """Verify gross profit + gross loss equals sum of absolute gains."""
        trades = [
            MockTrade(net_gain=100),
            MockTrade(net_gain=-50),
            MockTrade(net_gain=200),
            MockTrade(net_gain=-75),
            MockTrade(net_gain=0),  # Zero should be ignored
        ]

        gross_profit = get_gross_profit(trades)
        gross_loss = get_gross_loss(trades)

        # Sum of absolute non-zero gains
        expected_total = 100 + 50 + 200 + 75
        self.assertEqual(gross_profit + gross_loss, expected_total)

