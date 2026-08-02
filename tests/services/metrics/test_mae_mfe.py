import unittest

from investing_algorithm_framework.services.metrics.mae_mfe import (
    get_trade_mae_mfe_statistics,
)


class MockTrade:
    def __init__(
        self, open_price, high_water_mark, low_water_mark, is_short=False
    ):
        self.open_price = open_price
        self.high_water_mark = high_water_mark
        self.low_water_mark = low_water_mark
        self.is_short = is_short


class TestTradeMaeMfeStatistics(unittest.TestCase):

    def test_no_trades_returns_zeros(self):
        stats = get_trade_mae_mfe_statistics([])
        self.assertEqual(stats["average_mae"], 0.0)
        self.assertEqual(stats["average_mfe"], 0.0)
        self.assertEqual(stats["max_mae"], 0.0)
        self.assertEqual(stats["max_mfe"], 0.0)
        self.assertEqual(stats["mfe_mae_ratio"], 0.0)

    def test_trades_without_water_marks_are_skipped(self):
        trades = [MockTrade(100, None, None)]
        stats = get_trade_mae_mfe_statistics(trades)
        self.assertEqual(stats["average_mae"], 0.0)
        self.assertEqual(stats["average_mfe"], 0.0)

    def test_long_trade_mae_mfe(self):
        # Long trade opened at 100, dipped to 90 (MAE=10), rallied to
        # 120 (MFE=20) before closing.
        trades = [MockTrade(100, 120, 90, is_short=False)]
        stats = get_trade_mae_mfe_statistics(trades)
        self.assertAlmostEqual(stats["average_mae"], 10.0)
        self.assertAlmostEqual(stats["average_mae_percentage"], 10.0)
        self.assertAlmostEqual(stats["average_mfe"], 20.0)
        self.assertAlmostEqual(stats["average_mfe_percentage"], 20.0)
        self.assertAlmostEqual(stats["max_mae"], 10.0)
        self.assertAlmostEqual(stats["max_mfe"], 20.0)
        self.assertAlmostEqual(stats["mfe_mae_ratio"], 2.0)

    def test_short_trade_mae_mfe(self):
        # Short trade opened at 100, rallied to 110 (MAE=10, adverse
        # for a short), dropped to 80 (MFE=20, favorable for a short).
        trades = [MockTrade(100, 110, 80, is_short=True)]
        stats = get_trade_mae_mfe_statistics(trades)
        self.assertAlmostEqual(stats["average_mae"], 10.0)
        self.assertAlmostEqual(stats["average_mfe"], 20.0)

    def test_aggregate_across_multiple_trades(self):
        trades = [
            MockTrade(100, 120, 90, is_short=False),  # MAE 10, MFE 20
            MockTrade(200, 220, 150, is_short=False),  # MAE 50, MFE 20
        ]
        stats = get_trade_mae_mfe_statistics(trades)
        self.assertAlmostEqual(stats["average_mae"], 30.0)
        self.assertAlmostEqual(stats["average_mfe"], 20.0)
        self.assertAlmostEqual(stats["max_mae"], 50.0)
        self.assertAlmostEqual(stats["max_mfe"], 20.0)
