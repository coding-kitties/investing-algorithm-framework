"""SizePositionsPhase — turn approved :class:`Signal`s into concrete
:class:`SizedIntent`s by applying :class:`PositionSize`,
:class:`ScalingRule`, and (optionally) :pyattr:`Signal.strength`
based ranking.

This is where the legacy ``run_strategy`` did its size arithmetic:

* For ``OPEN_LONG`` / ``OPEN_SHORT`` — ``position_size.get_size``
  (quote currency) divided by latest price → base-currency amount.
* For ``SCALE_IN`` — base size multiplied by the per-entry scaling
  percentage, clamped to ``max_position_percentage`` headroom.
* For ``CLOSE_LONG`` — full position amount.
* For ``CLOSE_SHORT`` — sum of ``available_amount`` over open
  short trades.
* For ``SCALE_OUT`` — current position amount * scale-out percentage.

The :pyattr:`Signal.strength` field is consulted for **top-N ranking
within direction** when more opening intents are present than the
risk budget can fund — preserving the highest-conviction signals.
The actual cash scaling is :class:`ApplyRiskBudgetPhase`'s job; this
phase only sorts.
"""
from __future__ import annotations

from typing import List, Optional

from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)
from investing_algorithm_framework.domain.models.signal import (
    Signal,
    SignalSide,
)

from .base import StrategyPhase
from .phase_state import PhaseState, SizedIntent


# Map each :class:`SignalSide` to the ``order_reason`` metadata tag
# emitted in the legacy code. Preserved verbatim so existing
# analytics that key off it keep working.
_ORDER_REASON = {
    SignalSide.OPEN_LONG: "buy_signal",
    SignalSide.SCALE_IN: "scale_in",
    SignalSide.CLOSE_LONG: "sell_signal",
    SignalSide.SCALE_OUT: "scale_out",
    SignalSide.OPEN_SHORT: "short_signal",
    SignalSide.CLOSE_SHORT: "cover_signal",
}


