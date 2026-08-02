"""Unit tests for :class:`TradeHookDispatcher`.

These tests exercise the dispatcher in isolation (no app/container),
using minimal :class:`TradingStrategy` subclasses and plain objects
standing in for ``Trade`` (the dispatcher only reads ``.metadata`` and
``.id`` off whatever is passed to ``dispatch``).
"""
from types import SimpleNamespace
from unittest import TestCase

from investing_algorithm_framework import Schedule, TimeUnit, TradingStrategy
from investing_algorithm_framework.services.trade_hooks import (
    TRADE_HOOK_NAMES,
    TradeHookDispatcher,
)


class _NoOpStrategy(TradingStrategy):
    """Strategy that overrides nothing — the common case."""
    schedule = Schedule.every(1, TimeUnit.SECOND)


class _RecordingStrategy(TradingStrategy):
    """Strategy that overrides every trade hook and records calls."""
    schedule = Schedule.every(1, TimeUnit.SECOND)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def _record(self, name, context, trade):
        self.calls.append((name, context, trade))

    def on_trade_created(self, context, trade):
        self._record("on_trade_created", context, trade)

    def on_trade_opened(self, context, trade):
        self._record("on_trade_opened", context, trade)

    def on_trade_closed(self, context, trade):
        self._record("on_trade_closed", context, trade)

    def on_trade_updated(self, context, trade):
        self._record("on_trade_updated", context, trade)

    def on_trade_stop_loss_triggered(self, context, trade):
        self._record("on_trade_stop_loss_triggered", context, trade)

    def on_trade_trailing_stop_loss_triggered(self, context, trade):
        self._record(
            "on_trade_trailing_stop_loss_triggered", context, trade
        )

    def on_trade_take_profit_triggered(self, context, trade):
        self._record("on_trade_take_profit_triggered", context, trade)

    def on_trade_stop_loss_created(self, context, trade):
        self._record("on_trade_stop_loss_created", context, trade)

    def on_trade_trailing_stop_loss_created(self, context, trade):
        self._record(
            "on_trade_trailing_stop_loss_created", context, trade
        )

    def on_trade_take_profit_created(self, context, trade):
        self._record("on_trade_take_profit_created", context, trade)

    def on_trade_stop_loss_updated(self, context, trade):
        self._record("on_trade_stop_loss_updated", context, trade)

    def on_trade_trailing_stop_loss_updated(self, context, trade):
        self._record(
            "on_trade_trailing_stop_loss_updated", context, trade
        )

    def on_trade_take_profit_updated(self, context, trade):
        self._record("on_trade_take_profit_updated", context, trade)


class _RaisingStrategy(TradingStrategy):
    """Strategy whose hook implementation raises."""
    schedule = Schedule.every(1, TimeUnit.SECOND)

    def on_trade_created(self, context, trade):
        raise ValueError("boom")


def _trade(trade_id="trade-1", strategy_id=None):
    return SimpleNamespace(id=trade_id, metadata={"strategy_id": strategy_id}
                            if strategy_id is not None else {})


class TestTradeHookNames(TestCase):

    def test_all_13_hooks_are_tracked(self):
        # Every on_trade_* hook defined on TradingStrategy must be
        # known to the dispatcher, otherwise it can never be wired.
        strategy_hooks = {
            name for name in dir(TradingStrategy)
            if name.startswith("on_trade_")
        }
        self.assertEqual(strategy_hooks, set(TRADE_HOOK_NAMES))
        self.assertEqual(13, len(TRADE_HOOK_NAMES))


