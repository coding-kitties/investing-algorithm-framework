from unittest import TestCase
from datetime import datetime
from investing_algorithm_framework.services import get_average_trade_loss
from investing_algorithm_framework.domain import Trade


class TestAverageTradeLossMetrics(TestCase):

    def test_average_trade_loss_calculation(self):
        trades = [
            Trade(
                id=1,
                open_price=100,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 2, 1),
                orders=[],
                net_gain=150,
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=1,
                available_amount=0,
                cost=100,
                remaining=0,
                filled_amount=1,
                status="CLOSED",
            ),
            Trade(
                id=1,
                open_price=100,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 2, 1),
                orders=[],
                net_gain=200,
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=1,
                available_amount=0,
                cost=100,
                remaining=0,
                filled_amount=1,
                status="CLOSED",
            ),
            Trade(
                id=1,
                open_price=100,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 2, 1),
                orders=[],
                net_gain=300,
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=1,
                available_amount=0,
                cost=100,
                remaining=0,
                filled_amount=1,
                status="CLOSED",
            ),
            Trade(
                id=1,
                open_price=100,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 2, 1),
                orders=[],
                net_gain=-50,
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=1,
                available_amount=0,
                cost=100,
                remaining=0,
                filled_amount=1,
                status="CLOSED",
            ),
            Trade(
                id=1,
                open_price=100,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 2, 1),
                orders=[],
                net_gain=-300,
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=1,
                available_amount=0,
                cost=100,
                remaining=0,
                filled_amount=1,
                status="CLOSED",
            ),
        ]

        # Average gain should only consider losing trades
        average_los, percentage = get_average_trade_loss(trades)

        # Average los = (-50 + -300) / 2 = -175
        # Average loss percentage = ((-50/100) + (-300/100)) / 2 = -1.75
        self.assertEqual(average_los, -175)
        self.assertEqual(percentage, -1.75)
