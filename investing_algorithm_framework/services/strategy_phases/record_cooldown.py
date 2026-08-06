"""RecordCooldownPhase — update the strategy's
:class:`CooldownTracker` and per-symbol ``_cooldown_remaining``
counters after orders have been emitted.

Mirrors the post-order bookkeeping that the legacy
``run_strategy`` interleaved with order creation. Also handles
the scale-out counter increment / reset:

* A ``SCALE_OUT`` emission increments
  :pyattr:`TradingStrategy._scale_out_counts`.
* A ``CLOSE_LONG`` (full exit) clears the counter back to zero so
  the next position starts a fresh scale-out ladder.

In addition to ``state.emitted_orders`` (orders the strategy
itself produced this tick), the phase scans for system-emitted
exits — i.e. SELL / COVER orders created by the
:class:`TradeOrderEvaluator` from triggered take-profit or
stop-loss rules — and records them on the
:class:`CooldownTracker` too. Without this, a
``CooldownRule(trigger=SELL, ...)`` would never fire after a TP
or SL fill since those orders bypass the signal pipeline.
"""
from __future__ import annotations

from investing_algorithm_framework.domain.models.signal import SignalSide

from .base import StrategyPhase
from .phase_state import PhaseState


# Same map as :mod:`resolve_conflicts`, kept local to avoid a
# cross-import for one dict.
_TRACKER_SIDE = {
    SignalSide.OPEN_LONG: "buy",
    SignalSide.SCALE_IN: "buy",
    SignalSide.OPEN_SHORT: "sell",
    SignalSide.CLOSE_LONG: "sell",
    SignalSide.SCALE_OUT: "sell",
    SignalSide.CLOSE_SHORT: "buy",
}

# Map raw OrderSide string values to the CooldownTracker's
# ``buy``/``sell`` vocabulary. Used when recording system-emitted
# TP / SL exits whose original SignalSide isn't available.
_ORDER_SIDE_TO_TRACKER = {
    "BUY": "buy",
    "SELL": "sell",
    "SHORT": "sell",
    "COVER": "buy",
}

# Order ``metadata.order_reason`` values produced by the trade
# evaluator for TP / SL fills. Anything else (manual closes,
# scaling-rule exits) is already covered by ``state.emitted_orders``.
_SYSTEM_EXIT_REASONS = ("take_profit", "stop_loss")


class RecordCooldownPhase(StrategyPhase):
    """Phase 7 — update cooldown tracker + scale-out counters."""

    name = "record_cooldown"

    def run(self, state: PhaseState) -> None:
        self._record_system_exits(state)

        if not state.emitted_orders:
            return

        strategy = state.strategy
        bar_index = state.bar_index

        for emitted in state.emitted_orders:
            symbol = emitted.symbol
            side = emitted.side
            tracker_side = _TRACKER_SIDE.get(side)
            if tracker_side is None:
                continue  # pragma: no cover - exhaustive map

            # Record into the CooldownTracker for CooldownRule
            # evaluation on the *next* bar.
            strategy._cooldown_tracker.record(
                symbol=symbol,
                order_side=tracker_side,
                bar_index=bar_index,
            )

            # Per-side bookkeeping.
            scaling_rule = strategy.get_scaling_rule(symbol)
            if side is SignalSide.SCALE_OUT:
                so_index = strategy._scale_out_counts.get(symbol, 0)
                strategy._scale_out_counts[symbol] = so_index + 1
            elif side is SignalSide.CLOSE_LONG:
                # Full exit resets the scale-out ladder.
                strategy._scale_out_counts.pop(symbol, None)

            # Start per-symbol cooldown if the scaling rule asks for it.
            if scaling_rule and scaling_rule.cooldown_in_bars > 0:
                strategy._cooldown_remaining[symbol] = (
                    scaling_rule.cooldown_in_bars
                )

    def _record_system_exits(self, state: PhaseState) -> None:
        """Record TP / SL fills onto the strategy's
        :class:`CooldownTracker` so cooldown rules can react to
        them just like signal-driven exits.

        The :class:`TradeOrderEvaluator` creates SELL / COVER orders
        for triggered TP / SL rules outside the strategy phase
        pipeline, so they never reach :pyattr:`state.emitted_orders`.
        We scan the order service for any such order with
        ``metadata.order_reason in ("take_profit", "stop_loss")``
        created since the strategy's last scan, and call
        :py:meth:`CooldownTracker.record` for each one. The scan is a
        no-op when the strategy declares no cooldown rules — most
        strategies pay nothing for this phase."""
        strategy = state.strategy
        rules = getattr(strategy, "cooldowns", None)
        if not rules:
            return

        context = state.context
        order_service = getattr(context, "order_service", None)
        if order_service is None:
            return

        watermark = strategy._last_system_exit_scan_at
        try:
            orders = order_service.get_all({})
        except Exception:
            return

        # Restrict to symbols any cooldown rule actually cares about.
        # Portfolio-scoped rules (symbol is None) match every symbol.
        rule_symbols = {r.symbol for r in rules if r.symbol is not None}
        match_all = any(r.symbol is None for r in rules)

        latest = watermark
        for order in orders:
            side = (
                order.order_side.upper()
                if isinstance(order.order_side, str)
                else order.order_side.value.upper()
            )
            if side not in ("SELL", "COVER"):
                continue

            metadata = getattr(order, "metadata", None) or {}
            if metadata.get("order_reason") not in _SYSTEM_EXIT_REASONS:
                continue

            created_at = order.created_at
            if created_at is None:
                continue
            if watermark is not None and created_at <= watermark:
                continue

            symbol = order.target_symbol
            if not match_all and symbol not in rule_symbols:
                # Still advance the watermark for unrelated symbols
                # so we don't keep re-scanning them.
                if latest is None or created_at > latest:
                    latest = created_at
                continue

            tracker_side = _ORDER_SIDE_TO_TRACKER.get(side)
            if tracker_side is None:
                continue

            strategy._cooldown_tracker.record(
                symbol=symbol,
                order_side=tracker_side,
                bar_index=state.bar_index,
            )

            if latest is None or created_at > latest:
                latest = created_at

        if latest is not None and latest != watermark:
            strategy._last_system_exit_scan_at = latest
