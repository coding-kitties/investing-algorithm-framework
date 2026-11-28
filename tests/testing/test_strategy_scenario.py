"""Tests for the StrategyScenario setup harness (#625).

One test case per acceptance criterion of the issue. Valid strategies use
the shared RSI/EMA confluence baseline. Every scenario runs in memory:
no CSV data, no network and nothing written to the repository tree.
"""
import inspect
import os
import re
import socket
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import BacktestDateRange, \
    CooldownRule, DataSource, PortfolioConfiguration, PositionMode, \
    RESOURCE_DIRECTORY, ScalingRule, SignalSide, StopLossRule, \
    TakeProfitRule
from investing_algorithm_framework import StrategyScenario, \
    ScenarioSetupError, ScenarioStateError
from investing_algorithm_framework.domain import OperationalException
from tests.resources.strategies_for_testing.confluence_strategy import \
    ConfluenceScoringStrategy

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


class MyStrategy(ConfluenceScoringStrategy):
    """Use the same real RSI/EMA baseline as the capability scenarios."""


def minimal_example():
    from datetime import datetime, timedelta, timezone
    from investing_algorithm_framework import StrategyScenario

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with StrategyScenario(MyStrategy(), initial_cash=1_000,
                          trading_symbol="EUR", market="BITVAVO",
                          start=start) as scenario:
        trade = scenario.open_trade("BTC", amount=2, price=100,
                                    opened_at=start - timedelta(hours=4))
        assert trade.open_price == 100 and trade.amount == 2
        assert scenario.context.get_unallocated() == 800
        assert scenario.context.get_position("BTC").cost == 200
        return trade


def scenario(strategy=None, mode=None, cash=1_000, **kwargs):
    return StrategyScenario(
        strategy or MyStrategy(), initial_cash=cash, start=START,
        trading_symbol="EUR", market="BITVAVO", position_mode=mode,
        **kwargs,
    )


def snapshot(s):
    """Everything a seeding call could change, as plain values."""
    services = s._services
    with s._activate():
        return {
            "now": s.now,
            "cash": services.portfolio_service().get_all()[0].unallocated,
            "positions": sorted(
                (p.symbol, p.long_amount, p.short_amount, p.long_cost,
                 p.short_cost)
                for p in services.position_service().get_all()),
            "trades": sorted(
                (t.id, t.available_amount, t.last_reported_price,
                 tuple((r.stop_loss_price, r.high_water_mark)
                       for r in t.stop_losses),
                 tuple((r.take_profit_price, r.high_water_mark)
                       for r in t.take_profits))
                for t in services.trade_service().get_all()),
            "orders": sorted(
                (o.id, o.order_side, o.status, o.filled)
                for o in services.order_service().get_all()),
            "allocations": sorted(
                (a.trade_id, a.amount_pending) for a in
                services.trade_allocation_repository().get_all()),
            "cooldowns": (
                dict(s.strategy._cooldown_tracker._last_event),
                dict(s.strategy._cooldown_remaining),
                dict(s.strategy._scale_out_counts),
            ),
        }


class TestPublicImport(TestCase):
    """AC1: public import and a minimal example, no private API."""

    def test_both_import_paths_resolve(self):
        from investing_algorithm_framework import testing
        self.assertIs(testing.StrategyScenario, StrategyScenario)
        self.assertIs(testing.ScenarioSetupError, ScenarioSetupError)
        self.assertTrue(issubclass(ScenarioSetupError, OperationalException))
        self.assertTrue(issubclass(ScenarioStateError, OperationalException))

    def test_minimal_example_seeds_an_existing_trade(self):
        trade = minimal_example()
        self.assertEqual(trade.opened_at, START - 4 * HOUR)
        self.assertFalse(trade.is_short)
        self.assertEqual(trade.strategy_id, "MyStrategy")

    def test_minimal_example_uses_no_private_names(self):
        source = inspect.getsource(minimal_example)
        self.assertIsNone(re.search(r"\b_\w", source))


