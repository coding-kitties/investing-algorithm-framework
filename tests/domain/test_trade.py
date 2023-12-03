from datetime import datetime
from unittest import TestCase

from investing_algorithm_framework.domain import Trade


class Test(TestCase):

    def test_stop_loss_manual_trade(self):
        trade = Trade(
            buy_order_id=1,
            target_symbol='BTC',
            trading_symbol='USDT',
            amount=10,
            open_price=100,
            opened_at=datetime(2021, 1, 1),
        )
        self.assertTrue(trade.is_manual_stop_loss_trigger(
            101, [100, 110, 80], 2
        ))
        self.assertFalse(trade.is_manual_stop_loss_trigger(
            101, [100, 110, 80], 20
        ))

        # Test if the stop loss is triggered when the price
        # is lower then the open price
        self.assertTrue(
            trade.is_manual_stop_loss_trigger(80, [100, 110, 80], 2)
        )
        self.assertFalse(
            trade.is_manual_stop_loss_trigger(99, [100, 110, 80], 2)
        )
        self.assertFalse(
            trade.is_manual_stop_loss_trigger(90, [100, 110, 80], 20)
        )
        self.assertTrue(
            trade.is_manual_stop_loss_trigger(80, [100, 110, 80], 20)
        )
