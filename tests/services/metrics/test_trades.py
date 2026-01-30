"""
Tests for Trade metrics calculation functions.

Tests cover:
- get_positive_trades
- get_negative_trades
- get_number_of_trades
- get_number_of_open_trades
- get_number_of_closed_trades
- get_average_trade_duration
- get_current_average_trade_duration
- get_average_trade_size
- get_average_trade_return
- get_current_average_trade_return
- get_average_trade_gain
- get_current_average_trade_gain
- get_average_trade_loss
- get_current_average_trade_loss
- get_median_trade_return
- get_best_trade
- get_worst_trade
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from investing_algorithm_framework.services.metrics.trades import (
    get_positive_trades,
    get_negative_trades,
    get_number_of_trades,
    get_number_of_open_trades,
    get_number_of_closed_trades,
    get_average_trade_duration,
    get_current_average_trade_duration,
    get_average_trade_size,
    get_average_trade_return,
    get_current_average_trade_return,
    get_average_trade_gain,
    get_current_average_trade_gain,
    get_average_trade_loss,
    get_current_average_trade_loss,
    get_median_trade_return,
    get_best_trade,
    get_worst_trade,
)


class MockTradeStatus:
    """Mock TradeStatus for testing."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"

    @staticmethod
    def equals(status):
        return status == MockTradeStatus.CLOSED


class MockTrade:
    """Mock Trade class for testing."""

    def __init__(
        self,
        status: str = "CLOSED",
        net_gain: float = 0.0,
        net_gain_absolute: float = None,
        cost: float = 100.0,
        amount: float = 1.0,
        open_price: float = 100.0,
        opened_at: datetime = None,
        closed_at: datetime = None,
    ):
        self.status = status
        self.net_gain = net_gain
        self.net_gain_absolute = net_gain_absolute if net_gain_absolute is not None else abs(net_gain)
        self.cost = cost
        self.amount = amount
        self.open_price = open_price
        self.opened_at = opened_at or datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.closed_at = closed_at or datetime(2024, 1, 2, tzinfo=timezone.utc)


class MockBacktestRun:
    """Mock BacktestRun for testing."""

    def __init__(self, backtest_end_date: datetime = None):
        self.backtest_end_date = backtest_end_date or datetime(
            2024, 1, 10, tzinfo=timezone.utc
        )


# Patch TradeStatus.CLOSED.equals and TradeStatus.OPEN.equals
def create_trade(
    status: str = "CLOSED",
    net_gain: float = 0.0,
    net_gain_absolute: float = None,
    cost: float = 100.0,
    amount: float = 1.0,
    open_price: float = 100.0,
    opened_at: datetime = None,
    closed_at: datetime = None,
):
    """Helper to create mock trade with proper status checking."""
    trade = MagicMock()
    trade.status = status
    trade.net_gain = net_gain
    trade.net_gain_absolute = net_gain_absolute if net_gain_absolute is not None else net_gain
    trade.cost = cost
    trade.amount = amount
    trade.open_price = open_price
    trade.opened_at = opened_at or datetime(2024, 1, 1, tzinfo=timezone.utc)
    trade.closed_at = closed_at or datetime(2024, 1, 2, tzinfo=timezone.utc)
    return trade


