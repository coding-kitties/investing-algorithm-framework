"""ResolveConflictsPhase — apply :class:`ConflictPolicy` per symbol
and filter against the strategy's runtime state (open orders,
cooldowns, position state).

This phase replaces the cascade of ``if self.has_open_orders``,
``if symbol in self._cooldown_remaining``, and
``self._cooldown_tracker.is_blocked`` guards that the legacy
``run_strategy`` repeated in every Phase 1-5 block.

The order of operations is:

1. **Disabled-side drop** — :pyattr:`ConflictPolicy.disabled_sides`
   sides are removed up-front (cheap, no I/O).
2. **Open-order gate** — when
   :pyattr:`ConflictPolicy.block_when_open_order` is ``True`` (the
   default) every signal for a symbol with a pending order is
   dropped.
3. **State gate** — sides whose preconditions aren't met (e.g.
   ``OPEN_LONG`` while a long position exists,
   ``CLOSE_SHORT`` with no open short trade) are dropped.
4. **Cooldown gate** — cooldown_remaining + CooldownRule via the
   strategy's :class:`CooldownTracker`.
5. **Per-symbol policy arbitration** — :meth:`ConflictPolicy.resolve`
   handles direction mutex + priority/strength tie-breaking.

The surviving signals are written, ordered by priority then
strength desc, to :pyattr:`PhaseState.approved_signals`.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from investing_algorithm_framework.domain.models.signal import (
    Signal,
    SignalSide,
)

from .base import StrategyPhase
from .phase_state import PhaseState


# Side -> tracker side string. CooldownTracker speaks ``"buy"`` /
# ``"sell"``; map signal sides onto those legacy values so existing
# :class:`CooldownRule` definitions keep working unchanged.
_TRACKER_SIDE: Dict[SignalSide, str] = {
    SignalSide.OPEN_LONG: "buy",
    SignalSide.SCALE_IN: "buy",
    SignalSide.OPEN_SHORT: "sell",
    SignalSide.CLOSE_LONG: "sell",
    SignalSide.SCALE_OUT: "sell",
    SignalSide.CLOSE_SHORT: "buy",
}


class ResolveConflictsPhase(StrategyPhase):
    """Phase 2 — apply the strategy's :class:`ConflictPolicy` and
    runtime-state guards."""

    name = "resolve_conflicts"

    def run(self, state: PhaseState) -> None:
        strategy = state.strategy
        policy = strategy.conflict_policy
        if not state.raw_signals:
            state.approved_signals = []
            return

        # Step 1 — drop policy-disabled sides up front.
        candidates = [
            s for s in state.raw_signals
            if not policy.is_disabled(s.side)
        ]
        dropped_disabled = len(state.raw_signals) - len(candidates)
        if dropped_disabled:
            state.trace(
                "resolve_conflicts.dropped_disabled", dropped_disabled,
            )

        # Step 2-4 — per-signal gating (open-order, state, cooldown).
        gated: List[Signal] = []
        for sig in candidates:
            if not self._passes_open_order_gate(sig, state, policy):
                continue
            if not self._passes_state_gate(sig, state):
                continue
            if not self._passes_cooldown_gate(sig, state, policy):
                continue
            gated.append(sig)

        # Step 5 — per-symbol policy arbitration. Group, resolve.
        by_symbol: Dict[str, List[Signal]] = defaultdict(list)
        for sig in gated:
            by_symbol[sig.symbol].append(sig)

        approved: List[Signal] = []
        for symbol, group in by_symbol.items():
            approved.extend(policy.resolve(group, symbol=symbol))

        state.approved_signals = approved
        state.trace("resolve_conflicts.approved", len(approved))

    # ---- gate helpers --------------------------------------------- #
    @staticmethod
    def _passes_open_order_gate(
        sig: Signal,
        state: PhaseState,
        policy,
    ) -> bool:
        if not policy.block_when_open_order:
            return True
        if state.strategy.has_open_orders(sig.symbol):
            state.trace("resolve_conflicts.blocked_open_order", sig)
            return False
        return True

    @staticmethod
    def _passes_state_gate(sig: Signal, state: PhaseState) -> bool:
        """Drop a signal whose precondition on the current
        position/trade state is not met."""
        strategy = state.strategy
        symbol = sig.symbol
        side = sig.side

        has_long_position = strategy.has_position(symbol)
        # Open SHORT trades for the symbol (positive amount, is_short).
        open_short_trades = [
            t for t in state.context.get_open_trades(target_symbol=symbol)
            if getattr(t, "is_short", False)
        ]
        has_open_short = bool(open_short_trades)

        # Opens require a clean slot (no long position, no open short).
        if side in (SignalSide.OPEN_LONG, SignalSide.OPEN_SHORT):
            if has_long_position or has_open_short:
                state.trace("resolve_conflicts.state_block_open", sig)
                return False
            return True

        # SCALE_IN requires an existing long position and a scaling
        # rule with available capacity.
        if side is SignalSide.SCALE_IN:
            if not has_long_position:
                state.trace("resolve_conflicts.state_block_scale_in", sig)
                return False
            scaling_rule = strategy.get_scaling_rule(symbol)
            if scaling_rule is None:
                state.trace(
                    "resolve_conflicts.no_scaling_rule_scale_in", sig,
                )
                return False
            # Cap by max_entries.
            open_trades = state.context.get_open_trades(
                target_symbol=symbol
            )
            num_entries = len([t for t in open_trades
                               if not getattr(t, "is_short", False)])
            if num_entries >= scaling_rule.max_entries:
                state.trace("resolve_conflicts.scale_in_max_entries", sig)
                return False
            # Cap by max_position_percentage.
            if scaling_rule.max_position_percentage is not None:
                pct = (
                    state.context
                    .get_position_percentage_of_portfolio_by_net_size(
                        symbol
                    )
                )
                if pct >= scaling_rule.max_position_percentage:
                    state.trace(
                        "resolve_conflicts.scale_in_max_pct", sig,
                    )
                    return False
            return True

        # SCALE_OUT and CLOSE_LONG require an existing long position.
        if side in (SignalSide.SCALE_OUT, SignalSide.CLOSE_LONG):
            if not has_long_position:
                state.trace("resolve_conflicts.state_block_long_exit", sig)
                return False
            return True

        # CLOSE_SHORT requires an open short trade.
        if side is SignalSide.CLOSE_SHORT:
            if not has_open_short:
                state.trace("resolve_conflicts.state_block_cover", sig)
                return False
            return True

        return True  # pragma: no cover - exhaustive above

    @staticmethod
    def _passes_cooldown_gate(
        sig: Signal,
        state: PhaseState,
        policy,
    ) -> bool:
        strategy = state.strategy
        symbol = sig.symbol
        side = sig.side

        # Per-symbol scaling-rule cooldown (legacy ``_cooldown_remaining``).
        # Applies to sides the policy marks as cooldown-blocked.
        if (
            policy.is_blocked_by_cooldown(side)
            and symbol in strategy._cooldown_remaining
        ):
            state.trace("resolve_conflicts.scaling_cooldown", sig)
            return False

        # CooldownRule via the strategy's CooldownTracker. Tracker
        # speaks "buy"/"sell"; map our side onto that.
        tracker_side = _TRACKER_SIDE.get(side)
        if tracker_side is None:
            return True  # pragma: no cover - exhaustive map
        blocked, vetoing_rule = strategy._cooldown_tracker.is_blocked(
            strategy.cooldowns,
            signal_side=tracker_side,
            symbol=symbol,
            bar_index=state.bar_index,
        )
        if blocked:
            state.trace(
                "resolve_conflicts.cooldown_rule",
                (sig, repr(vetoing_rule)),
            )
            return False
        return True