class TestConsistency(TestCase):
    """AC2: cash, lots, positions, cost basis and reservations agree."""

    def test_lots_fee_and_pending_orders_agree(self):
        with scenario() as s:
            first = s.open_trade("BTC", amount=2, price=100,
                                 opened_at=START - 4 * HOUR)
            s.open_trade("BTC", amount=1, price=120,
                         opened_at=START - 2 * HOUR, fee=1.5)
            buy = s.place_order("BTC", side="BUY", amount=1, price=90)
            sell = s.place_order("BTC", side="SELL", amount=1, price=150)

            context = s.context
            # 1000 - 200 - 120 - fee 1.5 - BUY reservation 90
            self.assertAlmostEqual(context.get_unallocated(), 588.5)
            position = context.get_position("BTC")
            # The pending SELL reserves 1 of the 3 held.
            self.assertEqual(position.long_amount, 2)
            self.assertEqual(position.short_amount, 0)
            self.assertEqual(position.cost, 320)
            trades = sorted(context.get_trades(), key=lambda t: t.id)
            self.assertEqual([t.amount for t in trades], [2, 1])
            # FIFO: the oldest lot holds the reservation.
            self.assertEqual([t.available_amount for t in trades], [1, 1])
            self.assertEqual(trades[0].id, first.id)
            self.assertEqual(
                {o.id for o in context.get_open_orders()},
                {buy.id, sell.id},
            )
            self.assertEqual(buy.status, "OPEN")
            s.check_consistency()

    def test_short_and_cover_reservations_agree(self):
        with scenario(mode=PositionMode.HEDGE) as s:
            s.open_trade("BTC", amount=1, price=110, direction="short")
            s.place_order("BTC", side="COVER", amount=0.5, price=100)
            s.place_order("BTC", side="SHORT", amount=1, price=130)
            # 1000 + short proceeds 110 - COVER 50 - SHORT 130
            self.assertAlmostEqual(s.context.get_unallocated(), 930)
            s.check_consistency()

    def test_seeded_cooldowns_match_replayed_bars(self):
        from unittest.mock import MagicMock
        from investing_algorithm_framework import Signal
        from investing_algorithm_framework.services.strategy_phases \
            import CollectSignalsPhase, EmittedOrder, PhaseState, \
            RecordCooldownPhase, SizedIntent

        class Quiet(MyStrategy):
            def generate_signals(self, context, data):
                return []

        def tick(strategy, emit=None):
            state = PhaseState(strategy=strategy, context=MagicMock(),
                               data={}, current_datetime=START)
            CollectSignalsPhase().run(state)
            if emit is not None:
                state.emitted_orders = [EmittedOrder(
                    intent=SizedIntent(
                        signal=Signal("BTC", emit), amount=1, price=1,
                        quote_amount=1, full_symbol="BTC/EUR",
                        order_reason=emit.value),
                    order=MagicMock())]
                RecordCooldownPhase().run(state)
            return state.bar_index

        rule = CooldownRule(symbol="BTC", trigger="buy", bars=4)
        scaling = ScalingRule(symbol="BTC", max_entries=3,
                              cooldown_in_bars=3)
        for bars_ago in (1, 2, 3, 4):
            replayed = Quiet(cooldowns=[rule], scaling_rules=[scaling])
            tick(replayed, SignalSide.SCALE_IN)
            for _ in range(bars_ago - 1):
                tick(replayed)
            seeded = Quiet(cooldowns=[rule], scaling_rules=[scaling])
            with scenario(seeded) as s:
                s.record_cooldown(
                    "BTC", side=SignalSide.SCALE_IN, bars_ago=bars_ago)
            # The next evaluation of each strategy sees the same state.
            results = [
                (strategy._cooldown_tracker.remaining_bars(
                    rule, symbol="BTC", bar_index=tick(strategy)),
                 strategy._cooldown_remaining)
                for strategy in (replayed, seeded)
            ]
            with self.subTest(bars_ago=bars_ago):
                self.assertEqual(results[0], results[1])
                self.assertEqual(results[0][0], 4 - bars_ago)

    def test_stop_order_reservation_is_checked(self):
        with scenario() as s:
            s.context.create_order(
                target_symbol="BTC", price=None, order_type="STOP",
                order_side="BUY", amount=1, stop_price=110)
            self.assertEqual(s.context.get_unallocated(), 890)
            s.check_consistency()
            s.open_trade("ETH", amount=1, price=10)

    def test_corrupted_ledger_is_reported(self):
        with scenario() as s:
            s.open_trade("BTC", amount=2, price=100)
            with s._activate():
                services = s._services
                btc = services.position_service().find({"symbol": "BTC"})
                services.position_service().update(
                    btc.id, {"long_amount": 5, "long_cost": 7})
                portfolio = services.portfolio_service().get_all()[0]
                services.portfolio_repository().update(
                    portfolio.id, {"unallocated": 1})

            with self.assertRaises(ScenarioStateError) as error:
                s.check_consistency()
            violations = error.exception.violations
            self.assertTrue(any("BTC long leg 5" in v for v in violations))
            self.assertTrue(
                any("BTC long leg cost 7" in v for v in violations))
            self.assertTrue(
                any(v.startswith("unallocated 1") for v in violations))