class TestGetPositiveTrades(unittest.TestCase):
    """Tests for get_positive_trades function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        count, percentage = get_positive_trades([])
        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        count, percentage = get_positive_trades(None)
        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

    def test_all_positive_trades(self):
        """Test when all closed trades are positive."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100),
            create_trade(status="CLOSED", net_gain_absolute=50),
            create_trade(status="CLOSED", net_gain_absolute=200),
        ]

        count, percentage = get_positive_trades(trades)

        self.assertEqual(count, 3)
        self.assertEqual(percentage, 100.0)

    def test_no_positive_trades(self):
        """Test when no closed trades are positive."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=-100),
            create_trade(status="CLOSED", net_gain_absolute=-50),
        ]

        count, percentage = get_positive_trades(trades)

        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

    def test_mixed_trades(self):
        """Test with mixed positive and negative trades."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100),
            create_trade(status="CLOSED", net_gain_absolute=-50),
            create_trade(status="CLOSED", net_gain_absolute=200),
            create_trade(status="CLOSED", net_gain_absolute=-75),
        ]

        count, percentage = get_positive_trades(trades)

        self.assertEqual(count, 2)
        self.assertEqual(percentage, 50.0)

    def test_ignores_open_trades(self):
        """Test that open trades are ignored."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100),
            create_trade(status="OPEN", net_gain_absolute=200),
            create_trade(status="CLOSED", net_gain_absolute=-50),
        ]

        count, percentage = get_positive_trades(trades)

        self.assertEqual(count, 1)
        self.assertEqual(percentage, 50.0)


class TestGetNegativeTrades(unittest.TestCase):
    """Tests for get_negative_trades function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        count, percentage = get_negative_trades([])
        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        count, percentage = get_negative_trades(None)
        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

    def test_all_negative_trades(self):
        """Test when all closed trades are negative."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=-100),
            create_trade(status="CLOSED", net_gain_absolute=-50),
            create_trade(status="CLOSED", net_gain_absolute=-200),
        ]

        count, percentage = get_negative_trades(trades)

        self.assertEqual(count, 3)
        self.assertEqual(percentage, 100.0)

    def test_no_negative_trades(self):
        """Test when no closed trades are negative."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100),
            create_trade(status="CLOSED", net_gain_absolute=50),
        ]

        count, percentage = get_negative_trades(trades)

        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

    def test_mixed_trades(self):
        """Test with mixed positive and negative trades."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100),
            create_trade(status="CLOSED", net_gain_absolute=-50),
            create_trade(status="CLOSED", net_gain_absolute=200),
            create_trade(status="CLOSED", net_gain_absolute=-75),
        ]

        count, percentage = get_negative_trades(trades)

        self.assertEqual(count, 2)
        self.assertEqual(percentage, 50.0)


class TestGetNumberOfTrades(unittest.TestCase):
    """Tests for get_number_of_trades function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_number_of_trades([])
        self.assertEqual(result, 0)

    def test_none_trades(self):
        """Test with None input."""
        result = get_number_of_trades(None)
        self.assertEqual(result, 0)

    def test_multiple_trades(self):
        """Test with multiple trades."""
        trades = [
            create_trade(),
            create_trade(),
            create_trade(),
        ]

        result = get_number_of_trades(trades)
        self.assertEqual(result, 3)

    def test_single_trade(self):
        """Test with single trade."""
        trades = [create_trade()]
        result = get_number_of_trades(trades)
        self.assertEqual(result, 1)


class TestGetNumberOfOpenTrades(unittest.TestCase):
    """Tests for get_number_of_open_trades function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_number_of_open_trades([])
        self.assertEqual(result, 0)

    def test_none_trades(self):
        """Test with None input."""
        result = get_number_of_open_trades(None)
        self.assertEqual(result, 0)

    def test_all_open_trades(self):
        """Test with all open trades."""
        trades = [
            create_trade(status="OPEN"),
            create_trade(status="OPEN"),
            create_trade(status="OPEN"),
        ]

        result = get_number_of_open_trades(trades)
        self.assertEqual(result, 3)

    def test_no_open_trades(self):
        """Test with no open trades."""
        trades = [
            create_trade(status="CLOSED"),
            create_trade(status="CLOSED"),
        ]

        result = get_number_of_open_trades(trades)
        self.assertEqual(result, 0)

    def test_mixed_trades(self):
        """Test with mixed open and closed trades."""
        trades = [
            create_trade(status="OPEN"),
            create_trade(status="CLOSED"),
            create_trade(status="OPEN"),
        ]

        result = get_number_of_open_trades(trades)
        self.assertEqual(result, 2)


class TestGetNumberOfClosedTrades(unittest.TestCase):
    """Tests for get_number_of_closed_trades function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_number_of_closed_trades([])
        self.assertEqual(result, 0)

    def test_none_trades(self):
        """Test with None input."""
        result = get_number_of_closed_trades(None)
        self.assertEqual(result, 0)

    def test_all_closed_trades(self):
        """Test with all closed trades."""
        trades = [
            create_trade(status="CLOSED"),
            create_trade(status="CLOSED"),
            create_trade(status="CLOSED"),
        ]

        result = get_number_of_closed_trades(trades)
        self.assertEqual(result, 3)

    def test_no_closed_trades(self):
        """Test with no closed trades."""
        trades = [
            create_trade(status="OPEN"),
            create_trade(status="OPEN"),
        ]

        result = get_number_of_closed_trades(trades)
        self.assertEqual(result, 0)

    def test_mixed_trades(self):
        """Test with mixed open and closed trades."""
        trades = [
            create_trade(status="OPEN"),
            create_trade(status="CLOSED"),
            create_trade(status="CLOSED"),
        ]

        result = get_number_of_closed_trades(trades)
        self.assertEqual(result, 2)


