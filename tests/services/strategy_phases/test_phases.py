"""Phase-level unit tests for the v9.0 strategy pipeline.

Each phase is exercised against minimal stub :class:`Strategy` /
:class:`Context` objects so failures pinpoint a specific phase
rather than the integrated pipeline. Parity tests against the
legacy ``run_strategy`` live in
``tests/app/strategy/test_pipeline_parity.py`` (added after Turn 4).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework import (
    ConflictPolicy,
    ConflictResolution,
    Signal,
    SignalSide,
)
from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)
from investing_algorithm_framework.domain.models.risk_rules import (
    CooldownTracker,
)
from investing_algorithm_framework.services.strategy_phases import (
    ApplyRiskBudgetPhase,
    AttachRiskRulesPhase,
    CollectSignalsPhase,
    EmitOrdersPhase,
    EmittedOrder,
    PhaseState,
    RecordCooldownPhase,
    ResolveConflictsPhase,
    SizePositionsPhase,
    SizedIntent,
)


# --------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------- #
class _StubPortfolio:
    def __init__(self, net_size: float = 10_000.0) -> None:
        self._net = net_size

    def get_net_size(self) -> float:
        return self._net


class _StubPositionSize:
    def __init__(self, quote_amount: float) -> None:
        self.quote_amount = quote_amount

    def get_size(self, portfolio, price) -> float:
        return self.quote_amount


class _StubScalingRule:
    def __init__(
        self,
        scale_in_pct: float = 50.0,
        scale_out_pct: float = 25.0,
        max_entries: int = 3,
        max_position_percentage: Optional[float] = None,
        cooldown_in_bars: int = 0,
    ) -> None:
        self.scale_in_pct = scale_in_pct
        self.scale_out_pct = scale_out_pct
        self.max_entries = max_entries
        self.max_position_percentage = max_position_percentage
        self.cooldown_in_bars = cooldown_in_bars

    def get_scale_in_percentage(self, index: int) -> float:
        return self.scale_in_pct

    def get_scale_out_percentage(self, index: int) -> float:
        return self.scale_out_pct


class _StubStopLossRule:
    def __init__(self, pct: float = 2.0) -> None:
        self.percentage_threshold = pct
        self.trailing = False
        self.sell_percentage = 100


class _StubTakeProfitRule:
    def __init__(self, pct: float = 5.0) -> None:
        self.percentage_threshold = pct
        self.trailing = False
        self.sell_percentage = 100


class _StubPosition:
    def __init__(self, amount: float = 0.0, cost: float = 0.0) -> None:
        self.amount = amount
        self.cost = cost


class _StubTrade:
    def __init__(
        self, available_amount: float, is_short: bool = False,
    ) -> None:
        self.available_amount = available_amount
        self.is_short = is_short


class _StubContext:
    def __init__(
        self,
        *,
        price: float = 100.0,
        trading_symbol: str = "EUR",
        unallocated: float = 10_000.0,
        portfolio: Optional[_StubPortfolio] = None,
        open_trades: Optional[Dict[str, List[_StubTrade]]] = None,
        position: Optional[_StubPosition] = None,
    ) -> None:
        self._price = price
        self._trading_symbol = trading_symbol
        self._unallocated = unallocated
        self._portfolio = portfolio or _StubPortfolio()
        self._open_trades = open_trades or {}
        self._position = position or _StubPosition()
        self.created_orders: List[Dict[str, Any]] = []
        self.attached_stop_losses: List[Dict[str, Any]] = []
        self.attached_take_profits: List[Dict[str, Any]] = []

    def get_trading_symbol(self) -> str:
        return self._trading_symbol

    def get_latest_price(self, full_symbol: str) -> float:
        return self._price

    def get_unallocated(self) -> float:
        return self._unallocated

    def get_portfolio(self) -> _StubPortfolio:
        return self._portfolio

    def get_open_trades(
        self, target_symbol: Optional[str] = None, market: Optional[str] = None,
    ) -> List[_StubTrade]:
        return list(self._open_trades.get(target_symbol, []))

    def get_position_percentage_of_portfolio_by_net_size(
        self, symbol: str,
    ) -> float:
        return 0.0

    # ---- order creation (recorded for assertions) ----------------- #
    def create_limit_order(self, **kwargs):
        kwargs["__route__"] = "limit"
        self.created_orders.append(kwargs)
        order = MagicMock(name=f"Order({kwargs.get('target_symbol')})")
        order.kwargs = kwargs
        return order

    def create_short_order(self, **kwargs):
        kwargs["__route__"] = "short"
        self.created_orders.append(kwargs)
        order = MagicMock(name=f"ShortOrder({kwargs.get('target_symbol')})")
        order.kwargs = kwargs
        return order

    def create_cover_order(self, **kwargs):
        kwargs["__route__"] = "cover"
        self.created_orders.append(kwargs)
        order = MagicMock(name=f"CoverOrder({kwargs.get('target_symbol')})")
        order.kwargs = kwargs
        return order

    def add_stop_loss(self, **kwargs):
        self.attached_stop_losses.append(kwargs)

    def add_take_profit(self, **kwargs):
        self.attached_take_profits.append(kwargs)


class _StubStrategy:
    """Minimal stand-in for :class:`TradingStrategy` carrying only
    the attributes the phases touch."""

    def __init__(
        self,
        symbols: List[str],
        *,
        position_sizes: Optional[Dict[str, _StubPositionSize]] = None,
        scaling_rules: Optional[Dict[str, _StubScalingRule]] = None,
        stop_losses: Optional[Dict[str, _StubStopLossRule]] = None,
        take_profits: Optional[Dict[str, _StubTakeProfitRule]] = None,
        positions: Optional[Dict[str, _StubPosition]] = None,
        open_orders_for: Optional[List[str]] = None,
        conflict_policy: Optional[ConflictPolicy] = None,
        generated_signals: Optional[List[Signal]] = None,
    ) -> None:
        self.strategy_id = "stub"
        self.symbols = symbols
        self._position_sizes = position_sizes or {}
        self._scaling_rules = scaling_rules or {}
        self._stop_losses = stop_losses or {}
        self._take_profits = take_profits or {}
        self._positions = positions or {}
        self._open_orders_for = set(open_orders_for or [])
        self.conflict_policy = conflict_policy or ConflictPolicy.default()
        self._generated = list(generated_signals or [])
        self.executor = None
        # cooldown machinery
        self.cooldowns: List = []
        self._cooldown_tracker = CooldownTracker()
        self._cooldown_remaining: Dict[str, int] = {}
        self._cooldown_bar_index = 0
        self._scale_out_counts: Dict[str, int] = {}

    # ---- methods the phases call --------------------------------- #
    def generate_signals(self, context, data):
        return iter(self._generated)

    def has_open_orders(self, symbol: str) -> bool:
        return symbol in self._open_orders_for

    def has_position(self, symbol: str) -> bool:
        pos = self._positions.get(symbol)
        return pos is not None and pos.amount > 0

    def get_position(self, symbol: str) -> Optional[_StubPosition]:
        return self._positions.get(symbol)

    def get_position_size(self, symbol: str):
        return self._position_sizes.get(symbol)

    def get_scaling_rule(self, symbol: str):
        return self._scaling_rules.get(symbol)

    def get_stop_loss_rule(self, symbol: str):
        return self._stop_losses.get(symbol)

    def get_take_profit_rule(self, symbol: str):
        return self._take_profits.get(symbol)


def _make_state(strategy: _StubStrategy, context: _StubContext) -> PhaseState:
    return PhaseState(
        strategy=strategy,
        context=context,
        data={},
        current_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# --------------------------------------------------------------------- #
# CollectSignalsPhase
# --------------------------------------------------------------------- #
class TestCollectSignalsPhase(TestCase):

    def test_ticks_cooldown_and_advances_bar_index(self):
        strategy = _StubStrategy(symbols=["BTC", "ETH"])
        strategy._cooldown_remaining = {"BTC": 2, "ETH": 1}
        state = _make_state(strategy, _StubContext())

        CollectSignalsPhase().run(state)

        self.assertEqual(state.bar_index, 1)
        self.assertEqual(strategy._cooldown_remaining, {"BTC": 1})
        # second tick removes BTC too
        CollectSignalsPhase().run(state)
        self.assertEqual(state.bar_index, 2)
        self.assertEqual(strategy._cooldown_remaining, {})

    def test_collects_signals_from_strategy(self):
        sig = Signal("BTC", SignalSide.OPEN_LONG, 0.7, "ema")
        strategy = _StubStrategy(symbols=["BTC"], generated_signals=[sig])
        state = _make_state(strategy, _StubContext())
        CollectSignalsPhase().run(state)
        self.assertEqual(state.raw_signals, [sig])

    def test_rejects_non_signal_emission(self):
        strategy = _StubStrategy(symbols=["BTC"])
        strategy._generated = ["not a signal"]  # type: ignore[list-item]
        state = _make_state(strategy, _StubContext())
        with self.assertRaises(TypeError):
            CollectSignalsPhase().run(state)

    def test_merges_pipeline_to_signals_with_strategy_signals(self):
        from investing_algorithm_framework.domain.pipeline.pipeline import (
            Pipeline,
        )
        from investing_algorithm_framework.domain.pipeline.factors.builtin \
            import SMA

        class _SignalingPipe(Pipeline):
            sma = SMA(window=2)

            def to_signals(self, frame, context):
                yield Signal("ETH", SignalSide.OPEN_LONG, 0.5, "pipe")

        user_sig = Signal("BTC", SignalSide.OPEN_LONG, 0.7, "ema")
        strategy = _StubStrategy(
            symbols=["BTC", "ETH"], generated_signals=[user_sig],
        )
        strategy.pipelines = [_SignalingPipe]
        state = _make_state(strategy, _StubContext())
        state.data[_SignalingPipe.__name__] = object()  # any non-None frame

        CollectSignalsPhase().run(state)

        # User signal first, pipeline signal appended after.
        self.assertEqual(len(state.raw_signals), 2)
        self.assertEqual(state.raw_signals[0].source, "ema")
        self.assertEqual(state.raw_signals[1].source, "pipe")
        self.assertEqual(state.raw_signals[1].symbol, "ETH")

    def test_pipeline_with_missing_frame_is_skipped(self):
        from investing_algorithm_framework.domain.pipeline.pipeline import (
            Pipeline,
        )
        from investing_algorithm_framework.domain.pipeline.factors.builtin \
            import SMA

        class _PipeNoFrame(Pipeline):
            sma = SMA(window=2)

            def to_signals(self, frame, context):  # pragma: no cover
                yield Signal("ETH", SignalSide.OPEN_LONG, 1.0, "pipe")

        strategy = _StubStrategy(symbols=["BTC"], generated_signals=[])
        strategy.pipelines = [_PipeNoFrame]
        state = _make_state(strategy, _StubContext())
        # state.data has no entry for _PipeNoFrame.__name__

        CollectSignalsPhase().run(state)
        self.assertEqual(state.raw_signals, [])


# --------------------------------------------------------------------- #
# ResolveConflictsPhase
# --------------------------------------------------------------------- #
class TestResolveConflictsPhase(TestCase):

    def _resolve(self, strategy, context, signals):
        state = _make_state(strategy, context)
        state.raw_signals = signals
        state.bar_index = 1
        ResolveConflictsPhase().run(state)
        return state.approved_signals

    def test_open_long_dropped_when_open_order_pending(self):
        strategy = _StubStrategy(
            symbols=["BTC"], open_orders_for=["BTC"],
        )
        out = self._resolve(
            strategy, _StubContext(),
            [Signal("BTC", SignalSide.OPEN_LONG)],
        )
        self.assertEqual(out, [])

    def test_open_long_dropped_when_position_already_held(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            positions={"BTC": _StubPosition(amount=1.0, cost=100.0)},
        )
        out = self._resolve(
            strategy, _StubContext(),
            [Signal("BTC", SignalSide.OPEN_LONG)],
        )
        self.assertEqual(out, [])

    def test_close_long_requires_open_position(self):
        strategy = _StubStrategy(symbols=["BTC"])
        out = self._resolve(
            strategy, _StubContext(),
            [Signal("BTC", SignalSide.CLOSE_LONG)],
        )
        self.assertEqual(out, [])

    def test_close_short_requires_open_short_trade(self):
        strategy = _StubStrategy(symbols=["BTC"])
        out = self._resolve(
            strategy, _StubContext(),
            [Signal("BTC", SignalSide.CLOSE_SHORT)],
        )
        self.assertEqual(out, [])

        # With an open short trade visible via context, it passes.
        ctx = _StubContext(
            open_trades={"BTC": [_StubTrade(2.0, is_short=True)]},
        )
        out = self._resolve(
            strategy, ctx, [Signal("BTC", SignalSide.CLOSE_SHORT)],
        )
        self.assertEqual([s.side for s in out], [SignalSide.CLOSE_SHORT])

    def test_scaling_cooldown_blocks_only_open_sides(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            positions={"BTC": _StubPosition(amount=1.0, cost=100.0)},
            scaling_rules={"BTC": _StubScalingRule()},
        )
        strategy._cooldown_remaining = {"BTC": 2}
        # SCALE_IN is cooldown-blocked.
        out = self._resolve(
            strategy, _StubContext(),
            [Signal("BTC", SignalSide.SCALE_IN)],
        )
        self.assertEqual(out, [])
        # CLOSE_LONG passes — exits are never cooldown-blocked.
        out = self._resolve(
            strategy, _StubContext(),
            [Signal("BTC", SignalSide.CLOSE_LONG)],
        )
        self.assertEqual([s.side for s in out], [SignalSide.CLOSE_LONG])

    def test_direction_conflict_raises_by_default(self):
        strategy = _StubStrategy(symbols=["BTC"])
        with self.assertRaises(OperationalException):
            self._resolve(
                strategy, _StubContext(),
                [
                    Signal("BTC", SignalSide.OPEN_LONG),
                    Signal("BTC", SignalSide.OPEN_SHORT),
                ],
            )

    def test_priority_resolution_keeps_close(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            positions={"BTC": _StubPosition(amount=1.0, cost=100.0)},
            conflict_policy=ConflictPolicy.default().evolve(
                on_conflict=ConflictResolution.PRIORITY,
            ),
        )
        # CLOSE_LONG outranks SCALE_IN.
        out = self._resolve(
            strategy, _StubContext(),
            [
                Signal("BTC", SignalSide.SCALE_IN),
                Signal("BTC", SignalSide.CLOSE_LONG),
            ],
        )
        # SCALE_IN gated out (no scaling_rule), CLOSE_LONG survives.
        self.assertEqual([s.side for s in out], [SignalSide.CLOSE_LONG])


# --------------------------------------------------------------------- #
# SizePositionsPhase
# --------------------------------------------------------------------- #
class TestSizePositionsPhase(TestCase):

    def _size(self, strategy, context, signals):
        state = _make_state(strategy, context)
        state.approved_signals = signals
        SizePositionsPhase().run(state)
        return state.sized_intents

    def test_open_long_computes_base_amount(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            position_sizes={"BTC": _StubPositionSize(1_000.0)},
        )
        out = self._size(
            strategy, _StubContext(price=200.0),
            [Signal("BTC", SignalSide.OPEN_LONG)],
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].amount, 5.0)
        self.assertAlmostEqual(out[0].quote_amount, 1_000.0)
        self.assertAlmostEqual(out[0].price, 200.0)
        self.assertEqual(out[0].order_reason, "buy_signal")
        self.assertEqual(out[0].full_symbol, "BTC/EUR")

    def test_open_long_without_position_size_raises(self):
        strategy = _StubStrategy(symbols=["BTC"])
        with self.assertRaises(OperationalException):
            self._size(
                strategy, _StubContext(),
                [Signal("BTC", SignalSide.OPEN_LONG)],
            )

    def test_close_long_uses_position_amount(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            positions={"BTC": _StubPosition(amount=3.5, cost=700.0)},
        )
        out = self._size(
            strategy, _StubContext(price=200.0),
            [Signal("BTC", SignalSide.CLOSE_LONG)],
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].amount, 3.5)
        self.assertAlmostEqual(out[0].quote_amount, 700.0)
        self.assertEqual(out[0].order_reason, "sell_signal")

    def test_scale_out_applies_percentage(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            positions={"BTC": _StubPosition(amount=4.0, cost=400.0)},
            scaling_rules={"BTC": _StubScalingRule(scale_out_pct=25.0)},
        )
        out = self._size(
            strategy, _StubContext(price=100.0),
            [Signal("BTC", SignalSide.SCALE_OUT)],
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].amount, 1.0)

    def test_close_short_sums_open_short_available(self):
        strategy = _StubStrategy(symbols=["BTC"])
        ctx = _StubContext(
            price=50.0,
            open_trades={
                "BTC": [
                    _StubTrade(1.0, is_short=True),
                    _StubTrade(2.0, is_short=True),
                    _StubTrade(1.0, is_short=False),  # ignored
                ]
            },
        )
        out = self._size(
            strategy, ctx, [Signal("BTC", SignalSide.CLOSE_SHORT)],
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].amount, 3.0)
        self.assertEqual(out[0].order_reason, "cover_signal")

    def test_open_short_routes_via_position_size(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            position_sizes={"BTC": _StubPositionSize(500.0)},
        )
        out = self._size(
            strategy, _StubContext(price=100.0),
            [Signal("BTC", SignalSide.OPEN_SHORT)],
        )
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].amount, 5.0)
        self.assertEqual(out[0].order_reason, "short_signal")

    def test_top_n_ranking_orders_opens_by_strength(self):
        strategy = _StubStrategy(
            symbols=["A", "B", "C"],
            position_sizes={
                "A": _StubPositionSize(100.0),
                "B": _StubPositionSize(100.0),
                "C": _StubPositionSize(100.0),
            },
        )
        out = self._size(
            strategy, _StubContext(price=10.0),
            [
                Signal("A", SignalSide.OPEN_LONG, strength=0.3),
                Signal("B", SignalSide.OPEN_LONG, strength=0.9),
                Signal("C", SignalSide.OPEN_LONG, strength=0.6),
            ],
        )
        self.assertEqual(
            [it.symbol for it in out], ["B", "C", "A"],
        )

    def test_closes_appear_before_opens_after_ranking(self):
        strategy = _StubStrategy(
            symbols=["A", "B"],
            position_sizes={"B": _StubPositionSize(100.0)},
            positions={"A": _StubPosition(amount=2.0, cost=20.0)},
        )
        out = self._size(
            strategy, _StubContext(price=10.0),
            [
                Signal("B", SignalSide.OPEN_LONG, strength=0.9),
                Signal("A", SignalSide.CLOSE_LONG, strength=0.1),
            ],
        )
        self.assertEqual([it.symbol for it in out], ["A", "B"])


# --------------------------------------------------------------------- #
# ApplyRiskBudgetPhase
# --------------------------------------------------------------------- #
class TestApplyRiskBudgetPhase(TestCase):

    def _make(self, intents, unallocated):
        strategy = _StubStrategy(symbols=["BTC"])
        context = _StubContext(unallocated=unallocated)
        state = _make_state(strategy, context)
        state.sized_intents = intents
        ApplyRiskBudgetPhase().run(state)
        return state.sized_intents

    def _intent(self, symbol, side, amount, price):
        return SizedIntent(
            signal=Signal(symbol, side),
            amount=amount,
            price=price,
            quote_amount=amount * price,
            full_symbol=f"{symbol}/EUR",
            order_reason="buy_signal",
        )

    def test_no_scaling_when_under_budget(self):
        intents = [self._intent("BTC", SignalSide.OPEN_LONG, 1.0, 100.0)]
        out = self._make(intents, unallocated=200.0)
        self.assertAlmostEqual(out[0].quote_amount, 100.0)

    def test_proportional_scaling_when_over_budget(self):
        intents = [
            self._intent("BTC", SignalSide.OPEN_LONG, 1.0, 100.0),
            self._intent("ETH", SignalSide.OPEN_LONG, 1.0, 300.0),
        ]
        out = self._make(intents, unallocated=200.0)
        total = sum(it.quote_amount for it in out)
        self.assertAlmostEqual(total, 200.0)
        # Original ratio (1:3) is preserved.
        self.assertAlmostEqual(out[0].quote_amount / out[1].quote_amount,
                               100.0 / 300.0, places=4)

    def test_closing_intents_not_scaled(self):
        intents = [
            self._intent("BTC", SignalSide.OPEN_LONG, 1.0, 100.0),
            self._intent("ETH", SignalSide.CLOSE_LONG, 5.0, 100.0),
        ]
        out = self._make(intents, unallocated=50.0)
        # Close intent unchanged; open scaled down.
        close = next(i for i in out if i.side is SignalSide.CLOSE_LONG)
        opener = next(i for i in out if i.side is SignalSide.OPEN_LONG)
        self.assertAlmostEqual(close.quote_amount, 500.0)
        self.assertAlmostEqual(opener.quote_amount, 50.0)

    def test_dust_intents_dropped_after_scaling(self):
        # Tiny intent + big intent — when scaled the tiny becomes dust.
        intents = [
            self._intent("BTC", SignalSide.OPEN_LONG, 0.0001, 100.0),  # 0.01
            self._intent("ETH", SignalSide.OPEN_LONG, 100.0, 100.0),   # 10000
        ]
        out = self._make(intents, unallocated=10.0)
        # Only the big one survives (after scaling).
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].symbol, "ETH")


# --------------------------------------------------------------------- #
# EmitOrdersPhase
# --------------------------------------------------------------------- #
class TestEmitOrdersPhase(TestCase):

    def _emit(self, intents):
        strategy = _StubStrategy(symbols=["BTC"])
        context = _StubContext()
        state = _make_state(strategy, context)
        state.sized_intents = intents
        EmitOrdersPhase().run(state)
        return state.emitted_orders, context.created_orders

    def _intent(self, side, *, symbol="BTC", amount=1.0, price=100.0):
        return SizedIntent(
            signal=Signal(symbol, side, source="ema"),
            amount=amount,
            price=price,
            quote_amount=amount * price,
            full_symbol=f"{symbol}/EUR",
            order_reason=f"{side.value}",
        )

    def test_open_long_routes_to_limit_buy(self):
        emitted, raw = self._emit(
            [self._intent(SignalSide.OPEN_LONG)],
        )
        self.assertEqual(len(emitted), 1)
        self.assertEqual(raw[0]["__route__"], "limit")
        self.assertEqual(raw[0]["order_side"].value, "BUY")
        self.assertEqual(raw[0]["metadata"]["order_reason"], "open_long")
        self.assertEqual(raw[0]["metadata"]["signal_source"], "ema")

    def test_open_short_routes_via_create_short_order(self):
        emitted, raw = self._emit(
            [self._intent(SignalSide.OPEN_SHORT)],
        )
        self.assertEqual(len(emitted), 1)
        self.assertEqual(raw[0]["__route__"], "short")

    def test_close_short_routes_via_create_cover_order(self):
        emitted, raw = self._emit(
            [self._intent(SignalSide.CLOSE_SHORT)],
        )
        self.assertEqual(len(emitted), 1)
        self.assertEqual(raw[0]["__route__"], "cover")


# --------------------------------------------------------------------- #
# AttachRiskRulesPhase
# --------------------------------------------------------------------- #
class TestAttachRiskRulesPhase(TestCase):

    def test_attaches_sl_tp_to_open_orders_only(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            stop_losses={"BTC": _StubStopLossRule(2.0)},
            take_profits={"BTC": _StubTakeProfitRule(5.0)},
        )
        context = _StubContext()
        state = _make_state(strategy, context)
        # One open and one close intent emitted.
        open_intent = SizedIntent(
            signal=Signal("BTC", SignalSide.OPEN_LONG),
            amount=1.0, price=100.0, quote_amount=100.0,
            full_symbol="BTC/EUR", order_reason="open_long",
        )
        close_intent = SizedIntent(
            signal=Signal("BTC", SignalSide.CLOSE_LONG),
            amount=1.0, price=100.0, quote_amount=100.0,
            full_symbol="BTC/EUR", order_reason="close_long",
        )
        state.emitted_orders = [
            EmittedOrder(intent=open_intent, order=MagicMock()),
            EmittedOrder(intent=close_intent, order=MagicMock()),
        ]
        AttachRiskRulesPhase().run(state)
        self.assertEqual(len(context.attached_stop_losses), 1)
        self.assertEqual(len(context.attached_take_profits), 1)
        # Only the open order got the rules.
        self.assertIs(
            context.attached_stop_losses[0]["order"],
            state.emitted_orders[0].order,
        )

    def test_skips_when_no_rule_defined(self):
        strategy = _StubStrategy(symbols=["BTC"])
        context = _StubContext()
        state = _make_state(strategy, context)
        intent = SizedIntent(
            signal=Signal("BTC", SignalSide.OPEN_SHORT),
            amount=1.0, price=100.0, quote_amount=100.0,
            full_symbol="BTC/EUR", order_reason="open_short",
        )
        state.emitted_orders = [
            EmittedOrder(intent=intent, order=MagicMock()),
        ]
        AttachRiskRulesPhase().run(state)
        self.assertEqual(context.attached_stop_losses, [])
        self.assertEqual(context.attached_take_profits, [])


# --------------------------------------------------------------------- #
# RecordCooldownPhase
# --------------------------------------------------------------------- #
class TestRecordCooldownPhase(TestCase):

    def _record(self, strategy, sides):
        context = _StubContext()
        state = _make_state(strategy, context)
        state.bar_index = 1
        state.emitted_orders = [
            EmittedOrder(
                intent=SizedIntent(
                    signal=Signal("BTC", side),
                    amount=1.0, price=100.0, quote_amount=100.0,
                    full_symbol="BTC/EUR", order_reason=side.value,
                ),
                order=MagicMock(),
            )
            for side in sides
        ]
        RecordCooldownPhase().run(state)
        return state

    def test_scale_out_increments_counter(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            scaling_rules={"BTC": _StubScalingRule(cooldown_in_bars=2)},
        )
        self._record(strategy, [SignalSide.SCALE_OUT])
        self.assertEqual(strategy._scale_out_counts["BTC"], 1)
        self.assertEqual(strategy._cooldown_remaining["BTC"], 2)

    def test_close_long_resets_scale_out_counter(self):
        strategy = _StubStrategy(
            symbols=["BTC"],
            scaling_rules={"BTC": _StubScalingRule()},
        )
        strategy._scale_out_counts["BTC"] = 3
        self._record(strategy, [SignalSide.CLOSE_LONG])
        self.assertNotIn("BTC", strategy._scale_out_counts)

    def test_cooldown_tracker_records_event(self):
        strategy = _StubStrategy(symbols=["BTC"])
        self._record(strategy, [SignalSide.OPEN_LONG])
        # Tracker keyed by (None, ANY) and (symbol, BUY) and so on.
        # Use the public API: a CooldownRule with bars>0 on the same
        # side should report blocked on the very next bar_index.
        from investing_algorithm_framework.domain.models.risk_rules import (
            CooldownRule, CooldownTrigger,
        )
        rule = CooldownRule(
            symbol="BTC",
            bars=2,
            trigger=CooldownTrigger.BUY,
            blocks="buy",
        )
        blocked, _ = strategy._cooldown_tracker.is_blocked(
            [rule], signal_side="buy", symbol="BTC", bar_index=1,
        )
        self.assertTrue(blocked)