class TestDirectionAndMode(TestCase):
    """AC3: long/short direction and netting/hedge are preserved."""

    def test_netting_long_and_short(self):
        with scenario() as s:
            trade = s.open_trade("BTC", amount=1, price=100)
            self.assertFalse(trade.is_short)
            self.assertEqual(s.context.get_position("BTC").amount, 1)

        with scenario() as s:
            trade = s.open_trade("BTC", amount=1, price=100,
                                 direction="short")
            self.assertTrue(trade.is_short)
            position = s.context.get_position("BTC")
            self.assertEqual(
                (position.long_amount, position.short_amount,
                 position.short_cost, position.amount),
                (0, 1, 100, -1),
            )
            self.assertEqual(s.context.get_unallocated(), 1_100)

    def test_hedge_holds_independent_legs(self):
        with scenario(mode=PositionMode.HEDGE) as s:
            s.open_trade("BTC", amount=1, price=100)
            s.open_trade("BTC", amount=2, price=110, direction="short")
            position = s.context.get_position("BTC")
            self.assertEqual(
                (position.long_amount, position.short_amount,
                 position.long_cost, position.short_cost),
                (1, 2, 100, 220),
            )
            configuration = s.context.portfolio_configuration_service \
                .get_all()[0]
            self.assertEqual(configuration.position_mode, PositionMode.HEDGE)

    def test_netting_rejects_opposite_direction_with_hint(self):
        for first, second in (("long", "short"), ("short", "long")):
            with scenario() as s:
                s.open_trade("BTC", amount=1, price=100, direction=first)
                with self.assertRaisesRegex(
                        ScenarioSetupError, "PositionMode.HEDGE"):
                    s.open_trade("BTC", amount=1, price=100,
                                 direction=second)

    def test_side_specific_rules_attach_to_their_leg(self):
        strategy = MyStrategy(
            stop_losses=[StopLossRule(
                symbol="BTC", percentage_threshold=10, sell_percentage=100,
                side="short")],
            take_profits=[TakeProfitRule(
                symbol="BTC", percentage_threshold=20, sell_percentage=50)],
        )
        with scenario(strategy, mode=PositionMode.HEDGE) as s:
            long = s.open_trade("BTC", amount=1, price=100)
            short = s.open_trade("BTC", amount=1, price=100,
                                 direction="short")
            self.assertEqual(long.stop_losses, [])
            self.assertEqual(len(short.stop_losses), 1)
            self.assertTrue(short.stop_losses[0].is_short)
            self.assertAlmostEqual(short.stop_losses[0].stop_loss_price, 110)
            # The side-less take-profit applies to both legs.
            self.assertEqual(
                [len(t.take_profits) for t in (long, short)], [1, 1])

            plain = s.open_trade("BTC", amount=1, price=100,
                                 apply_strategy_rules=False)
            self.assertEqual(plain.take_profits, [])

    def test_pending_entry_queues_strategy_rules(self):
        strategy = MyStrategy(stop_losses=[StopLossRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100)])
        with scenario(strategy) as s:
            order = s.place_order("BTC", side="BUY", amount=1, price=100)
            self.assertEqual(len(order.pending_stop_losses), 1)

    def test_trailing_state_follows_marks(self):
        with scenario() as s:
            trade = s.open_trade("BTC", amount=1, price=100,
                                 opened_at=START - 3 * HOUR)
            s.add_stop_loss(trade, percentage=5, trailing=True,
                            created_at=START - 3 * HOUR)
            s.mark_price("BTC", 130, at=START - HOUR)
            rule = s.context.get_trades()[0].stop_losses[0]
            self.assertEqual(rule.high_water_mark, 130)
            self.assertAlmostEqual(rule.stop_loss_price, 123.5)
            self.assertEqual(rule.high_water_mark_date, START - HOUR)

    def test_cooldowns_are_keyed_per_side_in_hedge(self):
        rule = CooldownRule(symbol="BTC", trigger="sell", bars=3)
        strategy = MyStrategy(cooldowns=[rule])
        with scenario(strategy, mode=PositionMode.HEDGE) as s:
            s.record_cooldown("BTC", side=SignalSide.OPEN_SHORT, bars_ago=1)
            tracker = strategy._cooldown_tracker
            remaining = {
                side: tracker.remaining_bars(
                    rule, symbol="BTC", bar_index=1, position_side=side)
                for side in ("long", "short")
            }
            self.assertEqual(remaining, {"long": 0, "short": 2})

    def test_scaling_countdown_is_aged_by_bars_ago(self):
        strategy = MyStrategy(scaling_rules=[
            ScalingRule(symbol="BTC", max_entries=3, cooldown_in_bars=4)])
        with scenario(strategy) as s:
            s.record_cooldown("BTC", side=SignalSide.SCALE_OUT, bars_ago=2)
            self.assertEqual(strategy._cooldown_remaining, {"BTC": 3})
            self.assertEqual(strategy._scale_out_counts, {"BTC": 1})
            s.record_cooldown("BTC", side=SignalSide.SCALE_OUT, bars_ago=1)
            self.assertEqual(strategy._cooldown_remaining, {"BTC": 4})
            self.assertEqual(strategy._scale_out_counts, {"BTC": 2})