class TestTradeHookDispatcherConfigure(TestCase):

    def test_no_overrides_detected_for_base_strategy(self):
        dispatcher = TradeHookDispatcher()
        strategy = _NoOpStrategy(strategy_id="s1")
        dispatcher.configure([strategy], context=None)
        self.assertFalse(dispatcher._any_active)
        self.assertEqual(
            frozenset(), dispatcher._active_hooks_by_id["s1"]
        )

    def test_overrides_detected_for_recording_strategy(self):
        dispatcher = TradeHookDispatcher()
        strategy = _RecordingStrategy(strategy_id="s1")
        dispatcher.configure([strategy], context=None)
        self.assertTrue(dispatcher._any_active)
        self.assertEqual(
            frozenset(TRADE_HOOK_NAMES),
            dispatcher._active_hooks_by_id["s1"]
        )

    def test_configure_resets_previous_state(self):
        dispatcher = TradeHookDispatcher()
        dispatcher.configure([_RecordingStrategy(strategy_id="s1")], None)
        self.assertTrue(dispatcher._any_active)

        dispatcher.configure([_NoOpStrategy(strategy_id="s2")], None)
        self.assertFalse(dispatcher._any_active)
        self.assertNotIn("s1", dispatcher._strategies_by_id)


class TestTradeHookDispatcherDispatch(TestCase):

    def test_noop_when_no_strategy_overrides_anything(self):
        dispatcher = TradeHookDispatcher()
        strategy = _NoOpStrategy(strategy_id="s1")
        dispatcher.configure([strategy], context="ctx")
        # Should not raise and should be a true no-op.
        dispatcher.dispatch("on_trade_created", _trade())

    def test_noop_when_trade_is_none(self):
        dispatcher = TradeHookDispatcher()
        strategy = _RecordingStrategy(strategy_id="s1")
        dispatcher.configure([strategy], context="ctx")
        dispatcher.dispatch("on_trade_created", None)
        self.assertEqual([], strategy.calls)

    def test_dispatches_to_owning_strategy_by_strategy_id(self):
        dispatcher = TradeHookDispatcher()
        owner = _RecordingStrategy(strategy_id="owner")
        other = _RecordingStrategy(strategy_id="other")
        dispatcher.configure([owner, other], context="ctx")

        trade = _trade(strategy_id="owner")
        dispatcher.dispatch("on_trade_created", trade)

        self.assertEqual(
            [("on_trade_created", "ctx", trade)], owner.calls
        )
        self.assertEqual([], other.calls)

    def test_broadcasts_when_trade_has_no_strategy_id(self):
        dispatcher = TradeHookDispatcher()
        a = _RecordingStrategy(strategy_id="a")
        b = _RecordingStrategy(strategy_id="b")
        dispatcher.configure([a, b], context="ctx")

        trade = _trade(strategy_id=None)
        dispatcher.dispatch("on_trade_created", trade)

        self.assertEqual(1, len(a.calls))
        self.assertEqual(1, len(b.calls))

    def test_only_calls_hook_if_overridden_even_when_owned(self):
        dispatcher = TradeHookDispatcher()
        owner = _NoOpStrategy(strategy_id="owner")
        dispatcher.configure([owner], context="ctx")

        # No strategy overrides anything, so _any_active is False and
        # this should be a pure no-op (nothing to assert on _NoOpStrategy
        # since it has no recording behaviour — this just must not raise).
        dispatcher.dispatch(
            "on_trade_created", _trade(strategy_id="owner")
        )

    def test_exception_in_hook_is_isolated(self):
        dispatcher = TradeHookDispatcher()
        strategy = _RaisingStrategy(strategy_id="s1")
        dispatcher.configure([strategy], context="ctx")

        # Must not propagate.
        dispatcher.dispatch(
            "on_trade_created", _trade(strategy_id="s1")
        )

    def test_unknown_strategy_id_on_trade_is_ignored(self):
        dispatcher = TradeHookDispatcher()
        strategy = _RecordingStrategy(strategy_id="s1")
        dispatcher.configure([strategy], context="ctx")

        trade = _trade(strategy_id="does-not-exist")
        dispatcher.dispatch("on_trade_created", trade)

        self.assertEqual([], strategy.calls)
