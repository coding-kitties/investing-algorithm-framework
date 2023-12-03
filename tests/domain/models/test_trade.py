from datetime import datetime
from unittest import TestCase

from investing_algorithm_framework.domain import Trade


class Test(TestCase):

    def test_trade(self):
        trade_opened_at = datetime(2023, 11, 29)
        trade = Trade(
            buy_order_id=1,
            target_symbol="BTC",
            trading_symbol="EUR",
            amount=1,
            open_price=19822.0,
            opened_at=trade_opened_at,
            closed_price=None,
            closed_at=None,
        )
        self.assertEqual(trade.target_symbol, "BTC")
        self.assertEqual(trade.trading_symbol, "EUR")
        self.assertEqual(trade.amount, 1)
        self.assertEqual(trade.open_price, 19822.0)
        self.assertEqual(trade.opened_at, trade_opened_at)
