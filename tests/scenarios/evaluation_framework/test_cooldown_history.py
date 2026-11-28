"""Seeded cooldown history blocks entries until its expiry boundary."""

from investing_algorithm_framework import (
    CooldownRule, PositionMode, ScalingRule, ScenarioSetupError,
    SignalSide,
)
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestCooldownHistory(EvaluationFrameworkTestCase):

    def test_seeded_cooldown_gates_the_next_confluence_entry(self):

        for bars_ago, blocked in ((1, True), (2, True), (3, False)):
            with self.subTest(bars_ago=bars_ago, blocked=blocked):
                strategy = ConfluenceScoringStrategy(cooldowns=[
                    CooldownRule(
                        symbol="BTC", trigger="buy", blocks="buy", bars=3,
                    ),
                ])
                with scenario(strategy) as seeded:
                    seeded.record_cooldown(
                        "BTC", side=SignalSide.OPEN_LONG, bars_ago=bars_ago,
                    )
                    for _ in range(2):
                        preview = seeded.preview_cooldown("btc")
                        self.assertEqual(preview.blocked, blocked)
                        self.assertEqual(
                            preview.remaining_bars, max(0, 3 - bars_ago),
                        )
                        self.assertEqual(
                            preview.rules,
                            tuple(strategy.cooldowns) if blocked else (),
                        )
                        self.assertFalse(seeded.preview_cooldown(
                            "BTC", side=SignalSide.CLOSE_LONG,
                        ).blocked)
                    state = collect_and_resolve(seeded)
                    self.assertEqual(
                        [signal.side for signal in state.raw_signals],
                        [SignalSide.OPEN_LONG],
                    )
                    self.assertEqual(
                        bool(state.approved_signals), not blocked,
                    )
                    self.assertEqual(
                        seeded.context.get_unallocated(), 1_000,
                    )
                    self.assertEqual(seeded.context.get_open_orders(), [])
                    seeded.check_consistency()

    def test_inspection_and_portfolio_scope_use_the_longest_active_wait(self):
        symbol_rule = CooldownRule(symbol="BTC", bars=3)
        portfolio_rule = CooldownRule(trigger="buy", blocks="buy", bars=5)
        unrelated_rule = CooldownRule(symbol="ETH", bars=10)
        strategy = ConfluenceScoringStrategy(cooldowns=[
            symbol_rule, portfolio_rule, unrelated_rule,
        ])
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_cooldown_rules("btc"),
                (symbol_rule, portfolio_rule),
            )
            self.assertFalse(seeded.preview_cooldown("BTC").blocked)
            seeded.record_cooldown(
                "ETH", side=SignalSide.OPEN_LONG, bars_ago=1,
            )
            for _ in range(2):
                preview = seeded.preview_cooldown("BTC")
                self.assertEqual(preview.remaining_bars, 4)
                self.assertEqual(preview.rules, (portfolio_rule,))
                self.assertFalse(seeded.preview_cooldown(
                    "BTC", side=SignalSide.CLOSE_LONG,
                ).blocked)
            seeded.record_cooldown(
                "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
            )
            preview = seeded.preview_cooldown("BTC")
            self.assertEqual(preview.rules, (symbol_rule, portfolio_rule))
            self.assertEqual(preview.remaining_bars, 4)
            self.assertFalse(seeded.preview_order("BTC", price=100).approved)
            seeded.check_consistency()

    def test_cooldown_preview_separates_hedge_legs_and_buy_cover_sides(self):
        strategy = ConfluenceScoringStrategy(cooldowns=[
            CooldownRule(trigger="sell", blocks="buy", bars=3),
        ])
        with scenario(strategy, position_mode=PositionMode.HEDGE) as seeded:
            seeded.record_cooldown(
                "BTC", side=SignalSide.OPEN_SHORT, bars_ago=1,
            )
            self.assertFalse(seeded.preview_cooldown("BTC").blocked)
            self.assertFalse(seeded.preview_cooldown(
                "BTC", side=SignalSide.OPEN_SHORT,
            ).blocked)
            cover = seeded.preview_cooldown(
                "BTC", side=SignalSide.CLOSE_SHORT,
            )
            self.assertTrue(cover.blocked)
            self.assertEqual(cover.remaining_bars, 2)
            self.assertEqual(seeded.context.get_trades(), [])
            seeded.check_consistency()

    def test_scaling_countdown_respects_policy_without_consuming_bars(self):
        for mode in (PositionMode.NETTING, PositionMode.HEDGE):
            with self.subTest(mode=mode):
                strategy = ConfluenceScoringStrategy(
                    scaling_rules=[ScalingRule(
                        symbol="BTC", max_entries=3, cooldown_in_bars=4,
                    )],
                    cooldowns=[CooldownRule(symbol="BTC", bars=6)],
                )
                with scenario(strategy, position_mode=mode) as seeded:
                    seeded.record_cooldown(
                        "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
                    )
                    timers = dict(strategy._cooldown_remaining)
                    for _ in range(2):
                        preview = seeded.preview_cooldown("BTC")
                        self.assertEqual(preview.remaining_bars, 5)
                        self.assertEqual(preview.scaling_remaining_bars, 3)
                        self.assertFalse(
                            seeded.preview_order("BTC", price=100).approved,
                        )
                        exit_preview = seeded.preview_cooldown(
                            "BTC", side=SignalSide.CLOSE_LONG,
                        )
                        self.assertEqual(
                            exit_preview.scaling_remaining_bars, 0,
                        )
                        self.assertEqual(
                            strategy._cooldown_remaining, timers,
                        )
                    seeded.check_consistency()

    def test_cooldown_input_validation_and_closed_scenarios(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            self.assertEqual(seeded.get_cooldown_rules("BTC"), ())
            self.assertFalse(seeded.preview_cooldown("BTC").blocked)
            with self.assertRaises(ScenarioSetupError):
                seeded.preview_cooldown("BTC", side="buy")
            with self.assertRaises(ScenarioSetupError):
                seeded.get_cooldown_rules("BTC/EUR")
        with self.assertRaisesRegex(ScenarioSetupError, "closed"):
            seeded.preview_cooldown("BTC")
        with self.assertRaisesRegex(ScenarioSetupError, "closed"):
            seeded.get_cooldown_rules("BTC")
