from unittest import TestCase
from datetime import datetime
from investing_algorithm_framework.services import get_average_trade_gain
from investing_algorithm_framework.domain import Trade


class TestAverageTradeGainMetrics(TestCase):

    def test_average_trade_gain_calculation(self):
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

        # Average gain should not consider losing trades
        average_gain, percentage = get_average_trade_gain(trades)

        # Average gain = (150 + 200 + 300) / 3 = 216.67
        # Average gain percentage = ((150/100) + (200/100) + (300/100)) / 3 = 2.17 = 217%
        self.assertAlmostEqual(average_gain, 216.67, places=2)
        self.assertAlmostEqual(percentage, 2.17, places=2)