class TestValidation(TestCase):
    """AC4: invalid setup raises an actionable error, changing nothing."""

    def test_constructor_errors(self):
        naive = datetime(2024, 1, 1)
        strategy_with_sources = MyStrategy(data_sources=[
            *MyStrategy.data_sources,
            DataSource(symbol="ETH/USDT", data_type="OHLCV",
                       time_frame="2h", market="BINANCE"),
        ])
        ran = MyStrategy()
        ran._cooldown_bar_index = 3
        cases = [
            (dict(start=naive), "timezone-aware"),
            (dict(start=START + timedelta(minutes=5)), "on the UTC hour"),
            (dict(start=datetime(2024, 1, 1, 5, tzinfo=timezone(
                timedelta(hours=5, minutes=30)))), "on the UTC hour"),
            (dict(position_mode="sideways"), "position_mode must be"),
            (dict(trading_symbol=5), "trading_symbol is required"),
            (dict(trading_symbol=None, market=None,
                  portfolio_configuration={"market": "BITVAVO"}),
             "must be a PortfolioConfiguration"),
            (dict(initial_cash=-1), "initial_cash must be"),
            (dict(initial_cash=float("inf")), "initial_cash must be"),
            (dict(trading_symbol=None), "trading_symbol is required"),
            (dict(market=None, strategy=MyStrategy(data_sources=[
                replace(MyStrategy.data_sources[0], market=None),
            ])),
             "no market"),
            (dict(market=None, strategy=strategy_with_sources),
             "['BINANCE', 'BITVAVO']"),
            (dict(trading_symbol=None, market=None,
                  portfolio_configuration=PortfolioConfiguration(
                      market="BITVAVO", trading_symbol="EUR",
                      initial_balance=500)),
             "conflicts with portfolio_configuration.initial_balance 500"),
            (dict(portfolio_configuration=PortfolioConfiguration(
                market="BITVAVO", trading_symbol="EUR")),
             "inside portfolio_configuration"),
            (dict(strategy=ran), "already run"),
            (dict(strategy=object()), "TradingStrategy instance"),
        ]
        for overrides, message in cases:
            arguments = dict(
                strategy=MyStrategy(), initial_cash=1_000, start=START,
                trading_symbol="EUR", market="BITVAVO")
            arguments.update(overrides)
            with self.subTest(message), \
                    self.assertRaises(ScenarioSetupError) as error:
                StrategyScenario(arguments.pop("strategy"), **arguments)
            self.assertIn(message, str(error.exception))
            self.assertTrue(str(error.exception).startswith(
                "StrategyScenario(...): "))

    def test_market_comes_from_the_single_data_source_market(self):
        strategy = MyStrategy()
        with StrategyScenario(strategy, initial_cash=1, start=START,
                              trading_symbol="EUR") as s:
            self.assertEqual(
                s.context.portfolio_configuration_service.get_all()[0]
                .market, "BITVAVO")

    def test_seeding_errors_leave_state_unchanged(self):
        strategy = MyStrategy(stop_losses=[StopLossRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100)])
        with scenario(strategy) as s:
            trade = s.open_trade("BTC", amount=2, price=100,
                                 opened_at=START - 2 * HOUR)
            s.place_order("BTC", side="BUY", amount=1, price=100)
            s.mark_price("BTC", 101, at=START - HOUR / 2)
            unknown = SimpleNamespace(id=999)
            naive = datetime(2023, 12, 31)
            cases = [
                (lambda: s.open_trade("BTC", amount=0, price=100),
                 "amount must be a finite number > 0 (got 0)"),
                (lambda: s.open_trade("BTC", amount=1, price=-1),
                 "price must be"),
                (lambda: s.open_trade("BTC", amount=1, price=1, fee=-1),
                 "fee must be"),
                (lambda: s.open_trade("eur", amount=1, price=1),
                 "trading symbol"),
                (lambda: s.open_trade("BTC/EUR", amount=1, price=1),
                 "base symbol such as 'BTC'"),
                (lambda: s.open_trade("BTC", amount=1, price=1,
                                      direction="up"),
                 "direction must be"),
                (lambda: s.open_trade("BTC", amount=1, price=1,
                                      opened_at=naive),
                 "opened_at must be a timezone-aware"),
                (lambda: s.open_trade("BTC", amount=1, price=1,
                                      opened_at=START + HOUR),
                 "is after the scenario start"),
                (lambda: s.open_trade("BTC", amount=8, price=100, fee=1),
                 "open_trade('BTC', amount=8, price=100, direction='long',"
                 " fee=1): needs 801 EUR but 700.0 EUR is unallocated "
                 "(initial_cash 1000.0, pending order reservations 100.0)."
                 " Raise initial_cash"),
                (lambda: s.open_trade("BTC", amount=1, price=1,
                                      direction="short"),
                 "Use position_mode=PositionMode.HEDGE"),
                (lambda: s.place_order("BTC", side="SELL", amount=3,
                                       price=1),
                 "long leg has 2.0 BTC not yet reserved"),
                (lambda: s.place_order("BTC", side="COVER", amount=1,
                                       price=1),
                 "short leg has 0.0 BTC"),
                (lambda: s.place_order("BTC", side="HOLD", amount=1,
                                       price=1),
                 "side must be BUY, SELL, SHORT or COVER"),
                (lambda: s.add_stop_loss(trade, percentage=0),
                 "percentage must be"),
                (lambda: s.add_take_profit(trade, percentage=5,
                                           sell_percentage=150),
                 "sell_percentage must be in (0, 100]"),
                (lambda: s.add_stop_loss(trade, percentage=5,
                                         sell_percentage=10),
                 "stop-losses already sell 100.0%, so another 10% "
                 "exceeds 100%"),
                (lambda: s.add_take_profit(unknown, percentage=5),
                 "not an open trade of this scenario"),
                (lambda: s.add_take_profit(
                    trade, percentage=5, created_at=START - 3 * HOUR),
                 "is before trade"),
                (lambda: s.mark_price("ETH", 10, at=START),
                 "no open trade for ETH"),
                (lambda: s.mark_price("BTC", 110, at=START - 3 * HOUR),
                 "is before trade"),
                (lambda: s.mark_price("BTC", 110, at=START - HOUR),
                 "the last mark of trade"),
                (lambda: s.mark_price("BTC", 90, at=START),
                 "triggers the active stop-loss"),
                (lambda: s.record_cooldown("BTC", side="buy", bars_ago=1),
                 "side must be a SignalSide"),
                (lambda: s.record_cooldown(
                    "BTC", side=SignalSide.OPEN_LONG, bars_ago=0),
                 "bars_ago must be an int >= 1"),
                (lambda: s.record_cooldown(
                    "BTC", side=SignalSide.OPEN_LONG, bars_ago=1),
                 "declares no CooldownRule or ScalingRule for BTC"),
            ]
            before = snapshot(s)
            for seed, message in cases:
                with self.subTest(message), \
                        self.assertRaises(ScenarioSetupError) as error:
                    seed()
                self.assertIn(message, str(error.exception))
                self.assertEqual(snapshot(s), before)
            s.check_consistency()

    def test_cooldowns_are_recorded_oldest_first(self):
        strategy = MyStrategy(cooldowns=[CooldownRule(symbol="BTC", bars=5)])
        with scenario(strategy) as s:
            s.record_cooldown("BTC", side=SignalSide.OPEN_LONG, bars_ago=1)
            with self.assertRaisesRegex(ScenarioSetupError, "oldest first"):
                s.record_cooldown(
                    "BTC", side=SignalSide.CLOSE_LONG, bars_ago=2)

    def test_cooldown_order_is_per_symbol(self):
        strategy = MyStrategy(cooldowns=[CooldownRule(bars=5)])
        with scenario(strategy) as s:
            s.record_cooldown("BTC", side=SignalSide.OPEN_LONG, bars_ago=1)
            s.record_cooldown("ETH", side=SignalSide.OPEN_LONG, bars_ago=3)

    def test_mark_cannot_predate_a_rule(self):
        with scenario() as s:
            trade = s.open_trade("BTC", amount=1, price=100,
                                 opened_at=START - 2 * HOUR)
            s.add_stop_loss(trade, percentage=5, trailing=True)
            with self.assertRaisesRegex(
                    ScenarioSetupError, "a rule of trade 1 was created"):
                s.mark_price("BTC", 120, at=START - HOUR)

    def test_strategy_cannot_join_two_open_scenarios(self):
        strategy = MyStrategy()
        with scenario(strategy):
            with self.assertRaisesRegex(
                    ScenarioSetupError, "belongs to an open scenario"):
                scenario(strategy)


