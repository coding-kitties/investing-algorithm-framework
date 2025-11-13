from unittest import TestCase
from datetime import datetime
from investing_algorithm_framework.services import get_average_trade_return
from investing_algorithm_framework.domain import Trade


class TestAverageTradeReturnMetrics(TestCase):

    def test_average_trade_return_calculation(self):
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

        # Average gain should consider all trades, both winning and losing
        average_gain, percentage = get_average_trade_return(trades)

        # Average return = (150 + 200 + 300 - 50 - 300) / 5 = 60
        self.assertAlmostEqual(average_gain, 60, places=2)
        self.assertAlmostEqual(percentage, 0.6, places=2)
