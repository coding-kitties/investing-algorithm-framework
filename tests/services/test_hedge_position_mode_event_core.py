from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework import (
    ConflictPolicy,
    CooldownRule,
    CooldownTracker,
    MarketCredential,
    OrderSide,
    OrderStatus,
    PortfolioConfiguration,
    PositionMode,
    Schedule,
    Signal,
    SignalSide,
    StopLossRule,
    TakeProfitRule,
    TimeUnit,
    TradingStrategy,
)
from investing_algorithm_framework.services.strategy_phases import (
    PhaseState,
    ResolveConflictsPhase,
)
from tests.resources import TestBase


class TestHedgePositionModeTransactions(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance", api_key="api_key", secret_key="secret_key"
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=10_000,
            position_mode=PositionMode.NETTING,
        )
    ]
    external_balances = {"EUR": 10_000}

    def setUp(self):
        self.portfolio_configurations[0]._position_mode = PositionMode.NETTING
        super().setUp()
        self.portfolio_configurations[0]._position_mode = PositionMode.HEDGE

    def _fill(self, order):
        return self.app.container.order_service().update(
            order.id,
            {
                "filled": order.amount,
                "remaining": 0,
                "status": OrderStatus.CLOSED.value,
            },
        )

    def _open_both_legs(self):
        buy = self.app.context.create_limit_order(
            target_symbol="ADA",
            price=10,
            order_side=OrderSide.BUY,
            amount=20,
        )
        self._fill(buy)
        short = self.app.context.create_short_order(
            target_symbol="ADA", price=12, amount=10
        )
        self._fill(short)
        return self.app.container.trade_service().get_all(
            {"target_symbol": "ADA"}
        )

    def test_simultaneous_legs_and_independent_partial_closes(self):
        trades = self._open_both_legs()
        portfolio = self.app.container.portfolio_service().get(1)
        position_service = self.app.container.position_service()
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        self.assertEqual((20, 10, 10), (
            position.long_amount, position.short_amount, position.amount
        ))
        self.assertEqual((200, 120), (
            position.long_cost, position.short_cost
        ))

        sell = self.app.context.create_limit_order(
            target_symbol="ADA",
            price=15,
            order_side=OrderSide.SELL,
            amount=5,
        )
        self._fill(sell)
        cover = self.app.context.create_cover_order(
            target_symbol="ADA", price=8, amount=4
        )
        self._fill(cover)

        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        self.assertEqual((15, 6, 9), (
            position.long_amount, position.short_amount, position.amount
        ))
        self.assertEqual((150, 72), (
            position.long_cost, position.short_cost
        ))
        long_trade = next(trade for trade in trades if not trade.is_short)
        short_trade = next(trade for trade in trades if trade.is_short)
        long_trade = self.app.container.trade_service().get(long_trade.id)
        short_trade = self.app.container.trade_service().get(short_trade.id)
        self.assertEqual((15, 25), (
            long_trade.available_amount, long_trade.net_gain
        ))
        self.assertEqual((6, 16), (
            short_trade.available_amount, short_trade.net_gain
        ))

    def test_cover_fill_against_an_already_flat_short_leg_does_not_raise(self):
        """A stale/duplicate cover fill landing after the short leg is
        already flat must fail with a clear validation error instead of
        an unhandled ZeroDivisionError."""
        self._open_both_legs()
        portfolio = self.app.container.portfolio_service().get(1)
        position_service = self.app.container.position_service()
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )

        cover = self.app.context.create_cover_order(
            target_symbol="ADA", price=8, amount=10,
        )
        self._fill(cover)
        position = position_service.find(
            {"portfolio": portfolio.id, "symbol": "ADA"}
        )
        self.assertEqual(0, position.short_amount)

        with self.assertRaisesRegex(ValueError, "short_amount"):
            position_service.update_positions_with_cover_order_filled(
                cover, filled_amount=5, position_mode=PositionMode.HEDGE,
            )

    def test_take_profit_and_stop_loss_trigger_only_the_matching_leg(self):
        trades = self._open_both_legs()
        trade_service = self.app.container.trade_service()
        long_trade = next(trade for trade in trades if not trade.is_short)
        short_trade = next(trade for trade in trades if trade.is_short)
        trade_service.add_take_profit(long_trade, percentage=10)
        trade_service.add_take_profit(short_trade, percentage=10)
        trade_service.add_stop_loss(long_trade, percentage=10)
        trade_service.add_stop_loss(short_trade, percentage=10)

        now = datetime.now(tz=timezone.utc)
        trade_service.update(long_trade.id, {
            "last_reported_price": 11,
            "last_reported_price_datetime": now,
        })
        trade_service.update(short_trade.id, {
            "last_reported_price": 12,
            "last_reported_price_datetime": now,
        })
        take_profit_orders = trade_service.get_triggered_take_profit_orders()
        self.assertEqual(1, len(take_profit_orders))
        self.assertEqual(OrderSide.SELL.value,
                         take_profit_orders[0]["order_side"])
        self.assertEqual(long_trade.id,
                         take_profit_orders[0]["trades"][0]["trade_id"])

        trade_service.update(long_trade.id, {
            "last_reported_price": 10,
            "last_reported_price_datetime": now,
        })
        trade_service.update(short_trade.id, {
            "last_reported_price": 14,
            "last_reported_price_datetime": now,
        })
        stop_loss_orders = trade_service.get_triggered_stop_loss_orders()
        self.assertEqual(1, len(stop_loss_orders))
        self.assertEqual(OrderSide.COVER.value,
                         stop_loss_orders[0]["order_side"])
        self.assertEqual(short_trade.id,
                         stop_loss_orders[0]["trades"][0]["trade_id"])


