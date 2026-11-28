"""Hedged long/short lots and pending SHORT/COVER reservations."""

from investing_algorithm_framework import PositionMode, SignalSide
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestShortPositions(EvaluationFrameworkTestCase):
    def test_hedged_lots_and_short_cover_reservations_remain_independent(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy, position_mode=PositionMode.HEDGE) as seeded:
            seeded.open_trade("BTC", amount=1, price=100)
            short = seeded.open_trade(
                "BTC", amount=2, price=110, direction="short", fee=2,
            )
            cover = seeded.place_order(
                "BTC", side="COVER", amount=0.5, price=100,
            )
            pending_short = seeded.place_order(
                "BTC", side="SHORT", amount=1, price=130,
            )
            position = seeded.context.get_position("BTC")
            self.assertEqual(
                (position.long_amount, position.short_amount), (1, 2),
            )
            self.assertEqual(
                (position.long_cost, position.short_cost), (100, 220),
            )
            self.assertTrue(short.is_short)
            self.assertEqual(seeded.context.get_unallocated(), 938)
            self.assertSetEqual(
                {order.id for order in seeded.context.get_open_orders()},
                {cover.id, pending_short.id},
            )
            state = collect_and_resolve(seeded)
            self.assertEqual(
                [signal.side for signal in state.raw_signals],
                [SignalSide.OPEN_LONG],
            )
            self.assertEqual(state.approved_signals, [])
            seeded.check_consistency()
