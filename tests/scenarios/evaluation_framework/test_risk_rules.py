"""Declared/manual risk rules and historical trailing high-water marks."""

from investing_algorithm_framework import (
    PositionMode,
    ScenarioSetupError,
    SignalSide,
    StopLossRule,
    TakeProfitRule,
)
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)

from .helpers import (
    BAR, START, EvaluationFrameworkTestCase, collect_and_resolve, scenario,
)


class TestRiskRules(EvaluationFrameworkTestCase):
    def test_risk_previews_match_attached_long_and_short_protection(self):
        for side in ("long", "short"):
            with self.subTest(side=side):
                strategy = ConfluenceScoringStrategy(
                    stop_losses=[StopLossRule(
                        symbol="BTC", percentage_threshold=5,
                        sell_percentage=100, mirror_on_exchange=True,
                    )],
                    take_profits=[TakeProfitRule(
                        symbol="BTC", percentage_threshold=10,
                        sell_percentage=50,
                    )],
                )
                with scenario(strategy, position_mode=PositionMode.HEDGE) \
                        as seeded:
                    self.assertIs(
                        seeded.get_stop_loss_rule("btc", side=side),
                        strategy.stop_losses[0],
                    )
                    self.assertIs(
                        seeded.get_take_profit_rule("BTC", side=side),
                        strategy.take_profits[0],
                    )
                    stop = seeded.preview_stop_loss(
                        "BTC", price=100, amount=2, side=side,
                    )
                    profit = seeded.preview_take_profit(
                        "BTC", price=100, amount=2, side=side,
                    )
                    self.assertEqual(seeded.context.get_trades(), [])
                    self.assertEqual(seeded.context.get_open_orders(), [])
                    self.assertEqual(seeded.context.get_unallocated(), 1_000)
                    self.assertTrue(stop.mirror_on_exchange)
                    self.assertAlmostEqual(
                        stop.stop_loss_price, 95 if side == "long" else 105,
                    )
                    self.assertAlmostEqual(
                        profit.take_profit_price,
                        110 if side == "long" else 90,
                    )
                    trade = seeded.open_trade(
                        "BTC", amount=2, price=100, direction=side,
                    )
                    self.assertEqual(
                        stop.stop_loss_price,
                        trade.stop_losses[0].stop_loss_price,
                    )
                    self.assertEqual(
                        profit.take_profit_price,
                        trade.take_profits[0].take_profit_price,
                    )
                    self.assertEqual(stop.sell_amount, 2)
                    self.assertEqual(
                        profit.sell_amount, trade.take_profits[0].sell_amount,
                    )
                    self.assertEqual(profit.sell_amount, 1)
                    seeded.check_consistency()

    def test_side_specific_lookup_matches_the_portfolio_mode(self):
        for mode, threshold in (
            (PositionMode.NETTING, 3), (PositionMode.HEDGE, 8),
        ):
            with self.subTest(mode=mode):
                strategy = ConfluenceScoringStrategy(
                    stop_losses=[
                        StopLossRule(3, 100, symbol="BTC"),
                        StopLossRule(5, 100, symbol="BTC", side="long"),
                        StopLossRule(8, 100, symbol="BTC", side="short"),
                    ],
                    take_profits=[
                        TakeProfitRule(3, 100, symbol="BTC"),
                        TakeProfitRule(8, 100, symbol="BTC", side="short"),
                    ],
                )
                with scenario(strategy, position_mode=mode) as seeded:
                    stop = seeded.preview_stop_loss(
                        "BTC", price=100, side="short",
                    )
                    profit = seeded.preview_take_profit(
                        "BTC", price=100, side="short",
                    )
                    self.assertAlmostEqual(
                        stop.stop_loss_price, 100 + threshold,
                    )
                    self.assertAlmostEqual(
                        profit.take_profit_price, 100 - threshold,
                    )
                    self.assertEqual(
                        seeded.get_stop_loss_rule(
                            "BTC", side="short",
                        ).percentage_threshold,
                        threshold,
                    )

    def test_contextual_risk_overrides_keep_the_netting_signature(self):
        class DynamicStrategy(ConfluenceScoringStrategy):
            def get_stop_loss_rule(self, symbol):
                return StopLossRule(
                    self.context.get_unallocated() / 100, 100, symbol=symbol,
                )

            def get_take_profit_rule(self, symbol):
                return TakeProfitRule(
                    self.context.get_unallocated() / 40, 50, symbol=symbol,
                )

        strategy = DynamicStrategy()
        original_context = strategy.context
        with scenario(strategy) as seeded:
            self.assertEqual(
                seeded.get_stop_loss_rule("BTC").percentage_threshold, 10,
            )
            self.assertEqual(
                seeded.get_take_profit_rule("BTC").percentage_threshold, 25,
            )
            self.assertAlmostEqual(
                seeded.preview_stop_loss("BTC", price=100).stop_loss_price,
                90,
            )
            self.assertAlmostEqual(
                seeded.preview_take_profit(
                    "BTC", price=100,
                ).take_profit_price, 125,
            )
            self.assertIs(strategy.context, original_context)
            self.assertEqual(seeded.context.get_trades(), [])
            seeded.check_consistency()

    def test_detached_trailing_previews_do_not_change_seeded_protection(self):
        for side, mark, stop_price, profit_price, pullback in (
            ("long", 120, 114, 108, 107),
            ("short", 80, 84, 88, 89),
        ):
            with self.subTest(side=side):
                strategy = ConfluenceScoringStrategy(
                    stop_losses=[
                        StopLossRule(5, 100, symbol="BTC", trailing=True),
                    ],
                    take_profits=[
                        TakeProfitRule(10, 100, symbol="BTC", trailing=True),
                    ],
                )
                with scenario(strategy, position_mode=PositionMode.HEDGE) \
                        as seeded:
                    trade = seeded.open_trade(
                        "BTC", amount=1, price=100, direction=side,
                    )
                    original_cash = seeded.context.get_unallocated()
                    stop = seeded.preview_stop_loss(
                        "BTC", price=100, side=side,
                    )
                    profit = seeded.preview_take_profit(
                        "BTC", price=100, side=side,
                    )
                    self.assertIsNone(profit.take_profit_price)
                    stop.update_with_last_reported_price(mark, START)
                    profit.update_with_last_reported_price(mark, START)
                    self.assertAlmostEqual(stop.stop_loss_price, stop_price)
                    self.assertAlmostEqual(
                        profit.take_profit_price, profit_price,
                    )
                    self.assertTrue(profit.has_triggered(pullback))
                    self.assertTrue(stop.has_triggered(pullback))
                    fresh = seeded.preview_take_profit(
                        "BTC", price=100, side=side,
                    )
                    self.assertIsNone(fresh.take_profit_price)
                    stored = seeded.context.get_open_trades(
                        target_symbol="BTC",
                    )[0]
                    self.assertEqual(stored.id, trade.id)
                    self.assertEqual(
                        stored.stop_losses[0].high_water_mark, 100,
                    )
                    self.assertIsNone(
                        stored.take_profits[0].high_water_mark,
                    )
                    self.assertEqual(
                        seeded.context.get_unallocated(), original_cash,
                    )
                    self.assertEqual(seeded.now, START)
                    seeded.check_consistency()

    def test_missing_risk_rules_and_invalid_preview_inputs(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            for kind in ("stop_loss", "take_profit"):
                with self.subTest(kind=kind):
                    get_rule = getattr(seeded, f"get_{kind}_rule")
                    preview = getattr(seeded, f"preview_{kind}")
                    self.assertIsNone(get_rule("BTC"))
                    self.assertIsNone(preview("BTC", price=100))
                    for arguments in (
                        {"price": 0}, {"price": float("nan")},
                        {"price": 100, "amount": 0},
                        {"price": 100, "amount": True},
                        {"price": 100, "side": "BUY"},
                    ):
                        with self.subTest(arguments=arguments):
                            with self.assertRaises(ScenarioSetupError):
                                preview("BTC", **arguments)
                    with self.assertRaises(ScenarioSetupError):
                        get_rule("BTC/EUR")
            seeded.check_consistency()
        with self.assertRaisesRegex(ScenarioSetupError, "closed"):
            seeded.get_stop_loss_rule("BTC")
        with self.assertRaisesRegex(ScenarioSetupError, "closed"):
            seeded.preview_take_profit("BTC", price=100)

    def test_risk_override_prices_and_context_are_scoped(self):
        class DynamicStrategy(ConfluenceScoringStrategy):
            def get_stop_loss_rule(self, symbol):
                return StopLossRule(
                    self.context.get_portfolio().allocated / 10,
                    100, symbol=symbol,
                )

        strategy = DynamicStrategy()
        original_context = strategy.context
        with scenario(strategy) as seeded:
            seeded.open_trade(
                "ETH", amount=1, price=100, apply_strategy_rules=False,
            )
            provider = seeded._context.data_provider_service
            with self.assertRaisesRegex(ScenarioSetupError, "ETH/EUR"):
                seeded.preview_stop_loss("BTC", price=100)
            self.assertIs(strategy.context, original_context)
            self.assertIs(seeded._context.data_provider_service, provider)
            stop = seeded.preview_stop_loss(
                "BTC", price=100, prices={"ETH": 150},
            )
            self.assertAlmostEqual(stop.stop_loss_price, 85)
            self.assertIs(strategy.context, original_context)
            self.assertIs(seeded._context.data_provider_service, provider)
            self.assertEqual(len(seeded.context.get_trades()), 1)
            seeded.check_consistency()

    def test_hedge_risk_overrides_receive_the_position_side(self):
        class DynamicStrategy(ConfluenceScoringStrategy):
            def get_stop_loss_rule(self, symbol, side):
                return StopLossRule(
                    5 if side == "long" else 8, 100, symbol=symbol,
                )

            def get_take_profit_rule(self, symbol, side):
                return TakeProfitRule(
                    10 if side == "long" else 20, 100, symbol=symbol,
                )

        strategy = DynamicStrategy()
        with scenario(strategy, position_mode=PositionMode.HEDGE) as seeded:
            for side, stop_price, profit_price in (
                ("long", 95, 110), ("short", 108, 80),
            ):
                with self.subTest(side=side):
                    self.assertAlmostEqual(
                        seeded.preview_stop_loss(
                            "BTC", price=100, side=side,
                        ).stop_loss_price, stop_price,
                    )
                    self.assertAlmostEqual(
                        seeded.preview_take_profit(
                            "BTC", price=100, side=side,
                        ).take_profit_price, profit_price,
                    )
            self.assertIsNone(strategy.context)

    def test_strategy_risk_rules_attach_to_lots_and_pending_entries(self):
        for apply_rules in (False, True):
            with self.subTest(apply_rules=apply_rules):
                strategy = ConfluenceScoringStrategy(
                    stop_losses=[StopLossRule(
                        symbol="BTC", percentage_threshold=5,
                        sell_percentage=100,
                    )],
                    take_profits=[TakeProfitRule(
                        symbol="BTC", percentage_threshold=10,
                        sell_percentage=100,
                    )],
                )
                with scenario(strategy) as seeded:
                    trade = seeded.open_trade(
                        "BTC", amount=1, price=100,
                        apply_strategy_rules=apply_rules,
                    )
                    pending = seeded.place_order(
                        "BTC", side="BUY", amount=1, price=90,
                        apply_strategy_rules=apply_rules,
                    )
                    count = int(apply_rules)
                    self.assertEqual(len(trade.stop_losses), count)
                    self.assertEqual(len(trade.take_profits), count)
                    self.assertEqual(
                        len(pending.pending_stop_losses), count,
                    )
                    self.assertEqual(
                        len(pending.pending_take_profits), count,
                    )
                    if apply_rules:
                        self.assertAlmostEqual(
                            trade.stop_losses[0].stop_loss_price, 95,
                        )
                        self.assertAlmostEqual(
                            trade.take_profits[0].take_profit_price, 110,
                        )
                    state = collect_and_resolve(seeded)
                    self.assertEqual(
                        [signal.side for signal in state.raw_signals],
                        [SignalSide.OPEN_LONG],
                    )
                    self.assertEqual(state.approved_signals, [])
                    seeded.check_consistency()

    def test_manual_risk_rules_and_trailing_marks_preserve_history(self):
        strategy = ConfluenceScoringStrategy()
        with scenario(strategy) as seeded:
            trade = seeded.open_trade(
                "BTC", amount=1, price=100, opened_at=START - 3 * BAR,
            )
            seeded.add_stop_loss(
                trade, percentage=5, trailing=True,
                created_at=START - 2 * BAR,
            )
            seeded.add_take_profit(
                trade, percentage=50, created_at=START - 2 * BAR,
            )
            seeded.mark_price("BTC", 130, at=START - BAR)
            stored = seeded.context.get_open_trades(target_symbol="BTC")[0]
            stop = stored.stop_losses[0]
            self.assertEqual(stop.high_water_mark, 130)
            self.assertEqual(stop.high_water_mark_date, START - BAR)
            self.assertAlmostEqual(stop.stop_loss_price, 123.5)
            self.assertEqual(
                stored.take_profits[0].take_profit_price, 150,
            )
            self.assertEqual(stored.last_reported_price, 130)
            self.assertEqual(stored.opened_at, START - 3 * BAR)
            self.assertEqual(seeded.now, START)

            with self.assertRaisesRegex(
                ScenarioSetupError, "triggers.*stop-loss",
            ):
                seeded.mark_price("BTC", 120, at=START)
            unchanged = seeded.context.get_open_trades(
                target_symbol="BTC",
            )[0]
            self.assertEqual(unchanged.last_reported_price, 130)
            self.assertEqual(unchanged.stop_losses[0].high_water_mark, 130)
            self.assertEqual(seeded.context.get_unallocated(), 900)
            state = collect_and_resolve(seeded, signal="exit")
            self.assertEqual(
                [signal.side for signal in state.raw_signals],
                [SignalSide.CLOSE_LONG],
            )
            self.assertEqual(
                [signal.side for signal in state.approved_signals],
                [SignalSide.CLOSE_LONG],
            )
            seeded.check_consistency()
