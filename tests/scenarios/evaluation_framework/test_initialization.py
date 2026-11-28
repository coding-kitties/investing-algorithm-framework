"""Initialize isolated scenario state for the real confluence strategy."""

from datetime import timedelta

from investing_algorithm_framework import (
    PortfolioConfiguration,
    PositionMode,
    ScenarioSetupError,
    SignalSide,
    StrategyScenario,
)
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    START, EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestInitialization(EvaluationFrameworkTestCase):
    def test_initial_cash_and_inferred_market_support_first_evaluation(self):
        for cash in (0, 1_000):

            with self.subTest(initial_cash=cash):

                strategy = ConfluenceScoringStrategy()

                with StrategyScenario(
                    strategy, initial_cash=cash, start=START,
                    trading_symbol="EUR",
                ) as seeded:

                    configuration = seeded.context \
                        .portfolio_configuration_service.get_all()[0]

                    self.assertEqual(configuration.market, "BITVAVO")
                    self.assertEqual(
                        configuration.position_mode, PositionMode.NETTING,
                    )
                    self.assertEqual(seeded.context.get_unallocated(), cash)
                    self.assertEqual(
                        seeded.context.get_position("EUR").amount, cash,
                    )
                    self.assertEqual(seeded.context.get_trades(), [])
                    self.assertEqual(seeded.context.get_open_orders(), [])
                    self.assertEqual(seeded.now, START)

                    state = collect_and_resolve(seeded)
                    self.assertEqual(
                        [signal.side for signal in state.raw_signals],
                        [SignalSide.OPEN_LONG],
                    )
                    self.assertEqual(
                        seeded.context.get_unallocated(), cash,
                    )
                    seeded.check_consistency()

    def test_explicit_portfolio_configuration_preserves_position_mode(self):
        for mode in (PositionMode.NETTING, PositionMode.HEDGE):
            with self.subTest(position_mode=mode):
                strategy = ConfluenceScoringStrategy()
                configuration = PortfolioConfiguration(
                    market="BITVAVO", trading_symbol="EUR",
                    initial_balance=1_000, position_mode=mode,
                )
                with StrategyScenario(
                    strategy, initial_cash=1_000, start=START,
                    portfolio_configuration=configuration,
                ) as seeded:
                    stored = seeded.context \
                        .portfolio_configuration_service.get_all()[0]
                    self.assertEqual(stored.market, "BITVAVO")
                    self.assertEqual(stored.trading_symbol, "EUR")
                    self.assertEqual(stored.position_mode, mode)
                    state = collect_and_resolve(seeded)
                    self.assertEqual(
                        [signal.side for signal in state.approved_signals],
                        [SignalSide.OPEN_LONG],
                    )
                    seeded.check_consistency()

    def test_invalid_initialization_leaves_strategy_available(self):
        cases = (
            ({"initial_cash": -1}, "initial_cash must be"),
            ({"start": START.replace(tzinfo=None)}, "timezone-aware"),
            ({"start": START + timedelta(minutes=5)}, "on the UTC hour"),
            ({"trading_symbol": None}, "trading_symbol is required"),
            ({"position_mode": "sideways"}, "position_mode must be"),
            ({
                "portfolio_configuration": PortfolioConfiguration(
                    market="BITVAVO", trading_symbol="EUR",
                ),
            }, "inside portfolio_configuration"),
        )
        for overrides, message in cases:
            with self.subTest(arguments=overrides):
                strategy = ConfluenceScoringStrategy()
                arguments = {
                    "initial_cash": 1_000,
                    "start": START,
                    "trading_symbol": "EUR",
                }
                arguments.update(overrides)
                with self.assertRaisesRegex(ScenarioSetupError, message):
                    StrategyScenario(strategy, **arguments)

                with scenario(strategy) as seeded:
                    state = collect_and_resolve(seeded)
                    self.assertEqual(
                        [signal.side for signal in state.approved_signals],
                        [SignalSide.OPEN_LONG],
                    )
                    self.assertEqual(
                        seeded.context.get_unallocated(), 1_000,
                    )
                    seeded.check_consistency()

    def test_active_strategy_cannot_initialize_another_scenario(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            seeded.open_trade("BTC", amount=1, price=100)
            with self.assertRaisesRegex(
                ScenarioSetupError, "belongs to an open scenario",
            ):
                scenario(strategy)

            state = collect_and_resolve(seeded, signal="exit")
            self.assertEqual(
                [signal.side for signal in state.approved_signals],
                [SignalSide.CLOSE_LONG],
            )
            self.assertEqual(seeded.context.get_unallocated(), 900)
            seeded.check_consistency()

    def test_evaluated_strategy_requires_a_fresh_instance(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            state = collect_and_resolve(seeded)
            self.assertEqual(
                [signal.side for signal in state.approved_signals],
                [SignalSide.OPEN_LONG],
            )

        with self.assertRaisesRegex(ScenarioSetupError, "already run"):
            scenario(strategy)

        fresh_strategy = ConfluenceScoringStrategy()
        with scenario(fresh_strategy) as seeded:
            state = collect_and_resolve(seeded)
            self.assertEqual(
                [signal.side for signal in state.approved_signals],
                [SignalSide.OPEN_LONG],
            )
            self.assertEqual(seeded.context.get_trades(), [])
            seeded.check_consistency()
