from unittest import TestCase
from investing_algorithm_framework.domain import Trade, OperationalException


class TestTradeStatus(TestCase):

    def test_trade_status(self):

        trade = Trade(
            id=1,
            open_price=100,
            opened_at=None,
            closed_at=None,
            orders=[],
            target_symbol="BTC",
            trading_symbol="EUR",
            amount=1,
            cost=100,
            available_amount=1,
            remaining=0,
            filled_amount=1,
            status="open"
        )
        self.assertEqual(trade.status, "OPEN")

    def test_invalid_trade_status(self):

        with self.assertRaises(OperationalException) as e:
            trade = Trade(
                id=1,
                open_price=100,
                opened_at=None,
                closed_at=None,
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=1,
                cost=100,
                available_amount=1,
                remaining=0,
                filled_amount=1,
                status="opened"
            )
            self.assertEqual(
                str(e.exception),
                "Could not convert value: 'opened' to TradeStatus"
            )