class TestHedgePositionModeEventState(TestCase):
    def test_cooldown_events_are_independent_by_position_side(self):
        tracker = CooldownTracker()
        rule = CooldownRule(symbol="ADA", trigger="sell", bars=3)
        tracker.record(
            symbol="ADA", order_side="sell", bar_index=1,
            position_side="long",
        )
        blocked_long, _ = tracker.is_blocked(
            [rule], signal_side="sell", symbol="ADA", bar_index=2,
            position_side="long",
        )
        blocked_short, _ = tracker.is_blocked(
            [rule], signal_side="sell", symbol="ADA", bar_index=2,
            position_side="short",
        )
        self.assertTrue(blocked_long)
        self.assertFalse(blocked_short)

    def test_risk_rule_lookup_is_side_specific_with_default_fallback(self):
        strategy = TradingStrategy(
            schedule=Schedule.every(1, TimeUnit.DAY),
            stop_losses=[
                StopLossRule(5, 100, "ADA", side="long"),
                StopLossRule(8, 100, "ADA", side="short"),
            ],
            take_profits=[
                TakeProfitRule(10, 100, "ADA"),
                TakeProfitRule(15, 100, "ADA", side="short"),
            ],
        )
        self.assertEqual(
            5, strategy.get_stop_loss_rule("ADA", "long").percentage_threshold
        )
        self.assertEqual(
            8, strategy.get_stop_loss_rule("ADA", "short").percentage_threshold
        )
        self.assertEqual(
            10, strategy.get_take_profit_rule("ADA", "long").percentage_threshold
        )
        self.assertEqual(
            15, strategy.get_take_profit_rule("ADA", "short").percentage_threshold
        )

    def test_hedge_conflict_resolution_allows_opposite_opens(self):
        strategy = MagicMock()
        strategy.conflict_policy = ConflictPolicy.default()
        strategy.flip_on_opposite_signal = True
        strategy.has_open_orders.return_value = False
        strategy.has_position.return_value = False
        strategy.cooldowns = []
        strategy._cooldown_remaining = {}
        strategy._cooldown_tracker = CooldownTracker()
        context = MagicMock()
        context.get_open_trades.return_value = []
        portfolio = MagicMock(identifier="hedge", market="binance")
        context.get_portfolio.return_value = portfolio
        configuration = MagicMock(position_mode=PositionMode.HEDGE)
        context.portfolio_configuration_service.resolve_for_portfolio\
            .return_value = configuration
        state = PhaseState(
            strategy=strategy,
            context=context,
            data={},
            current_datetime=datetime.now(tz=timezone.utc),
            raw_signals=[
                Signal("ADA", SignalSide.OPEN_LONG),
                Signal("ADA", SignalSide.OPEN_SHORT),
            ],
            bar_index=1,
        )
        ResolveConflictsPhase().run(state)
        self.assertEqual(
            {SignalSide.OPEN_LONG, SignalSide.OPEN_SHORT},
            {signal.side for signal in state.approved_signals},
        )

    def test_netting_cooldown_default_key_is_unchanged(self):
        tracker = CooldownTracker()
        rule = CooldownRule(symbol="ADA", trigger="sell", bars=3)
        tracker.record(symbol="ADA", order_side="sell", bar_index=1)
        blocked, _ = tracker.is_blocked(
            [rule], signal_side="buy", symbol="ADA", bar_index=2
        )
        self.assertTrue(blocked)