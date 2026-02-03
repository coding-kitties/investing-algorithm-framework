"""
Tests for Win Rate and Win/Loss Ratio calculation functions.

Tests cover:
- get_win_rate
- get_current_win_rate
- get_win_loss_ratio
- get_current_win_loss_ratio
"""

import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace

from investing_algorithm_framework.services.metrics.win_rate import (
    get_win_rate,
    get_current_win_rate,
    get_win_loss_ratio,
    get_current_win_loss_ratio,
)


def create_trade(net_gain, status='CLOSED', net_gain_absolute=None):
    """Helper to create mock trade objects."""
    trade = MagicMock()
    trade.net_gain = net_gain
    trade.status = status
    trade.net_gain_absolute = net_gain_absolute if net_gain_absolute is not None else net_gain
    return trade


class TestGetWinRate(unittest.TestCase):
    """Tests for get_win_rate function."""

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_all_winning_trades(self):
        """Test win rate when all trades are profitable."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=200),
            create_trade(net_gain=50),
        ]

        result = get_win_rate(trades)

        self.assertEqual(result, 1.0)  # 100%

    def test_all_losing_trades(self):
        """Test win rate when all trades are losing."""
        trades = [
            create_trade(net_gain=-100),
            create_trade(net_gain=-200),
            create_trade(net_gain=-50),
        ]

        result = get_win_rate(trades)

        self.assertEqual(result, 0.0)  # 0%

    def test_mixed_trades_50_percent(self):
        """Test win rate with 50% winning trades."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=-50),
            create_trade(net_gain=200),
            create_trade(net_gain=-75),
        ]

        result = get_win_rate(trades)

        self.assertEqual(result, 0.5)  # 50%

    def test_mixed_trades_75_percent(self):
        """Test win rate with 75% winning trades."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=200),
            create_trade(net_gain=150),
            create_trade(net_gain=-50),
        ]

        result = get_win_rate(trades)

        self.assertEqual(result, 0.75)  # 75%

    def test_mixed_trades_25_percent(self):
        """Test win rate with 25% winning trades."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=-200),
            create_trade(net_gain=-150),
            create_trade(net_gain=-50),
        ]

        result = get_win_rate(trades)

        self.assertEqual(result, 0.25)  # 25%

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_win_rate([])
        self.assertEqual(result, 0.0)

    def test_single_winning_trade(self):
        """Test with single winning trade."""
        trades = [create_trade(net_gain=100)]
        result = get_win_rate(trades)
        self.assertEqual(result, 1.0)

    def test_single_losing_trade(self):
        """Test with single losing trade."""
        trades = [create_trade(net_gain=-100)]
        result = get_win_rate(trades)
        self.assertEqual(result, 0.0)

    def test_zero_gain_trade_not_counted_as_win(self):
        """Test that zero gain trades are not counted as wins."""
        trades = [
            create_trade(net_gain=0),
            create_trade(net_gain=100),
            create_trade(net_gain=-50),
        ]

        result = get_win_rate(trades)

        # 1 win out of 3 closed trades
        self.assertAlmostEqual(result, 1/3, places=5)

    def test_ignores_open_trades(self):
        """Test that open trades are ignored."""
        trades = [
            create_trade(net_gain=100, status='CLOSED'),
            create_trade(net_gain=200, status='OPEN'),
            create_trade(net_gain=-50, status='CLOSED'),
        ]

        result = get_win_rate(trades)

        # 1 win out of 2 closed trades
        self.assertEqual(result, 0.5)


class TestGetCurrentWinRate(unittest.TestCase):
    """Tests for get_current_win_rate function."""

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_all_winning_trades(self):
        """Test current win rate when all trades are profitable."""
        trades = [
            create_trade(net_gain=100, net_gain_absolute=100),
            create_trade(net_gain=200, net_gain_absolute=200),
        ]

        result = get_current_win_rate(trades)

        self.assertEqual(result, 1.0)

    def test_all_losing_trades(self):
        """Test current win rate when all trades are losing."""
        trades = [
            create_trade(net_gain=-100, net_gain_absolute=-100),
            create_trade(net_gain=-200, net_gain_absolute=-200),
        ]

        result = get_current_win_rate(trades)

        self.assertEqual(result, 0.0)

    def test_mixed_trades(self):
        """Test current win rate with mixed trades."""
        trades = [
            create_trade(net_gain=100, net_gain_absolute=100),
            create_trade(net_gain=-50, net_gain_absolute=-50),
        ]

        result = get_current_win_rate(trades)

        self.assertEqual(result, 0.5)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_current_win_rate([])
        self.assertEqual(result, 0.0)

    def test_includes_open_trades(self):
        """Test that open trades are included."""
        trades = [
            create_trade(net_gain=100, status='CLOSED', net_gain_absolute=100),
            create_trade(net_gain=200, status='OPEN', net_gain_absolute=200),
            create_trade(net_gain=-50, status='CLOSED', net_gain_absolute=-50),
        ]

        result = get_current_win_rate(trades)

        # 2 wins out of 3 trades (includes open)
        self.assertAlmostEqual(result, 2/3, places=5)

    def test_uses_net_gain_absolute(self):
        """Test that net_gain_absolute is used for calculation."""
        trades = [
            create_trade(net_gain=-100, net_gain_absolute=50),  # Actually positive
            create_trade(net_gain=100, net_gain_absolute=-50),  # Actually negative
        ]

        result = get_current_win_rate(trades)

        # Based on net_gain_absolute: 1 win, 1 loss
        self.assertEqual(result, 0.5)


