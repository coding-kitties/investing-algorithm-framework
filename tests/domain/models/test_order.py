from datetime import datetime
from unittest import TestCase

from investing_algorithm_framework.domain import Order


class Test(TestCase):

    def test_from_ccxt_order(self):
        order = Order.from_ccxt_order(
            {
                "id": "123",
                "symbol": "BTC/USDT",
                "side": "buy",
                "type": "limit",
                "price": 10000,
                "amount": 1,
                "cost": 10000,
                "filled": 1,
                "remaining": 0,
                "status": "open",
                "timestamp": 1600000000000,
                "datetime": '2017-08-17 12:42:48.000',
                "lastTradeTimestamp": 1600000000000,
                "fee": {
                    "cost": 0.1,
                    "currency": "USDT"
                }
            }
        )
        self.assertEqual(order.get_external_id(), "123")
        self.assertEqual(order.get_symbol(), "BTC/USDT")
        self.assertEqual(order.get_order_side(), "BUY")
        self.assertEqual(order.get_order_type(), "LIMIT")
        self.assertEqual(order.get_price(), 10000)
        self.assertEqual(order.get_amount(), 1)
        self.assertEqual(order.get_filled(), 1)
        self.assertEqual(order.get_remaining(), 0)
        self.assertEqual(order.get_status(), "OPEN")
        self.assertEqual(
            order.get_created_at(), datetime(2017, 8, 17, 12, 42, 48)
        )
