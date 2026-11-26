"""Concrete strategy sizing and non-emitting production order previews."""

from investing_algorithm_framework import (
    CooldownRule, ExposureRule, PositionMode, PositionSize, ScalingRule,
    ScenarioOrderPreview, ScenarioSetupError, SignalSide,
)
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import START, EvaluationFrameworkTestCase, scenario


class DynamicConfluenceStrategy(ConfluenceScoringStrategy):
    def get_position_size(self, symbol):
        return PositionSize(
            symbol=symbol,
            fixed_amount=self.context.get_unallocated() * 0.1,
        )


class PriceAwarePositionSize(PositionSize):
    def get_size(self, portfolio, asset_price):
        return asset_price * 0.75


class TestPositionSizing(EvaluationFrameworkTestCase):
    def test_raw_allocation_and_order_preview_without_submitting_orders(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_position_size("btc", price=100), 250,
            )
            for _ in range(2):
                preview = seeded.preview_order("BTC", price=100)
                self.assertIsInstance(preview, ScenarioOrderPreview)
                self.assertTrue(preview.approved)
                self.assertEqual(len(preview.orders), 1)
                self.assertEqual(preview.orders[0].quote_amount, 250)
                self.assertEqual(preview.orders[0].amount, 2.5)
                self.assertEqual(seeded.context.get_unallocated(), 1_000)
                self.assertEqual(seeded.context.get_open_orders(), [])
                self.assertEqual(seeded.context.get_trades(), [])
                self.assertEqual(seeded.now, START)
                seeded.check_consistency()

    def test_sizing_honors_context_dependent_strategy_override(self):
        strategy = DynamicConfluenceStrategy()
        original_context = strategy.context
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_position_size("BTC", price=100), 100,
            )
            preview = seeded.preview_order("BTC", price=100)
            self.assertEqual(preview.orders[0].quote_amount, 100)
            self.assertEqual(preview.orders[0].amount, 1)
            self.assertIs(strategy.context, original_context)

            seeded.place_order("ETH", side="BUY", amount=4, price=100)
            self.assertEqual(seeded.context.get_unallocated(), 600)
            self.assertEqual(
                seeded.get_position_size(
                    "BTC", price=100, prices={"ETH": 100},
                ),
                60,
            )
            preview = seeded.preview_order(
                "BTC", price=100, prices={"ETH": 100},
            )
            self.assertTrue(preview.approved)
            self.assertEqual(preview.orders[0].quote_amount, 60)
            self.assertAlmostEqual(preview.orders[0].amount, 0.6)
            self.assertEqual(seeded.context.get_unallocated(), 600)
            self.assertEqual(len(seeded.context.get_open_orders()), 1)
            self.assertIs(strategy.context, original_context)
            seeded.check_consistency()

    def test_custom_rule_get_size_receives_the_asset_price(self):
        strategy = ConfluenceScoringStrategy(position_sizes=[
            PriceAwarePositionSize(symbol="BTC"),
        ])
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_position_size("BTC", price=200), 150,
            )
            preview = seeded.preview_order("BTC", price=200)
            self.assertEqual(preview.orders[0].amount, 0.75)
            self.assertEqual(preview.orders[0].quote_amount, 150)

    def test_zero_allocation_returns_a_blocked_preview_with_diagnostics(self):
        strategy = ConfluenceScoringStrategy(position_sizes=[
            PositionSize(symbol="BTC", fixed_amount=0),
        ])
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_position_size("BTC", price=100), 0,
            )
            preview = seeded.preview_order("BTC", price=100)
            self.assertFalse(preview.approved)
            self.assertEqual(preview.orders, ())
            self.assertIn("preview_order.zero_size", dict(preview.traces))
            self.assertEqual(seeded.context.get_open_orders(), [])

    def test_pending_cash_reservations_limit_preview_not_raw_sizing(self):
        strategy = ConfluenceScoringStrategy(position_sizes=[
            PositionSize(symbol="BTC", fixed_amount=250),
        ])
        with scenario(strategy) as seeded:
            pending = seeded.place_order(
                "ETH", side="BUY", amount=9, price=100,
            )
            self.assertEqual(
                seeded.get_position_size(
                    "BTC", price=100, prices={"ETH": 100},
                ),
                250,
            )
            preview = seeded.preview_order(
                "BTC", price=100, prices={"ETH": 100},
            )
            self.assertEqual(preview.orders[0].quote_amount, 100)
            self.assertEqual(preview.orders[0].amount, 1)
            self.assertIn("apply_risk_budget.scale_factor", dict(
                preview.traces,
            ))
            self.assertEqual(seeded.context.get_unallocated(), 100)
            self.assertEqual(
                [order.id for order in seeded.context.get_open_orders()],
                [pending.id],
            )
            seeded.check_consistency()

    def test_exposure_limit_changes_preview_not_raw_allocation(self):
        strategy = ConfluenceScoringStrategy(
            exposure_rule=ExposureRule(max_portfolio_percentage=10),
        )
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_position_size("BTC", price=100), 250,
            )
            preview = seeded.preview_order("BTC", price=100)
            self.assertEqual(preview.orders[0].quote_amount, 100)
            self.assertEqual(preview.orders[0].amount, 1)

    def test_pending_order_blocks_preview_with_reason(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            seeded.place_order("BTC", side="BUY", amount=1, price=90)
            preview = seeded.preview_order("BTC", price=100)
            self.assertFalse(preview.approved)
            self.assertEqual(preview.orders, ())
            self.assertIn(
                "resolve_conflicts.blocked_open_order", dict(preview.traces),
            )
            self.assertEqual(seeded.context.get_unallocated(), 910)
            seeded.check_consistency()

    def test_holdings_block_entry_but_allow_closing_the_existing_lot(self):
        strategy = ConfluenceScoringStrategy(
            exposure_rule=ExposureRule(max_portfolio_percentage=1),
        )
        with scenario(strategy) as seeded:
            seeded.open_trade("BTC", amount=2, price=100)
            self.assertFalse(seeded.preview_order(
                "BTC", price=110,
            ).approved)
            preview = seeded.preview_order(
                "BTC", price=110, side=SignalSide.CLOSE_LONG,
            )
            self.assertEqual(preview.orders[0].amount, 2)
            self.assertEqual(preview.orders[0].quote_amount, 220)
            self.assertEqual(seeded.context.get_position("BTC").amount, 2)
            self.assertEqual(seeded.context.get_unallocated(), 800)
            seeded.check_consistency()

    def test_cooldown_preview_is_repeatable_and_does_not_age_history(self):
        for bars_ago, approved in ((1, False), (3, True)):
            with self.subTest(bars_ago=bars_ago):
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
                        preview = seeded.preview_order("BTC", price=100)
                        self.assertEqual(preview.approved, approved)
                    self.assertEqual(seeded.context.get_unallocated(), 1000)
                    self.assertEqual(seeded.now, START)

    def test_scaling_uses_production_entry_percentages_and_countdown(self):
        strategy = ConfluenceScoringStrategy(scaling_rules=[
            ScalingRule(
                symbol="BTC", max_entries=3, initial_entry_percentage=20,
                scale_in_percentage=[40, 40], cooldown_in_bars=3,
            ),
        ])
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_position_size("BTC", price=100), 250,
            )
            preview = seeded.preview_order("BTC", price=100)
            self.assertEqual(preview.orders[0].quote_amount, 50)
            seeded.open_trade("BTC", amount=0.5, price=100)
            preview = seeded.preview_order(
                "BTC", price=100, side=SignalSide.SCALE_IN,
            )
            self.assertEqual(preview.orders[0].quote_amount, 100)
            seeded.record_cooldown(
                "BTC", side=SignalSide.SCALE_IN, bars_ago=1,
            )
            for _ in range(2):
                preview = seeded.preview_order(
                    "BTC", price=100, side=SignalSide.SCALE_IN,
                )
                self.assertFalse(preview.approved)
                self.assertIn(
                    "resolve_conflicts.scaling_cooldown",
                    dict(preview.traces),
                )
            seeded.check_consistency()

    def test_other_asset_prices_and_context_restore_after_failure(self):
        strategy = ConfluenceScoringStrategy()
        original_context = strategy.context
        with scenario(strategy) as seeded:
            seeded.open_trade("ETH", amount=2, price=100)
            with self.assertRaisesRegex(ScenarioSetupError, "ETH/EUR"):
                seeded.get_position_size("BTC", price=100)
            self.assertIs(strategy.context, original_context)
            self.assertEqual(
                seeded.get_position_size(
                    "BTC", price=100, prices={"ETH": 150},
                ),
                275,
            )
            preview = seeded.preview_order(
                "BTC", price=100, prices={"ETH": 150},
            )
            self.assertEqual(preview.orders[0].quote_amount, 275)
            self.assertEqual(seeded.context.get_unallocated(), 800)
            self.assertIs(strategy.context, original_context)
            seeded.check_consistency()

    def test_hedged_cover_preview_uses_only_the_short_leg(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy, position_mode=PositionMode.HEDGE) as seeded:
            seeded.open_trade("BTC", amount=1, price=100)
            seeded.open_trade(
                "BTC", amount=2, price=110, direction="short",
            )
            preview = seeded.preview_order(
                "BTC", price=100, side=SignalSide.CLOSE_SHORT,
            )
            self.assertEqual(preview.orders[0].amount, 2)
            self.assertEqual(preview.orders[0].quote_amount, 200)
            position = seeded.context.get_position("BTC")
            self.assertEqual((position.long_amount, position.short_amount),
                             (1, 2))
            seeded.check_consistency()

    def test_invalid_inputs_and_closed_scenarios_fail_explicitly(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            for method in (seeded.get_position_size, seeded.preview_order):
                for price in (0, -1, float("nan")):
                    with self.subTest(method=method.__name__, price=price):
                        with self.assertRaisesRegex(
                            ScenarioSetupError, "price must be",
                        ):
                            method("BTC", price=price)
                with self.assertRaisesRegex(
                    ScenarioSetupError, "price conflicts",
                ):
                    method("BTC", price=100, prices={"BTC": 101})
            with self.assertRaisesRegex(ScenarioSetupError, "SignalSide"):
                seeded.preview_order("BTC", price=100, side="BUY")
            seeded.check_consistency()
        for method in (seeded.get_position_size, seeded.preview_order):
            with self.assertRaisesRegex(ScenarioSetupError, "closed"):
                method("BTC", price=100)