class TestIndependence(TestCase):
    """AC5: scenarios share no runtime state, trackers, clocks or
    storage."""

    def test_interleaved_scenarios_stay_separate(self):
        rule = CooldownRule(symbol="BTC", bars=2)
        a_strategy = MyStrategy(cooldowns=[rule])
        b_strategy = MyStrategy(cooldowns=[rule])
        a = scenario(a_strategy)
        b = scenario(b_strategy, mode=PositionMode.HEDGE, cash=500)
        try:
            a.open_trade("BTC", amount=2, price=100,
                         opened_at=START - HOUR)
            b.open_trade("BTC", amount=1, price=50, direction="short")
            a.place_order("BTC", side="SELL", amount=1, price=120)
            a.record_cooldown("BTC", side=SignalSide.OPEN_LONG, bars_ago=1)

            self.assertEqual(a.context.get_unallocated(), 800)
            self.assertEqual(b.context.get_unallocated(), 550)
            self.assertEqual(len(a.context.get_open_orders()), 1)
            self.assertEqual(b.context.get_open_orders(), [])
            self.assertEqual(
                [t.is_short for t in b.context.get_trades()], [True])
            self.assertTrue(a_strategy._cooldown_tracker._last_event)
            self.assertFalse(b_strategy._cooldown_tracker._last_event)
            self.assertIsNot(a._state, b._state)
            self.assertIsNot(a._services.configuration_service(),
                             b._services.configuration_service())
            self.assertEqual((a.now, b.now), (START, START))
            a.check_consistency()
            b.check_consistency()
        finally:
            a.close()
            b.close()

    def test_sql_app_in_same_process_sees_no_scenario_rows(self):
        from investing_algorithm_framework.app import App
        from investing_algorithm_framework.dependency_container import \
            DependencyContainer
        from investing_algorithm_framework.infrastructure.database \
            import teardown_sqlalchemy

        with tempfile.TemporaryDirectory() as directory:
            app = App()
            app.container = DependencyContainer()
            app.set_config(RESOURCE_DIRECTORY, directory)
            app.add_portfolio_configuration(PortfolioConfiguration(
                market="BITVAVO", trading_symbol="EUR",
                initial_balance=1_000))
            app.initialize_backtest_config(
                BacktestDateRange(START, START), initial_amount=1_000)
            app.initialize_storage(remove_database_if_exists=True)
            app.initialize_backtest_services()
            app.initialize_backtest_portfolios()
            try:
                with scenario() as s:
                    s.open_trade("BTC", amount=2, price=100)
                    s.place_order("BTC", side="BUY", amount=1, price=100)
                self.assertEqual(app.container.order_service().get_all(), [])
                self.assertEqual(app.context.get_unallocated(), 1_000)
            finally:
                teardown_sqlalchemy()

    def test_services_reached_through_context_stay_scoped(self):
        with scenario() as s:
            s.open_trade("BTC", amount=1, price=100)
            orders = s.context.order_service.get_all()
            self.assertEqual([o.order_side for o in orders], ["BUY"])

    def test_environment_does_not_change_the_portfolio(self):
        overrides = {
            "BITVAVO_OVERRIDE_INITIAL_BALANCE": "5",
            "INITIAL_BALANCE": "7",
            "MARKET": "BINANCE",
            "TRADING_SYMBOL": "USDT",
            "RESOURCE_DIRECTORY": "/nonexistent",
        }
        with patch.dict(os.environ, overrides), scenario() as s:
            self.assertEqual(s.context.get_unallocated(), 1_000)
            configuration = s.context.portfolio_configuration_service \
                .get_all()[0]
            self.assertEqual(
                (configuration.market, configuration.trading_symbol),
                ("BITVAVO", "EUR"))

    def test_no_network_and_no_files_outside_the_temp_dir(self):
        cwd = os.getcwd()
        before = set(os.listdir(cwd))

        def refuse(*args, **kwargs):
            raise AssertionError("network access attempted")

        with patch.object(socket, "socket", refuse), \
                patch.object(socket, "create_connection", refuse):
            with scenario() as s:
                trade = s.open_trade("BTC", amount=1, price=100)
                s.add_take_profit(trade, percentage=10)
                s.place_order("BTC", side="SELL", amount=1, price=130)
                s.mark_price("BTC", 105, at=START)
                self.assertEqual(os.listdir(s._tmp.name), [])

        self.assertEqual(os.getcwd(), cwd)
        self.assertEqual(set(os.listdir(cwd)), before)


