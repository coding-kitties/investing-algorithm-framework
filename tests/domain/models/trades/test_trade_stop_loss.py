from unittest import TestCase
from investing_algorithm_framework.domain import TradeStopLoss

class TestTradeStopLoss(TestCase):

    def test_model_creation(self):
        stop_loss = TradeStopLoss(
            trade_id=1,
            trade_risk_type="fixed",
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )
        self.assertEqual(stop_loss.trade_id, 1)
        self.assertEqual(stop_loss.trade_risk_type, "fixed")
        self.assertEqual(stop_loss.percentage, 10)
        self.assertEqual(stop_loss.sell_percentage, 50)
        self.assertEqual(stop_loss.high_water_mark, 20)

    def test_is_triggered_default(self):
        stop_loss = TradeStopLoss(
            trade_id=1,
            trade_risk_type="fixed",
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )

        self.assertFalse(stop_loss.has_triggered(20))
        self.assertFalse(stop_loss.has_triggered(19))
        self.assertTrue(stop_loss.has_triggered(18))
        self.assertTrue(stop_loss.has_triggered(17))

    def test_is_triggered_trailing(self):
        stop_loss = TradeStopLoss(
            trade_id=1,
            trade_risk_type="trailing",
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )

        self.assertEqual(stop_loss.stop_loss_price, 18)
        self.assertFalse(stop_loss.has_triggered(20))
        self.assertFalse(stop_loss.has_triggered(19))
        self.assertTrue(stop_loss.has_triggered(18))
        self.assertTrue(stop_loss.has_triggered(17))

        # Increase the high water mark, setting the stop loss price to 22.5
        self.assertFalse(stop_loss.has_triggered(25))
        self.assertEqual(stop_loss.stop_loss_price, 22.5)
        self.assertFalse(stop_loss.has_triggered(24))
        self.assertFalse(stop_loss.has_triggered(23))
        self.assertTrue(stop_loss.has_triggered(22))
