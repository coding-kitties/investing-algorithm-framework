from unittest import TestCase
from investing_algorithm_framework.domain import TradeTakeProfit

class TestTradeStopLoss(TestCase):

    def test_model_creation(self):
        stop_loss = TradeTakeProfit(
            trade_id=1,
            trailing=False,
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )
        self.assertEqual(stop_loss.trade_id, 1)
        self.assertFalse(stop_loss.trailing)
        self.assertEqual(stop_loss.percentage, 10)
        self.assertEqual(stop_loss.sell_percentage, 50)
        self.assertEqual(stop_loss.high_water_mark, None)
        self.assertEqual(stop_loss.take_profit_price, 22)

        take_profit = TradeTakeProfit(
            trade_id=1,
            trailing=True,
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )
        self.assertEqual(take_profit.trade_id, 1)
        self.assertTrue(take_profit.trailing)
        self.assertEqual(take_profit.percentage, 10)
        self.assertEqual(take_profit.sell_percentage, 50)
        self.assertEqual(take_profit.high_water_mark, None)
        self.assertEqual(take_profit.take_profit_price, None)

    def test_is_triggered_default(self):
        take_profit = TradeTakeProfit(
            trade_id=1,
            trailing=False,
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )

        self.assertEqual(take_profit.take_profit_price, 22)
        self.assertFalse(take_profit.has_triggered(20))
        self.assertFalse(take_profit.has_triggered(19))
        self.assertFalse(take_profit.has_triggered(18))
        self.assertFalse(take_profit.has_triggered(17))
        self.assertTrue(take_profit.has_triggered(22))

    def test_is_triggered_trailing(self):
        """
        Test the trailing stop loss

        * Open price: 20
        * Percentage: 10%
        * Sell percentage: 50%

        Initial take profit price: 22

        """
        take_profit = TradeTakeProfit(
            trade_id=1,
            trailing=True,
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )

        self.assertEqual(take_profit.take_profit_price, None)
        self.assertEqual(take_profit.high_water_mark, None)
        self.assertFalse(take_profit.has_triggered(20))
        self.assertFalse(take_profit.has_triggered(19))
        self.assertFalse(take_profit.has_triggered(18))
        self.assertFalse(take_profit.has_triggered(17))

        # Increase the high watermark, setting the stop loss price to 22.5
        self.assertFalse(take_profit.has_triggered(25))
        self.assertEqual(take_profit.high_water_mark, 25)
        self.assertAlmostEqual(take_profit.take_profit_price, 22.5, 2)
        self.assertFalse(take_profit.has_triggered(24))
        self.assertFalse(take_profit.has_triggered(23))
        self.assertTrue(take_profit.has_triggered(22))

        # Increase the high watermark, setting the stop loss price
        # to 27.0
        self.assertFalse(take_profit.has_triggered(30))
        self.assertAlmostEqual(take_profit.take_profit_price, 27.0, 2)
        self.assertEqual(take_profit.high_water_mark, 30)
        self.assertFalse(take_profit.has_triggered(29))
        self.assertFalse(take_profit.has_triggered(28))
        self.assertTrue(take_profit.has_triggered(25))