class SizePositionsPhase(StrategyPhase):
    """Phase 3 — size each approved signal."""

    name = "size_positions"

    def run(self, state: PhaseState) -> None:
        if not state.approved_signals:
            state.sized_intents = []
            return

        sized: List[SizedIntent] = []
        for sig in state.approved_signals:
            intent = self._size_one(sig, state)
            if intent is None:
                continue
            sized.append(intent)

        # Top-N ranking within direction: when strength is below 1.0
        # for any opening intent, sort opens descending by strength
        # so :class:`ApplyRiskBudgetPhase` keeps the strongest if
        # capacity binds. Closing intents are never reordered.
        sized = self._rank_by_strength(sized)
        state.sized_intents = sized
        state.trace("size_positions.count", len(sized))

    # ------------------------------------------------------------------
    # Per-side sizing
    # ------------------------------------------------------------------
    def _size_one(
        self, sig: Signal, state: PhaseState,
    ) -> Optional[SizedIntent]:
        symbol = sig.symbol
        full_symbol = (
            f"{symbol}/{state.context.get_trading_symbol()}"
        )
        price = state.context.get_latest_price(full_symbol)
        if price is None or price <= 0:
            state.trace("size_positions.no_price", sig)
            return None

        side = sig.side

        if side is SignalSide.OPEN_LONG:
            return self._size_open(
                sig, state, full_symbol, price, is_short=False,
            )
        if side is SignalSide.OPEN_SHORT:
            return self._size_open(
                sig, state, full_symbol, price, is_short=True,
            )
        if side is SignalSide.SCALE_IN:
            return self._size_scale_in(sig, state, full_symbol, price)
        if side is SignalSide.CLOSE_LONG:
            return self._size_close_long(sig, state, full_symbol, price)
        if side is SignalSide.SCALE_OUT:
            return self._size_scale_out(sig, state, full_symbol, price)
        if side is SignalSide.CLOSE_SHORT:
            return self._size_close_short(sig, state, full_symbol, price)

        # Exhaustive — but keep a defensive None for forward-compat
        # SignalSide additions.
        return None  # pragma: no cover

    # ---- helpers --------------------------------------------------- #
    def _size_open(
        self,
        sig: Signal,
        state: PhaseState,
        full_symbol: str,
        price: float,
        *,
        is_short: bool,
    ) -> SizedIntent:
        strategy = state.strategy
        position_size = strategy.get_position_size(sig.symbol)
        if position_size is None:
            raise OperationalException(
                f"No position size defined for symbol '{sig.symbol}' "
                f"in strategy '{strategy.strategy_id}'. Add a "
                f"PositionSize to ``position_sizes`` covering this "
                f"symbol or override get_position_size()."
            )
        portfolio = state.context.get_portfolio()
        quote_amount = position_size.get_size(portfolio, price)
        amount = quote_amount / price
        return SizedIntent(
            signal=sig,
            amount=amount,
            price=price,
            quote_amount=quote_amount,
            full_symbol=full_symbol,
            order_reason=_ORDER_REASON[sig.side],
        )

    def _size_scale_in(
        self,
        sig: Signal,
        state: PhaseState,
        full_symbol: str,
        price: float,
    ) -> Optional[SizedIntent]:
        strategy = state.strategy
        scaling_rule = strategy.get_scaling_rule(sig.symbol)
        # Already guaranteed non-None by ResolveConflictsPhase, but
        # be defensive.
        if scaling_rule is None:
            return None  # pragma: no cover

        # Determine which entry index this is (0-based across
        # already-open long trades for the symbol).
        open_trades = state.context.get_open_trades(target_symbol=sig.symbol)
        num_entries = len(
            [t for t in open_trades if not getattr(t, "is_short", False)]
        )
        scale_in_index = max(0, num_entries - 1)
        pct = scaling_rule.get_scale_in_percentage(scale_in_index)

        position_size = strategy.get_position_size(sig.symbol)
        if position_size is None:
            raise OperationalException(
                f"No position size defined for symbol '{sig.symbol}' "
                f"in strategy '{strategy.strategy_id}'. Required for "
                f"SCALE_IN sizing."
            )
        portfolio = state.context.get_portfolio()
        base_quote = position_size.get_size(portfolio, price)
        quote_amount = base_quote * (pct / 100.0)

        # Clamp to max_position_percentage headroom.
        if scaling_rule.max_position_percentage is not None:
            net_size = portfolio.get_net_size()
            max_allowed = (
                net_size * scaling_rule.max_position_percentage / 100.0
            )
            position = strategy.get_position(sig.symbol)
            current_cost = position.cost if position else 0
            headroom = max_allowed - current_cost
            if headroom <= 0:
                state.trace("size_positions.scale_in_no_headroom", sig)
                return None
            quote_amount = min(quote_amount, headroom)

        amount = quote_amount / price
        return SizedIntent(
            signal=sig,
            amount=amount,
            price=price,
            quote_amount=quote_amount,
            full_symbol=full_symbol,
            order_reason=_ORDER_REASON[sig.side],
        )

    def _size_close_long(
        self,
        sig: Signal,
        state: PhaseState,
        full_symbol: str,
        price: float,
    ) -> Optional[SizedIntent]:
        position = state.strategy.get_position(sig.symbol)
        if position is None or position.amount <= 0:
            return None
        amount = float(position.amount)
        return SizedIntent(
            signal=sig,
            amount=amount,
            price=price,
            quote_amount=amount * price,
            full_symbol=full_symbol,
            order_reason=_ORDER_REASON[sig.side],
        )

    def _size_scale_out(
        self,
        sig: Signal,
        state: PhaseState,
        full_symbol: str,
        price: float,
    ) -> Optional[SizedIntent]:
        strategy = state.strategy
        scaling_rule = strategy.get_scaling_rule(sig.symbol)
        if scaling_rule is None:
            state.trace("size_positions.no_scaling_rule_scale_out", sig)
            return None
        position = strategy.get_position(sig.symbol)
        if position is None or position.amount <= 0:
            return None
        so_index = strategy._scale_out_counts.get(sig.symbol, 0)
        pct = scaling_rule.get_scale_out_percentage(so_index)
        amount = float(position.amount) * pct / 100.0
        if amount <= 0:
            return None
        return SizedIntent(
            signal=sig,
            amount=amount,
            price=price,
            quote_amount=amount * price,
            full_symbol=full_symbol,
            order_reason=_ORDER_REASON[sig.side],
        )

    def _size_close_short(
        self,
        sig: Signal,
        state: PhaseState,
        full_symbol: str,
        price: float,
    ) -> Optional[SizedIntent]:
        open_shorts = [
            t for t in state.context.get_open_trades(
                target_symbol=sig.symbol
            )
            if getattr(t, "is_short", False)
        ]
        cover_amount = sum(
            (t.available_amount or 0) for t in open_shorts
        )
        if cover_amount <= 0:
            return None
        return SizedIntent(
            signal=sig,
            amount=cover_amount,
            price=price,
            quote_amount=cover_amount * price,
            full_symbol=full_symbol,
            order_reason=_ORDER_REASON[sig.side],
        )

    # ---- top-N ranking -------------------------------------------- #
    @staticmethod
    def _rank_by_strength(intents: List[SizedIntent]) -> List[SizedIntent]:
        """Reorder *opening* intents by descending strength so that
        :class:`ApplyRiskBudgetPhase` keeps the strongest when
        cash binds. Closing intents stay in their resolved-order
        position.

        The current resolve order from :class:`ConflictPolicy.resolve`
        is preserved as a stable secondary key.
        """
        opens: List[SizedIntent] = []
        closes: List[SizedIntent] = []
        for it in intents:
            (opens if it.side.is_open else closes).append(it)
        # Stable sort by descending strength.
        opens.sort(key=lambda i: -i.signal.strength)
        # Closes first (exits never starved), then opens by strength.
        return closes + opens
