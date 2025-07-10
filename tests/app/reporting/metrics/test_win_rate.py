import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace

# Assuming your function is defined in a module called strategy_metrics
from investing_algorithm_framework import get_win_loss_ratio


class TestGetWinLossRatio(unittest.TestCase):

    def create_mock_trade(self, net_gain):
        return SimpleNamespace(net_gain=net_gain)

    def test_mixed_winning_and_losing_trades(self):
        report = MagicMock()
        report.get_trades.return_value = [
            self.create_mock_trade(100),
            self.create_mock_trade(200),
            self.create_mock_trade(-50),
            self.create_mock_trade(-150),
        ]
        ratio = get_win_loss_ratio(report)
        expected_avg_win = (100 + 200) / 2  # 150
        expected_avg_loss = abs((-50 + -150) / 2)  # 100
        expected_ratio = expected_avg_win / expected_avg_loss  # 1.5
        self.assertAlmostEqual(ratio, expected_ratio)

    def test_all_winning_trades(self):
        report = MagicMock()
        report.get_trades.return_value = [
            self.create_mock_trade(100),
            self.create_mock_trade(300),
        ]
        self.assertEqual(get_win_loss_ratio(report), 0.0)

    def test_all_losing_trades(self):
        report = MagicMock()
        report.get_trades.return_value = [
            self.create_mock_trade(-100),
            self.create_mock_trade(-200),
        ]
        self.assertEqual(get_win_loss_ratio(report), 0.0)

    def test_empty_trade_list(self):
        report = MagicMock()
        report.get_trades.return_value = []
        self.assertEqual(get_win_loss_ratio(report), 0.0)

    def test_division_by_zero_loss(self):
        # Should not happen with realistic data, but test edge case
        report = MagicMock()
        report.get_trades.return_value = [
            self.create_mock_trade(100),
            self.create_mock_trade(200),
            self.create_mock_trade(0),  # zero gain/loss
        ]
        self.assertEqual(get_win_loss_ratio(report), 0.0)