class TestGetAverageTradeDuration(unittest.TestCase):
    """Tests for get_average_trade_duration function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_average_trade_duration([])
        self.assertEqual(result, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        result = get_average_trade_duration(None)
        self.assertEqual(result, 0.0)

    def test_single_trade_one_hour(self):
        """Test single trade lasting one hour."""
        opened = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        closed = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

        trades = [create_trade(status="CLOSED", opened_at=opened, closed_at=closed)]

        result = get_average_trade_duration(trades)
        self.assertEqual(result, 1.0)

    def test_multiple_trades_average_duration(self):
        """Test average duration of multiple trades."""
        # Trade 1: 2 hours
        opened1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        closed1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Trade 2: 4 hours
        opened2 = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
        closed2 = datetime(2024, 1, 2, 14, 0, 0, tzinfo=timezone.utc)

        trades = [
            create_trade(status="CLOSED", opened_at=opened1, closed_at=closed1),
            create_trade(status="CLOSED", opened_at=opened2, closed_at=closed2),
        ]

        result = get_average_trade_duration(trades)
        # Average: (2 + 4) / 2 = 3 hours
        self.assertEqual(result, 3.0)

    def test_ignores_open_trades(self):
        """Test that open trades are ignored."""
        opened = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        closed = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        trades = [
            create_trade(status="CLOSED", opened_at=opened, closed_at=closed),
            create_trade(status="OPEN", opened_at=opened),
        ]

        result = get_average_trade_duration(trades)
        self.assertEqual(result, 2.0)


class TestGetCurrentAverageTradeDuration(unittest.TestCase):
    """Tests for get_current_average_trade_duration function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        backtest_run = MockBacktestRun()
        result = get_current_average_trade_duration([], backtest_run)
        self.assertEqual(result, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        backtest_run = MockBacktestRun()
        result = get_current_average_trade_duration(None, backtest_run)
        self.assertEqual(result, 0.0)

    def test_includes_open_trades(self):
        """Test that open trades use backtest_end_date."""
        opened = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        backtest_end = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)

        trades = [create_trade(status="OPEN", opened_at=opened)]
        backtest_run = MockBacktestRun(backtest_end_date=backtest_end)

        result = get_current_average_trade_duration(trades, backtest_run)
        # Duration: 4 hours
        self.assertEqual(result, 4.0)