class TestGetWinLossRatio(unittest.TestCase):
    """Tests for get_win_loss_ratio function."""

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_mixed_winning_and_losing_trades(self):
        """Test win/loss ratio with mixed trades."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=200),
            create_trade(net_gain=-50),
            create_trade(net_gain=-150),
        ]

        result = get_win_loss_ratio(trades)

        # avg_win = (100 + 200) / 2 = 150
        # avg_loss = abs((-50 + -150) / 2) = 100
        # ratio = 150 / 100 = 1.5
        self.assertAlmostEqual(result, 1.5, places=5)

    def test_ratio_greater_than_one(self):
        """Test win/loss ratio > 1 (wins larger than losses)."""
        trades = [
            create_trade(net_gain=300),
            create_trade(net_gain=-100),
        ]

        result = get_win_loss_ratio(trades)

        # avg_win = 300, avg_loss = 100
        # ratio = 3.0
        self.assertEqual(result, 3.0)

    def test_ratio_less_than_one(self):
        """Test win/loss ratio < 1 (losses larger than wins)."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=-300),
        ]

        result = get_win_loss_ratio(trades)

        # avg_win = 100, avg_loss = 300
        # ratio = 0.333
        self.assertAlmostEqual(result, 1/3, places=5)

    def test_ratio_equals_one(self):
        """Test win/loss ratio = 1 (wins equal losses)."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=-100),
        ]

        result = get_win_loss_ratio(trades)

        self.assertEqual(result, 1.0)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_win_loss_ratio([])
        self.assertEqual(result, 0.0)

    def test_all_winning_trades_returns_inf(self):
        """Test that all winning trades returns inf (no losers to compare)."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=300),
        ]

        result = get_win_loss_ratio(trades)

        self.assertEqual(result, float('inf'))

    def test_all_losing_trades_returns_zero(self):
        """Test that all losing trades returns 0.0 (no winners to compare)."""
        trades = [
            create_trade(net_gain=-100),
            create_trade(net_gain=-200),
        ]

        result = get_win_loss_ratio(trades)

        self.assertEqual(result, 0.0)

    def test_zero_gain_trade_excluded(self):
        """Test that zero gain trades are excluded from calculation."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=200),
            create_trade(net_gain=0),  # Neither win nor loss
            create_trade(net_gain=-50),
        ]

        result = get_win_loss_ratio(trades)

        # avg_win = (100 + 200) / 2 = 150
        # avg_loss = 50
        # ratio = 3.0
        self.assertEqual(result, 3.0)

    def test_ignores_open_trades(self):
        """Test that open trades are ignored."""
        trades = [
            create_trade(net_gain=100, status='CLOSED'),
            create_trade(net_gain=500, status='OPEN'),  # Should be ignored
            create_trade(net_gain=-50, status='CLOSED'),
        ]

        result = get_win_loss_ratio(trades)

        # avg_win = 100, avg_loss = 50
        # ratio = 2.0
        self.assertEqual(result, 2.0)

    # ==========================================================
    # Interpretation Tests
    # ==========================================================

    def test_high_ratio_big_wins(self):
        """Test high ratio indicating big wins relative to losses."""
        trades = [
            create_trade(net_gain=1000),
            create_trade(net_gain=-100),
        ]

        result = get_win_loss_ratio(trades)

        # Big win strategy
        self.assertEqual(result, 10.0)

    def test_low_ratio_big_losses(self):
        """Test low ratio indicating big losses relative to wins."""
        trades = [
            create_trade(net_gain=100),
            create_trade(net_gain=-1000),
        ]

        result = get_win_loss_ratio(trades)

        # Big loss strategy
        self.assertEqual(result, 0.1)


class TestGetCurrentWinLossRatio(unittest.TestCase):
    """Tests for get_current_win_loss_ratio function."""

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_mixed_trades(self):
        """Test current win/loss ratio with mixed trades."""
        trades = [
            create_trade(net_gain=100, net_gain_absolute=100),
            create_trade(net_gain=200, net_gain_absolute=200),
            create_trade(net_gain=-50, net_gain_absolute=-50),
            create_trade(net_gain=-150, net_gain_absolute=-150),
        ]

        result = get_current_win_loss_ratio(trades)

        # avg_win = 150, avg_loss = 100
        self.assertAlmostEqual(result, 1.5, places=5)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_current_win_loss_ratio([])
        self.assertEqual(result, 0.0)

    def test_all_winning_trades_returns_inf(self):
        """Test that all winning trades returns inf."""
        trades = [
            create_trade(net_gain=100, net_gain_absolute=100),
            create_trade(net_gain=200, net_gain_absolute=200),
        ]

        result = get_current_win_loss_ratio(trades)

        self.assertEqual(result, float('inf'))

    def test_all_losing_trades_returns_zero(self):
        """Test that all losing trades returns 0.0."""
        trades = [
            create_trade(net_gain=-100, net_gain_absolute=-100),
            create_trade(net_gain=-200, net_gain_absolute=-200),
        ]

        result = get_current_win_loss_ratio(trades)

        self.assertEqual(result, 0.0)

    def test_includes_open_trades(self):
        """Test that open trades are included."""
        trades = [
            create_trade(net_gain=100, status='CLOSED', net_gain_absolute=100),
            create_trade(net_gain=200, status='OPEN', net_gain_absolute=200),
            create_trade(net_gain=-50, status='CLOSED', net_gain_absolute=-50),
            create_trade(net_gain=-150, status='OPEN', net_gain_absolute=-150),
        ]

        result = get_current_win_loss_ratio(trades)

        # All 4 trades included
        # avg_win = 150, avg_loss = 100
        self.assertAlmostEqual(result, 1.5, places=5)

    def test_uses_net_gain_absolute(self):
        """Test that net_gain_absolute is used for calculation."""
        trades = [
            create_trade(net_gain=-100, net_gain_absolute=200),  # Win based on absolute
            create_trade(net_gain=100, net_gain_absolute=-100),  # Loss based on absolute
        ]

        result = get_current_win_loss_ratio(trades)

        # avg_win = 200, avg_loss = 100
        self.assertEqual(result, 2.0)


class TestWinRateIntegration(unittest.TestCase):
    """Integration tests for win rate and win/loss ratio."""

    def test_win_rate_and_ratio_consistency(self):
        """Test that win rate and ratio can both be calculated from same trades."""
        trades = [
            create_trade(net_gain=100, net_gain_absolute=100),
            create_trade(net_gain=200, net_gain_absolute=200),
            create_trade(net_gain=-50, net_gain_absolute=-50),
            create_trade(net_gain=-100, net_gain_absolute=-100),
        ]

        win_rate = get_win_rate(trades)
        win_loss_ratio = get_win_loss_ratio(trades)

        # 2 wins, 2 losses -> 50% win rate
        self.assertEqual(win_rate, 0.5)
        # avg_win = 150, avg_loss = 75 -> ratio = 2.0
        self.assertEqual(win_loss_ratio, 2.0)

    def test_high_win_rate_low_ratio_can_be_unprofitable(self):
        """
        Test scenario: High win rate but low ratio can still be unprofitable.
        90% win rate, but wins are small and losses are big.
        """
        trades = [
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=10),   # Win
            create_trade(net_gain=-100), # Loss
        ]

        win_rate = get_win_rate(trades)
        win_loss_ratio = get_win_loss_ratio(trades)

        # 90% win rate
        self.assertEqual(win_rate, 0.9)
        # avg_win = 10, avg_loss = 100 -> ratio = 0.1
        self.assertEqual(win_loss_ratio, 0.1)

    def test_low_win_rate_high_ratio_can_be_profitable(self):
        """
        Test scenario: Low win rate but high ratio can still be profitable.
        30% win rate, but wins are big and losses are small.
        """
        trades = [
            create_trade(net_gain=300),  # Win
            create_trade(net_gain=300),  # Win
            create_trade(net_gain=300),  # Win
            create_trade(net_gain=-50),  # Loss
            create_trade(net_gain=-50),  # Loss
            create_trade(net_gain=-50),  # Loss
            create_trade(net_gain=-50),  # Loss
            create_trade(net_gain=-50),  # Loss
            create_trade(net_gain=-50),  # Loss
            create_trade(net_gain=-50),  # Loss
        ]

        win_rate = get_win_rate(trades)
        win_loss_ratio = get_win_loss_ratio(trades)

        # 30% win rate
        self.assertEqual(win_rate, 0.3)
        # avg_win = 300, avg_loss = 50 -> ratio = 6.0
        self.assertEqual(win_loss_ratio, 6.0)

    def test_current_vs_closed_metrics(self):
        """Test difference between current (all) and closed-only metrics."""
        trades = [
            create_trade(net_gain=100, status='CLOSED', net_gain_absolute=100),
            create_trade(net_gain=200, status='OPEN', net_gain_absolute=200),
            create_trade(net_gain=-50, status='CLOSED', net_gain_absolute=-50),
        ]

        # Closed only
        win_rate = get_win_rate(trades)
        win_loss_ratio = get_win_loss_ratio(trades)

        # Current (all trades)
        current_win_rate = get_current_win_rate(trades)
        current_win_loss_ratio = get_current_win_loss_ratio(trades)

        # Closed: 1 win, 1 loss = 50%
        self.assertEqual(win_rate, 0.5)
        # Current: 2 wins, 1 loss = 66.7%
        self.assertAlmostEqual(current_win_rate, 2/3, places=5)


if __name__ == "__main__":
    unittest.main()
