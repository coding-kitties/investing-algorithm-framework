"""Shared mutable state passed through the phase pipeline (v9.0).

A :class:`PhaseState` is constructed once per
:py:meth:`TradingStrategy.run_strategy` call. Each phase mutates a
specific slice of it; downstream phases read what upstream phases
wrote. The state object is the **only** way phases communicate —
phases never call into each other directly.

Phase ordering convention (default pipeline):

- CollectSignalsPhase: reads ``strategy`` / ``context`` / ``data``;
    writes ``raw_signals`` and ``bar_index``.
- ResolveConflictsPhase: reads ``raw_signals``; writes
    ``approved_signals``.
- SizePositionsPhase: reads ``approved_signals``; writes
    ``sized_intents``.
- ApplyRiskBudgetPhase: reads ``sized_intents``; writes
    ``sized_intents``.
- EmitOrdersPhase: reads ``sized_intents``; writes ``emitted_orders``.
- AttachRiskRulesPhase: reads ``emitted_orders``; has side effects.
- RecordCooldownPhase: reads ``emitted_orders``; mutates tracker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Tuple

from investing_algorithm_framework.domain import PositionMode
from investing_algorithm_framework.domain.models.signal import (
    Signal,
    SignalSide,
)

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from investing_algorithm_framework.app.context import Context
    from investing_algorithm_framework.app.strategy import TradingStrategy
    from investing_algorithm_framework.domain.models.order import Order


@dataclass
class SizedIntent:
    """A :class:`Signal` paired with the concrete execution
    parameters chosen by :class:`SizePositionsPhase`.

    Attributes:
        signal: The original :class:`Signal` that produced this
            intent. Preserved for traceability into
            :pyattr:`emitted_orders`.
        amount: The base-currency amount the executor should send
            (``order_amount`` in legacy code — pre-divided by price).
        price: Limit price the executor should use. The default
            :class:`LimitOrderExecutor` uses this directly; alternative
            executors (market, TWAP) may treat it as a reference.
        quote_amount: The quote-currency notional (``amount * price``).
            Carried alongside ``amount`` so
            :class:`ApplyRiskBudgetPhase` can scale by notional
            without re-multiplying.
        full_symbol: The ``"BTC/EUR"``-style symbol the executor
            needs. Cached here so :class:`EmitOrdersPhase` does not
            have to re-call :py:meth:`Context.get_trading_symbol`.
        order_reason: Free-form tag written to ``Order.metadata``,
            mirroring today's ``metadata={"order_reason": ...}``.
        extra_metadata: Additional metadata to merge into the
            emitted order's metadata.
    """

    signal: Signal
    amount: float
    price: float
    quote_amount: float
    full_symbol: str
    order_reason: str
    extra_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def side(self) -> SignalSide:
        return self.signal.side

    def scaled(self, factor: float) -> "SizedIntent":
        """Return a new intent with ``amount`` and ``quote_amount``
        multiplied by ``factor``. Used by
        :class:`ApplyRiskBudgetPhase`."""
        return SizedIntent(
            signal=self.signal,
            amount=self.amount * factor,
            price=self.price,
            quote_amount=self.quote_amount * factor,
            full_symbol=self.full_symbol,
            order_reason=self.order_reason,
            extra_metadata=dict(self.extra_metadata),
        )


@dataclass
class EmittedOrder:
    """Pairing of a :class:`SizedIntent` with the :class:`Order` it
    produced. :class:`AttachRiskRulesPhase` and
    :class:`RecordCooldownPhase` consume this list."""

    intent: SizedIntent
    order: "Order"

    @property
    def symbol(self) -> str:
        return self.intent.symbol

    @property
    def side(self) -> SignalSide:
        return self.intent.side


@dataclass
class PhaseState:
    """The shared scratchpad threaded through one execution of the
    phase pipeline.

    Constructed at the top of
    :py:meth:`TradingStrategy.run_strategy` and discarded when the
    pipeline returns. Phases may add to :pyattr:`traces` for
    debugging / explain output but should otherwise stick to the
    typed slots below.
    """

    # ---- inputs (set once at construction) ------------------------ #
    strategy: "TradingStrategy"
    context: "Context"
    data: Dict[str, Any]
    current_datetime: datetime

    # ---- mutated by CollectSignalsPhase --------------------------- #
    bar_index: int = 0
    raw_signals: List[Signal] = field(default_factory=list)

    # ---- mutated by ResolveConflictsPhase ------------------------- #
    approved_signals: List[Signal] = field(default_factory=list)

    # ---- mutated by SizePositionsPhase / ApplyRiskBudgetPhase ----- #
    sized_intents: List[SizedIntent] = field(default_factory=list)

    # ---- mutated by EmitOrdersPhase ------------------------------- #
    emitted_orders: List[EmittedOrder] = field(default_factory=list)

    # ---- optional explain / trace output -------------------------- #
    traces: List[Tuple[str, Any]] = field(default_factory=list)

    # ---- convenience accessors ------------------------------------ #
    @property
    def position_mode(self) -> PositionMode:
        try:
            portfolio = self.context.get_portfolio()
            configuration = (
                self.context.portfolio_configuration_service
                .resolve_for_portfolio(portfolio)
            )
        except (AttributeError, IndexError):
            configuration = None
        if configuration is None:
            return PositionMode.NETTING
        position_mode = getattr(configuration, "position_mode", None)
        if not isinstance(position_mode, (PositionMode, str)):
            return PositionMode.NETTING
        return PositionMode(position_mode)

    def symbols_with_emitted_orders(self) -> List[str]:
        """Return the deduplicated list of symbols that had at least
        one order emitted this iteration."""
        seen: List[str] = []
        for eo in self.emitted_orders:
            if eo.symbol not in seen:
                seen.append(eo.symbol)
        return seen

    def emitted_for(self, symbol: str) -> List[EmittedOrder]:
        """Return all emitted orders for one symbol."""
        return [eo for eo in self.emitted_orders if eo.symbol == symbol]

    def trace(self, tag: str, payload: Any) -> None:
        """Append a ``(tag, payload)`` entry to :pyattr:`traces`.
        Phases use this for explain/debug output without polluting
        regular logs."""
        self.traces.append((tag, payload))