class TestGetAverageTradeSize(unittest.TestCase):
    """Tests for get_average_trade_size function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_average_trade_size([])
        self.assertEqual(result, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        result = get_average_trade_size(None)
        self.assertEqual(result, 0.0)

    def test_single_trade(self):
        """Test single trade size calculation."""
        trades = [create_trade(amount=10, open_price=50)]

        result = get_average_trade_size(trades)
        # Size: 10 * 50 = 500
        self.assertEqual(result, 500.0)

    def test_multiple_trades(self):
        """Test average of multiple trade sizes."""
        trades = [
            create_trade(amount=10, open_price=50),   # 500
            create_trade(amount=5, open_price=100),   # 500
            create_trade(amount=20, open_price=25),   # 500
        ]

        result = get_average_trade_size(trades)
        # Average: (500 + 500 + 500) / 3 = 500
        self.assertEqual(result, 500.0)

    def test_varied_trade_sizes(self):
        """Test average with varied trade sizes."""
        trades = [
            create_trade(amount=10, open_price=100),  # 1000
            create_trade(amount=5, open_price=200),   # 1000
            create_trade(amount=2, open_price=500),   # 1000
        ]

        result = get_average_trade_size(trades)
        self.assertEqual(result, 1000.0)


class TestGetAverageTradeReturn(unittest.TestCase):
    """Tests for get_average_trade_return function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        absolute, percentage = get_average_trade_return([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        absolute, percentage = get_average_trade_return(None)
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_all_positive_returns(self):
        """Test with all positive returns."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100, cost=1000),
            create_trade(status="CLOSED", net_gain_absolute=200, cost=1000),
        ]

        absolute, percentage = get_average_trade_return(trades)

        # Average absolute: (100 + 200) / 2 = 150
        self.assertEqual(absolute, 150.0)
        # Average percentage: ((100/1000) + (200/1000)) / 2 = 0.15
        self.assertAlmostEqual(percentage, 0.15, places=10)

    def test_mixed_returns(self):
        """Test with mixed positive and negative returns."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100, cost=1000),
            create_trade(status="CLOSED", net_gain_absolute=-50, cost=1000),
        ]

        absolute, percentage = get_average_trade_return(trades)

        # Average absolute: (100 + (-50)) / 2 = 25
        self.assertEqual(absolute, 25.0)

    def test_ignores_open_trades(self):
        """Test that open trades are ignored."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100, cost=1000),
            create_trade(status="OPEN", net_gain_absolute=500, cost=1000),
        ]

        absolute, percentage = get_average_trade_return(trades)

        # Only closed trade counted
        self.assertEqual(absolute, 100.0)


class TestGetCurrentAverageTradeReturn(unittest.TestCase):
    """Tests for get_current_average_trade_return function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        absolute, percentage = get_current_average_trade_return([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_includes_all_trades(self):
        """Test that all trades (open and closed) are included."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100, cost=1000),
            create_trade(status="OPEN", net_gain_absolute=200, cost=1000),
        ]

        absolute, percentage = get_current_average_trade_return(trades)

        # Average: (100 + 200) / 2 = 150
        self.assertEqual(absolute, 150.0)


class TestGetAverageTradeGain(unittest.TestCase):
    """Tests for get_average_trade_gain function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        absolute, percentage = get_average_trade_gain([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        absolute, percentage = get_average_trade_gain(None)
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_only_gains(self):
        """Test with only positive gains."""
        trades = [
            create_trade(net_gain_absolute=100, cost=1000),
            create_trade(net_gain_absolute=200, cost=1000),
        ]

        absolute, percentage = get_average_trade_gain(trades)

        self.assertEqual(absolute, 150.0)
        self.assertAlmostEqual(percentage, 0.15, places=10)

    def test_filters_losses(self):
        """Test that losses are filtered out."""
        trades = [
            create_trade(net_gain_absolute=100, cost=1000),
            create_trade(net_gain_absolute=-50, cost=1000),
            create_trade(net_gain_absolute=200, cost=1000),
        ]

        absolute, percentage = get_average_trade_gain(trades)

        # Only positive: (100 + 200) / 2 = 150
        self.assertEqual(absolute, 150.0)

    def test_no_gains(self):
        """Test when there are no positive trades."""
        trades = [
            create_trade(net_gain_absolute=-100, cost=1000),
            create_trade(net_gain_absolute=-50, cost=1000),
        ]

        absolute, percentage = get_average_trade_gain(trades)

        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)


class TestGetCurrentAverageTradeGain(unittest.TestCase):
    """Tests for get_current_average_trade_gain function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        absolute, percentage = get_current_average_trade_gain([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_includes_open_trades(self):
        """Test that open trades are included."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100, cost=1000),
            create_trade(status="OPEN", net_gain_absolute=200, cost=1000),
        ]

        absolute, percentage = get_current_average_trade_gain(trades)

        # Both positive: (100 + 200) / 2 = 150
        self.assertEqual(absolute, 150.0)


class TestGetAverageTradeLoss(unittest.TestCase):
    """Tests for get_average_trade_loss function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        absolute, percentage = get_average_trade_loss([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_none_trades(self):
        """Test with None input."""
        absolute, percentage = get_average_trade_loss(None)
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_only_losses(self):
        """Test with only negative trades."""
        trades = [
            create_trade(status="CLOSED", net_gain=-100, net_gain_absolute=-100, cost=1000),
            create_trade(status="CLOSED", net_gain=-200, net_gain_absolute=-200, cost=1000),
        ]

        absolute, percentage = get_average_trade_loss(trades)

        # Average: (-100 + -200) / 2 = -150
        self.assertEqual(absolute, -150.0)

    def test_filters_gains(self):
        """Test that gains are filtered out."""
        trades = [
            create_trade(status="CLOSED", net_gain=-100, net_gain_absolute=-100, cost=1000),
            create_trade(status="CLOSED", net_gain=50, net_gain_absolute=50, cost=1000),
            create_trade(status="CLOSED", net_gain=-200, net_gain_absolute=-200, cost=1000),
        ]

        absolute, percentage = get_average_trade_loss(trades)

        # Only negative: (-100 + -200) / 2 = -150
        self.assertEqual(absolute, -150.0)

    def test_no_losses(self):
        """Test when there are no negative trades."""
        trades = [
            create_trade(status="CLOSED", net_gain=100, net_gain_absolute=100, cost=1000),
            create_trade(status="CLOSED", net_gain=50, net_gain_absolute=50, cost=1000),
        ]

        absolute, percentage = get_average_trade_loss(trades)

        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)


class TestGetCurrentAverageTradeLoss(unittest.TestCase):
    """Tests for get_current_average_trade_loss function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        absolute, percentage = get_current_average_trade_loss([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_includes_all_losses(self):
        """Test that all losing trades are included."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=-100, cost=1000),
            create_trade(status="OPEN", net_gain_absolute=-200, cost=1000),
        ]

        absolute, percentage = get_current_average_trade_loss(trades)

        # Average: (-100 + -200) / 2 = -150
        self.assertEqual(absolute, -150.0)


class TestGetMedianTradeReturn(unittest.TestCase):
    """Tests for get_median_trade_return function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        median, percentage = get_median_trade_return([])
        self.assertEqual(median, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_odd_number_of_trades(self):
        """Test median with odd number of trades."""
        trades = [
            create_trade(net_gain_absolute=100, cost=1000),
            create_trade(net_gain_absolute=200, cost=1000),
            create_trade(net_gain_absolute=300, cost=1000),
        ]

        median, percentage = get_median_trade_return(trades)

        # Median of [100, 200, 300] = 200
        self.assertEqual(median, 200.0)

    def test_even_number_of_trades(self):
        """Test median with even number of trades."""
        trades = [
            create_trade(net_gain_absolute=100, cost=1000),
            create_trade(net_gain_absolute=200, cost=1000),
            create_trade(net_gain_absolute=300, cost=1000),
            create_trade(net_gain_absolute=400, cost=1000),
        ]

        median, percentage = get_median_trade_return(trades)

        # Median of [100, 200, 300, 400] = (200 + 300) / 2 = 250
        self.assertEqual(median, 250.0)

    def test_single_trade(self):
        """Test median with single trade."""
        trades = [create_trade(net_gain_absolute=150, cost=1000)]

        median, percentage = get_median_trade_return(trades)

        self.assertEqual(median, 150.0)

    def test_unsorted_trades(self):
        """Test that trades are sorted before median calculation."""
        trades = [
            create_trade(net_gain_absolute=300, cost=1000),
            create_trade(net_gain_absolute=100, cost=1000),
            create_trade(net_gain_absolute=200, cost=1000),
        ]

        median, percentage = get_median_trade_return(trades)

        # Should sort to [100, 200, 300], median = 200
        self.assertEqual(median, 200.0)


class TestGetBestTrade(unittest.TestCase):
    """Tests for get_best_trade function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_best_trade([])
        self.assertIsNone(result)

    def test_single_trade(self):
        """Test with single trade."""
        trade = create_trade(net_gain_absolute=100)
        trades = [trade]

        result = get_best_trade(trades)

        self.assertEqual(result, trade)

    def test_multiple_trades(self):
        """Test finding best trade from multiple."""
        trade1 = create_trade(net_gain_absolute=100)
        trade2 = create_trade(net_gain_absolute=500)  # Best
        trade3 = create_trade(net_gain_absolute=200)

        trades = [trade1, trade2, trade3]

        result = get_best_trade(trades)

        self.assertEqual(result, trade2)

    def test_with_negative_trades(self):
        """Test finding best trade when all are negative."""
        trade1 = create_trade(net_gain_absolute=-100)
        trade2 = create_trade(net_gain_absolute=-50)  # Best (least negative)
        trade3 = create_trade(net_gain_absolute=-200)

        trades = [trade1, trade2, trade3]

        result = get_best_trade(trades)

        self.assertEqual(result, trade2)


class TestGetWorstTrade(unittest.TestCase):
    """Tests for get_worst_trade function."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        result = get_worst_trade([])
        self.assertIsNone(result)

    def test_single_trade(self):
        """Test with single trade."""
        trade = create_trade(net_gain=-100)
        trades = [trade]

        result = get_worst_trade(trades)

        self.assertEqual(result, trade)

    def test_multiple_trades(self):
        """Test finding worst trade from multiple."""
        trade1 = create_trade(net_gain=-100)
        trade2 = create_trade(net_gain=-500)  # Worst
        trade3 = create_trade(net_gain=-200)

        trades = [trade1, trade2, trade3]

        result = get_worst_trade(trades)

        self.assertEqual(result, trade2)

    def test_with_positive_trades(self):
        """Test finding worst trade when all are positive."""
        trade1 = create_trade(net_gain=100)
        trade2 = create_trade(net_gain=50)   # Worst (smallest gain)
        trade3 = create_trade(net_gain=200)

        trades = [trade1, trade2, trade3]

        result = get_worst_trade(trades)

        self.assertEqual(result, trade2)


class TestTradesIntegration(unittest.TestCase):
    """Integration tests for trade metrics."""

    def test_positive_plus_negative_equals_total(self):
        """Test that positive + negative trades equals total closed trades."""
        trades = [
            create_trade(status="CLOSED", net_gain_absolute=100),
            create_trade(status="CLOSED", net_gain_absolute=-50),
            create_trade(status="CLOSED", net_gain_absolute=200),
            create_trade(status="CLOSED", net_gain_absolute=-75),
            create_trade(status="CLOSED", net_gain_absolute=0),  # Zero trade
        ]

        positive_count, _ = get_positive_trades(trades)
        negative_count, _ = get_negative_trades(trades)
        closed_count = get_number_of_closed_trades(trades)

        # Note: Zero gain trades are neither positive nor negative
        self.assertLessEqual(positive_count + negative_count, closed_count)

    def test_open_plus_closed_equals_total(self):
        """Test that open + closed trades equals total trades."""
        trades = [
            create_trade(status="CLOSED"),
            create_trade(status="OPEN"),
            create_trade(status="CLOSED"),
            create_trade(status="OPEN"),
        ]

        open_count = get_number_of_open_trades(trades)
        closed_count = get_number_of_closed_trades(trades)
        total_count = get_number_of_trades(trades)

        self.assertEqual(open_count + closed_count, total_count)


if __name__ == "__main__":
    unittest.main()

