"""Seeded holdings and pending orders gate real RSI/EMA signals."""

from investing_algorithm_framework import SignalSide
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    BAR, START, EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestSignalEligibility(EvaluationFrameworkTestCase):
    def test_seeded_position_controls_long_exit_eligibility(self):
        for held in (False, True):
            strategy = ConfluenceScoringStrategy()
            with self.subTest(held=held), scenario(strategy) as seeded:
                if held:
                    seeded.open_trade(
                        "BTC", amount=1, price=100,
                        opened_at=START - BAR,
                    )
                state = collect_and_resolve(seeded, signal="exit")
                expected = [SignalSide.CLOSE_LONG] if held else []
                self.assertEqual(
                    [signal.side for signal in state.raw_signals], expected,
                )
                self.assertEqual(
                    [signal.side for signal in state.approved_signals],
                    expected,
                )
                self.assertEqual(seeded.context.get_open_orders(), [])
                seeded.check_consistency()

    def test_seeded_state_gates_an_actual_rsi_ema_entry(self):
        for blocker in (None, "position", "pending_order"):
            strategy = ConfluenceScoringStrategy()
            with self.subTest(blocker=blocker), scenario(strategy) as seeded:
                if blocker == "position":
                    seeded.open_trade("BTC", amount=1, price=100)
                elif blocker == "pending_order":
                    seeded.place_order(
                        "BTC", side="BUY", amount=1, price=90,
                    )
                state = collect_and_resolve(seeded)

                self.assertEqual(
                    [signal.side for signal in state.raw_signals],
                    [SignalSide.OPEN_LONG],
                )
                self.assertEqual(
                    [signal.side for signal in state.approved_signals],
                    [SignalSide.OPEN_LONG] if blocker is None else [],
                )
                seeded.check_consistency()
