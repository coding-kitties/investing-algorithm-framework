"""Interleaved scenarios keep portfolio state and cleanup independent."""

from investing_algorithm_framework import ScenarioSetupError, SignalSide
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestIsolation(EvaluationFrameworkTestCase):
    def test_interleaved_confluence_scenarios_isolate_state_and_cleanup(self):
        first_strategy = ConfluenceScoringStrategy()
        second_strategy = ConfluenceScoringStrategy()
        with scenario(first_strategy) as first, \
                scenario(second_strategy) as second:
            first.open_trade("BTC", amount=1, price=100)
            first.place_order("BTC", side="BUY", amount=1, price=90)
            self.assertEqual(first.context.get_unallocated(), 810)
            self.assertEqual(second.context.get_unallocated(), 1_000)
            self.assertEqual(second.context.get_trades(), [])
            self.assertEqual(second.context.get_open_orders(), [])
            first_signals = collect_and_resolve(first, signal="exit")
            second_signals = collect_and_resolve(second, signal="exit")
            self.assertEqual(
                [signal.side for signal in first_signals.raw_signals],
                [SignalSide.CLOSE_LONG],
            )
            self.assertEqual(second_signals.raw_signals, [])
            first.close()
            with self.assertRaisesRegex(ScenarioSetupError, "closed"):
                first.check_consistency()
            second.open_trade("BTC", amount=1, price=50)
            self.assertEqual(second.context.get_unallocated(), 950)
            second.check_consistency()