class TestCleanup(TestCase):
    """AC6: fixture setup and cleanup."""

    def test_close_is_idempotent_and_releases_everything(self):
        strategy = MyStrategy()
        s = scenario(strategy)
        s.open_trade("BTC", amount=1, price=100)
        directory = s._tmp.name
        s.close()
        s.close()

        self.assertFalse(os.path.exists(directory))
        self.assertEqual(s._state.rows, {})
        for use in (
            lambda: s.open_trade("BTC", amount=1, price=100),
            lambda: s.context.get_unallocated(),
            lambda: s.now,
            lambda: s.check_consistency(),
        ):
            with self.assertRaisesRegex(ScenarioSetupError, "closed"):
                use()

        with scenario(strategy) as again:
            self.assertEqual(again.context.get_trades(), [])
            self.assertEqual(again.context.get_unallocated(), 1_000)
            # A repeated close of the old scenario keeps the new binding.
            s.close()
            with self.assertRaisesRegex(ScenarioSetupError, "belongs"):
                scenario(strategy)

    def test_cleanup_runs_when_the_body_raises(self):
        strategy = MyStrategy()
        with self.assertRaises(ValueError):
            with scenario(strategy) as s:
                directory = s._tmp.name
                raise ValueError("test body failed")
        self.assertFalse(os.path.exists(directory))
        scenario(strategy).close()

    def test_unclosed_scenario_releases_the_strategy(self):
        import gc

        strategy = MyStrategy()
        s = scenario(strategy)
        directory = s._tmp.name
        with self.assertWarns(ResourceWarning):
            del s
            gc.collect()
        self.assertFalse(os.path.exists(directory))
        scenario(strategy).close()

    def test_failed_construction_releases_the_strategy(self):
        from investing_algorithm_framework.app import App

        strategy = MyStrategy()
        made = []
        real = tempfile.TemporaryDirectory

        def track(*args, **kwargs):
            made.append(real(*args, **kwargs))
            return made[-1]

        with patch.object(App, "initialize_backtest_services",
                          side_effect=RuntimeError("boom")), \
                patch("investing_algorithm_framework.testing.scenario"
                      ".TemporaryDirectory", track), \
                self.assertRaises(RuntimeError):
            scenario(strategy)
        self.assertFalse(os.path.exists(made[0].name))
        scenario(strategy).close()
