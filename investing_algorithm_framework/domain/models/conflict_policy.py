"""Declarative arbitration policy for competing :class:`Signal`s (v9.0).

A :class:`ConflictPolicy` resolves what should happen when a strategy
emits multiple signals for the same symbol in a single iteration —
e.g. an ``OPEN_LONG`` and an ``OPEN_SHORT``, or a ``CLOSE_LONG``
together with a ``SCALE_OUT``.

The policy is consumed by
:class:`investing_algorithm_framework.services.strategy_phases.ResolveConflictsPhase`,
which never bakes priorities into method ordering — every decision is
data-driven by an instance of this class.

See ``docs/architecture/strategy.md`` (Composition model) for the
full design rationale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Iterable, List, Optional, Set, Tuple

from .signal import Signal, SignalSide


class ConflictResolution(Enum):
    """How to resolve **opposing-direction** conflicts on one symbol.

    A *direction conflict* is when at least one long-side signal
    (``OPEN_LONG`` / ``SCALE_IN``) and at least one short-side
    signal (``OPEN_SHORT``) are emitted for the same symbol in the
    same iteration.

    * ``RAISE`` — treat the conflict as a strategy bug and raise
      :class:`OperationalException`. This is the default because
      well-formed strategies should not produce opposing intents in
      the same bar.
    * ``PRIORITY`` — keep the signal whose side ranks earliest in
      :pyattr:`ConflictPolicy.priority`. Use this when your strategy
      legitimately produces opposing votes from independent rule
      sources and you want the framework to break ties by policy.
    * ``STRENGTH`` — keep the signal with the highest
      :pyattr:`Signal.strength`. Ties are broken by
      :pyattr:`ConflictPolicy.priority`.
    """

    RAISE = "raise"
    PRIORITY = "priority"
    STRENGTH = "strength"


# Default priority used by :meth:`ConflictPolicy.default` — exits
# first (so risk reduction never gets starved by a fresh entry),
# then opens, then scaling. Mirrors the implicit ordering of the
# legacy monolithic ``run_strategy`` so the default policy is
# behaviour-compatible.
_DEFAULT_PRIORITY: Tuple[SignalSide, ...] = (
    SignalSide.CLOSE_LONG,
    SignalSide.CLOSE_SHORT,
    SignalSide.SCALE_OUT,
    SignalSide.OPEN_LONG,
    SignalSide.OPEN_SHORT,
    SignalSide.SCALE_IN,
)


# Sides that should be vetoed while the symbol is in a cooldown
# window. Closing sides are *never* blocked by cooldown — a stop /
# exit must always be free to fire.
_DEFAULT_COOLDOWN_BLOCKS: FrozenSet[SignalSide] = frozenset({
    SignalSide.OPEN_LONG,
    SignalSide.OPEN_SHORT,
    SignalSide.SCALE_IN,
    SignalSide.SCALE_OUT,
})


@dataclass(frozen=True)
class ConflictPolicy:
    """Arbitration policy applied per-symbol by
    :class:`ResolveConflictsPhase`.

    Attributes:
        priority: Tuple of :class:`SignalSide` values ordered from
            **highest** to **lowest** priority. When multiple signals
            of compatible direction fire on the same symbol, the
            one whose side appears first wins. Defaults to
            ``CLOSE_LONG → CLOSE_SHORT → SCALE_OUT → OPEN_LONG →
            OPEN_SHORT → SCALE_IN``.
        direction_mutex: When ``True`` (default) at most one of
            long-side / short-side signals can survive per symbol per
            iteration. ``False`` allows e.g. a ``SCALE_OUT`` on the
            long position to coexist with an ``OPEN_SHORT`` (rarely
            useful — exists for advanced pairs/hedging strategies).
        on_conflict: How to resolve opposing-direction conflicts.
            See :class:`ConflictResolution`. Defaults to ``RAISE``.
        cooldown_blocks: Set of sides that are vetoed while the
            symbol is in a cooldown window. Closing sides should
            **never** be in this set (the framework asserts this).
            Defaults to ``{OPEN_LONG, OPEN_SHORT, SCALE_IN,
            SCALE_OUT}``.
        block_when_open_order: When ``True`` (default) all signals
            for a symbol are dropped while that symbol has an
            open (unfilled) order — mirrors today's
            ``if self.has_open_orders(symbol): continue`` guard.

    Examples:
        Default policy (matches legacy ``run_strategy``)::

            policy = ConflictPolicy.default()

        Allow opposing intents and arbitrate by strength::

            policy = ConflictPolicy.default().evolve(
                on_conflict=ConflictResolution.STRENGTH
            )

        Strict long-only — drop every short side at policy time::

            policy = ConflictPolicy.long_only()
    """

    priority: Tuple[SignalSide, ...] = _DEFAULT_PRIORITY
    direction_mutex: bool = True
    on_conflict: ConflictResolution = ConflictResolution.RAISE
    cooldown_blocks: FrozenSet[SignalSide] = _DEFAULT_COOLDOWN_BLOCKS
    block_when_open_order: bool = True
    # Set of sides this policy will *unconditionally* drop, before
    # any other rule runs. Used by :meth:`long_only` / :meth:`short_only`.
    disabled_sides: FrozenSet[SignalSide] = field(
        default_factory=frozenset
    )

    # ---- factory helpers ------------------------------------------- #
    @classmethod
    def default(cls) -> "ConflictPolicy":
        """The default policy — behaviour-compatible with the
        legacy monolithic ``run_strategy``."""
        return cls()

    @classmethod
    def long_only(cls) -> "ConflictPolicy":
        """A policy that drops every short-side signal at policy
        time. Useful for venues / instruments that do not support
        shorting."""
        return cls(
            disabled_sides=frozenset({
                SignalSide.OPEN_SHORT,
                SignalSide.CLOSE_SHORT,
            }),
        )

    @classmethod
    def short_only(cls) -> "ConflictPolicy":
        """A policy that drops every long-side signal at policy time."""
        return cls(
            disabled_sides=frozenset({
                SignalSide.OPEN_LONG,
                SignalSide.CLOSE_LONG,
                SignalSide.SCALE_IN,
                SignalSide.SCALE_OUT,
            }),
        )

    # ---- ergonomic evolution --------------------------------------- #
    def evolve(self, **changes) -> "ConflictPolicy":
        """Return a copy of this policy with the given fields
        replaced. Mirrors :func:`dataclasses.replace` but coerces
        :pyattr:`priority` and :pyattr:`cooldown_blocks` to their
        immutable types for safety."""
        if "priority" in changes:
            changes["priority"] = tuple(changes["priority"])
        if "cooldown_blocks" in changes:
            changes["cooldown_blocks"] = frozenset(
                changes["cooldown_blocks"]
            )
        if "disabled_sides" in changes:
            changes["disabled_sides"] = frozenset(
                changes["disabled_sides"]
            )
        # Manual replace — dataclass is frozen.
        merged = {
            "priority": self.priority,
            "direction_mutex": self.direction_mutex,
            "on_conflict": self.on_conflict,
            "cooldown_blocks": self.cooldown_blocks,
            "block_when_open_order": self.block_when_open_order,
            "disabled_sides": self.disabled_sides,
        }
        merged.update(changes)
        return ConflictPolicy(**merged)

    # ---- arbitration ----------------------------------------------- #
    def priority_rank(self, side: SignalSide) -> int:
        """Return the priority rank of ``side`` (0 = highest).

        Sides not listed in :pyattr:`priority` get a rank of
        ``len(priority)`` — i.e. they sort after every listed side
        but remain comparable, so a custom policy that omits a side
        still produces deterministic ordering.
        """
        try:
            return self.priority.index(side)
        except ValueError:
            return len(self.priority)

    def is_blocked_by_cooldown(self, side: SignalSide) -> bool:
        """Return ``True`` if ``side`` is vetoed while the symbol
        is in cooldown."""
        return side in self.cooldown_blocks

    def is_disabled(self, side: SignalSide) -> bool:
        """Return ``True`` if ``side`` is unconditionally dropped by
        this policy."""
        return side in self.disabled_sides

    def resolve(
        self,
        signals: Iterable[Signal],
        *,
        symbol: Optional[str] = None,
    ) -> List[Signal]:
        """Resolve a collection of signals **for a single symbol**
        into the surviving set after applying this policy.

        Args:
            signals: The candidate signals for one symbol. Caller is
                responsible for grouping by symbol — this method does
                not re-group.
            symbol: Optional symbol name, used purely for error
                messages when ``on_conflict == RAISE``.

        Returns:
            The list of surviving signals, ordered by priority
            rank (highest priority first). May be empty.

        Raises:
            OperationalException: when a direction conflict occurs
                and :pyattr:`on_conflict` is
                :pyattr:`ConflictResolution.RAISE`.
        """
        # Local import to avoid circulars at module load time.
        from investing_algorithm_framework.domain.exceptions import (
            OperationalException,
        )

        candidates = [s for s in signals if not self.is_disabled(s.side)]
        if not candidates:
            return []

        if self.direction_mutex:
            longs = [s for s in candidates if s.side.is_long]
            shorts = [s for s in candidates if s.side.is_short]

            # Direction conflict — opposing intents on the same symbol.
            if longs and shorts:
                if self.on_conflict is ConflictResolution.RAISE:
                    sym = symbol or candidates[0].symbol
                    raise OperationalException(
                        f"Direction conflict on symbol '{sym}': "
                        f"long-side signals "
                        f"{[s.side.value for s in longs]} and "
                        f"short-side signals "
                        f"{[s.side.value for s in shorts]} "
                        f"were emitted in the same iteration. Set "
                        f"ConflictPolicy(on_conflict=ConflictResolution"
                        f".PRIORITY) or .STRENGTH to resolve "
                        f"automatically, or fix the strategy to emit "
                        f"a single direction per bar."
                    )
                elif self.on_conflict is ConflictResolution.PRIORITY:
                    # Pick whichever side group contains the
                    # highest-priority signal.
                    best_long = min(
                        longs, key=lambda s: self.priority_rank(s.side)
                    )
                    best_short = min(
                        shorts, key=lambda s: self.priority_rank(s.side)
                    )
                    if self.priority_rank(best_long.side) <= \
                            self.priority_rank(best_short.side):
                        candidates = longs
                    else:
                        candidates = shorts
                elif self.on_conflict is ConflictResolution.STRENGTH:
                    best_long = max(longs, key=lambda s: s.strength)
                    best_short = max(shorts, key=lambda s: s.strength)
                    if best_long.strength > best_short.strength:
                        candidates = longs
                    elif best_short.strength > best_long.strength:
                        candidates = shorts
                    else:
                        # Strength tie — fall back to priority.
                        if self.priority_rank(best_long.side) <= \
                                self.priority_rank(best_short.side):
                            candidates = longs
                        else:
                            candidates = shorts

        # Within the surviving direction, sort by priority rank then
        # by strength (descending). The phase consumer is free to
        # truncate to the top-1, top-N, or keep all.
        candidates.sort(
            key=lambda s: (self.priority_rank(s.side), -s.strength)
        )
        return candidates

    # ---- introspection --------------------------------------------- #
    def affected_sides(self) -> Set[SignalSide]:
        """Return the set of sides this policy explicitly references
        in :pyattr:`priority`, :pyattr:`cooldown_blocks`, or
        :pyattr:`disabled_sides`. Useful for self-checks in user
        code."""
        out: Set[SignalSide] = set(self.priority)
        out.update(self.cooldown_blocks)
        out.update(self.disabled_sides)
        return out
