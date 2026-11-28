"""Cash, fees, trade lots and FIFO pending-order reservations."""

from investing_algorithm_framework import SignalSide
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    BAR, START, EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestPortfolioState(EvaluationFrameworkTestCase):
    def test_seeded_lots_fees_and_fifo_reservations(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            first = seeded.open_trade(
                "BTC", amount=2, price=100, fee=1,
                opened_at=START - 3 * BAR,
            )
            second = seeded.open_trade(
                "BTC", amount=1, price=120, fee=0.5,
                opened_at=START - 2 * BAR,
            )
            buy = seeded.place_order("BTC", side="BUY", amount=1, price=90)
            sell = seeded.place_order(
                "BTC", side="SELL", amount=2.5, price=150,
            )

            self.assertAlmostEqual(
                seeded.context.get_unallocated(), 588.5,
            )
            self.assertAlmostEqual(
                seeded.context.get_position("EUR").amount, 588.5,
            )
            position = seeded.context.get_position("BTC")
            self.assertAlmostEqual(position.long_amount, 0.5)
            self.assertAlmostEqual(position.cost, 320)
            lots = {trade.id: trade for trade in seeded.context.get_trades()}
            self.assertEqual(lots[first.id].available_amount, 0)
            self.assertAlmostEqual(lots[second.id].available_amount, 0.5)
            for trade in lots.values():
                self.assertEqual(
                    trade.strategy_id, seeded.strategy.strategy_id,
                )
            self.assertSetEqual(
                {order.id for order in seeded.context.get_open_orders()},
                {buy.id, sell.id},
            )
            self.assertEqual(seeded.now, START)
            state = collect_and_resolve(seeded)
            self.assertEqual(
                [signal.side for signal in state.raw_signals],
                [SignalSide.OPEN_LONG],
            )
            self.assertEqual(state.approved_signals, [])
            seeded.check_consistency()
