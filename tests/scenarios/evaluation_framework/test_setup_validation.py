"""Invalid seeds fail explicitly without changing existing state."""

from investing_algorithm_framework import ScenarioSetupError, SignalSide
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    START, EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestSetupValidation(EvaluationFrameworkTestCase):
    def test_invalid_seeds_leave_existing_portfolio_unchanged(self):
        """Test in isolation."""
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            trade = seeded.open_trade("BTC", amount=2, price=100, fee=1)
            pending = seeded.place_order(
                "BTC", side="BUY", amount=1, price=100,
            )

            with self.assertRaisesRegex(
                ScenarioSetupError, "Raise initial_cash",
            ):
                seeded.open_trade("BTC", amount=7, price=100)

            with self.assertRaisesRegex(
                ScenarioSetupError, "long leg has",
            ):
                seeded.place_order("BTC", side="SELL", amount=3, price=100)

            with self.assertRaisesRegex(
                ScenarioSetupError, "PositionMode.HEDGE",
            ):
                seeded.open_trade(
                    "BTC", amount=1, price=100, direction="short",
                )

            self.assertEqual(seeded.context.get_unallocated(), 699)
            self.assertEqual(
                seeded.context.get_position("BTC").long_amount, 2,
            )
            self.assertEqual(seeded.context.get_position("BTC").cost, 200)
            self.assertEqual(
                [lot.id for lot in seeded.context.get_open_trades()],
                [trade.id],
            )
            self.assertEqual(
                [order.id for order in seeded.context.get_open_orders()],
                [pending.id],
            )
            self.assertEqual(seeded.now, START)
            state = collect_and_resolve(seeded)
            self.assertEqual(
                [signal.side for signal in state.raw_signals],
                [SignalSide.OPEN_LONG],
            )
            self.assertEqual(state.approved_signals, [])
            seeded.check_consistency()
