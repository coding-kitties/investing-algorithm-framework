from unittest import TestCase
from investing_algorithm_framework.domain import TradeStopLoss


class TestTradeStopLoss(TestCase):

    def test_round_trip_preserves_fixed_trigger_and_filled_amount(self):
        stop_loss = TradeStopLoss(
            trade_id=1, percentage=5, open_price=120,
            total_amount_trade=10, is_short=True,
        )
        stop_loss.high_water_mark = 90
        stop_loss.sold_amount = 3
        restored = TradeStopLoss.from_dict(stop_loss.to_dict())
        self.assertEqual(restored.stop_loss_price, 126)
        self.assertEqual(restored.high_water_mark, 90)
        self.assertEqual(restored.sold_amount, 3)

    def test_model_creation(self):
        stop_loss = TradeStopLoss(
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
        self.assertEqual(stop_loss.high_water_mark, 20)

    def test_is_triggered_default(self):
        stop_loss = TradeStopLoss(
            trade_id=1,
            trailing=False,
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
            trailing=True,
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

        # Increase the high watermark, setting the stop loss price to 22.5
        self.assertFalse(stop_loss.has_triggered(25))
        self.assertEqual(stop_loss.stop_loss_price, 22.5)
        self.assertFalse(stop_loss.has_triggered(24))
        self.assertFalse(stop_loss.has_triggered(23))
        self.assertTrue(stop_loss.has_triggered(22))

    def test_mirror_fields_default(self):
        stop_loss = TradeStopLoss(
            trade_id=1,
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100
        )
        self.assertFalse(stop_loss.mirror_on_exchange)
        self.assertIsNone(stop_loss.mirror_order_id)
        self.assertFalse(stop_loss.mirror_triggered)
        self.assertIsNone(stop_loss.mirror_triggered_at)

    def test_mirror_fields_round_trip_via_dict(self):
        stop_loss = TradeStopLoss(
            trade_id=1,
            percentage=10,
            open_price=20,
            sell_percentage=50,
            total_amount_trade=100,
            mirror_on_exchange=True,
            mirror_order_id="ext-123",
            mirror_triggered=True,
            mirror_triggered_at="2024-01-01T00:00:00+00:00",
        )
        restored = TradeStopLoss.from_dict(stop_loss.to_dict())
        self.assertTrue(restored.mirror_on_exchange)
        self.assertEqual("ext-123", restored.mirror_order_id)
        self.assertTrue(restored.mirror_triggered)
        self.assertIsNotNone(restored.mirror_triggered_at)
