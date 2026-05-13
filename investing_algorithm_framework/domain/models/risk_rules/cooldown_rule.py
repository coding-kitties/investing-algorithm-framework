"""CooldownRule — first-class signal-throttling rule.

A :class:`CooldownRule` lets a strategy declare that, after a triggering
order has been placed, certain *new* signals must be suppressed for a
fixed number of bars. It is the symmetric, side-aware sibling of
:attr:`ScalingRule.cooldown_in_bars`: the latter only models a single
symbol-scoped, both-sides cooldown that is restarted by *any* order.

Examples
--------
Block buys on ``BTC`` for 12 bars after closing a ``BTC`` trade::

    CooldownRule(symbol="BTC", trigger="sell", blocks="buy", bars=12)

Throttle the whole portfolio after any order::

    CooldownRule(trigger="any", blocks="any", bars=4)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class CooldownTrigger(str, Enum):
    """The kind of order that *starts* a cooldown period."""

    BUY = "buy"
    SELL = "sell"
    ANY = "any"

    @classmethod
    def coerce(cls, value: "str | CooldownTrigger") -> "CooldownTrigger":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(
                f"Invalid CooldownTrigger {value!r}; "
                f"expected one of {[m.value for m in cls]}"
            ) from exc


class CooldownBlocks(str, Enum):
    """The signal side that the cooldown *suppresses*."""

    BUY = "buy"
    SELL = "sell"
    ANY = "any"

    @classmethod
    def coerce(cls, value: "str | CooldownBlocks") -> "CooldownBlocks":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(
                f"Invalid CooldownBlocks {value!r}; "
                f"expected one of {[m.value for m in cls]}"
            ) from exc

    def matches(self, side: "str | CooldownBlocks") -> bool:
        """Return ``True`` if this rule's ``blocks`` covers ``side``."""
        side = CooldownBlocks.coerce(side)
        if self is CooldownBlocks.ANY:
            return True
        return self is side


class CooldownRule:
    """Declarative cooldown gate for a strategy.

    Args:
        symbol: Symbol the rule applies to (e.g. ``"BTC"``). When
            ``None`` the rule is *portfolio-scoped* — any qualifying
            order on any symbol restarts the cooldown, and any
            qualifying signal on any symbol is suppressed.
        trigger: Which order side restarts the cooldown timer
            (``"buy" | "sell" | "any"``). Defaults to ``"any"``.
        blocks: Which signal side this cooldown suppresses
            (``"buy" | "sell" | "any"``). Defaults to ``"any"``.
        bars: Number of bars the cooldown lasts. Must be ``>= 0``.
            ``0`` is a valid no-op (useful for tests / disabled rules).

    Notes:
        Both ``trigger`` and ``blocks`` accept the string forms shown
        above as well as :class:`CooldownTrigger` / :class:`CooldownBlocks`
        members.

        The semantics intentionally mirror
        :attr:`ScalingRule.cooldown_in_bars`: the bar on which the order
        is placed *is* the start of the cooldown, so a rule with
        ``bars=3`` blocks the next 3 bars and allows the 4th.
    """

    def __init__(
        self,
        *,
        symbol: Optional[str] = None,
        trigger: "str | CooldownTrigger" = CooldownTrigger.ANY,
        blocks: "str | CooldownBlocks" = CooldownBlocks.ANY,
        bars: int = 0,
    ) -> None:
        if bars < 0:
            raise ValueError(
                f"CooldownRule.bars must be >= 0, got {bars}"
            )
        self.symbol: Optional[str] = symbol
        self.trigger: CooldownTrigger = CooldownTrigger.coerce(trigger)
        self.blocks: CooldownBlocks = CooldownBlocks.coerce(blocks)
        self.bars: int = int(bars)

    @property
    def is_portfolio_scoped(self) -> bool:
        """``True`` when ``symbol is None``."""
        return self.symbol is None

    def applies_to_symbol(self, symbol: str) -> bool:
        """Whether this rule's *scope* covers ``symbol``."""
        return self.is_portfolio_scoped or self.symbol == symbol

    def trigger_matches(self, order_side: str) -> bool:
        """Whether an order with ``order_side`` restarts this rule."""
        side = CooldownTrigger.coerce(order_side)
        if self.trigger is CooldownTrigger.ANY:
            return True
        return self.trigger is side

    def blocks_signal(self, signal_side: str) -> bool:
        """Whether this rule suppresses signals of ``signal_side``."""
        return self.blocks.matches(signal_side)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        scope = self.symbol if self.symbol is not None else "<portfolio>"
        return (
            f"CooldownRule(symbol={scope!r}, "
            f"trigger={self.trigger.value!r}, "
            f"blocks={self.blocks.value!r}, bars={self.bars})"
        )


class CooldownTracker:
    """Runtime helper that decides whether a signal is in cooldown.

    The tracker keeps the bar index of the most recent qualifying order
    per ``(scope, trigger)`` and exposes two methods:

    * :meth:`record` — called by the engine after an order fills.
    * :meth:`is_blocked` — called by the engine before placing an order
      from a strategy signal.

    The tracker is intentionally engine-agnostic: it uses *bar indices*
    (monotonic integers) so it works identically in the vector backtest
    loop and in event-based / live runs (which can pass a counter that
    increments once per ``run_strategy`` call).
    """

    def __init__(self) -> None:
        # key: (scope_symbol_or_None, CooldownTrigger) -> bar_index
        self._last_event: dict[
            tuple[Optional[str], CooldownTrigger], int
        ] = {}

    def reset(self) -> None:
        """Forget all recorded events (used between backtest runs)."""
        self._last_event.clear()

    def record(
        self,
        *,
        symbol: str,
        order_side: "str | CooldownTrigger",
        bar_index: int,
    ) -> None:
        """Record that an order fired on ``symbol`` at ``bar_index``."""
        side = CooldownTrigger.coerce(order_side)
        # Index this event under both the symbol-scoped key and the
        # portfolio-scoped (``None``) key so both kinds of rules can
        # find it.
        for scope in (symbol, None):
            for trig in (side, CooldownTrigger.ANY):
                prev = self._last_event.get((scope, trig))
                if prev is None or prev < bar_index:
                    self._last_event[(scope, trig)] = bar_index

    def is_blocked(
        self,
        rules: "list[CooldownRule]",
        *,
        signal_side: str,
        symbol: str,
        bar_index: int,
    ) -> "tuple[bool, Optional[CooldownRule]]":
        """Return ``(blocked, vetoing_rule)`` for the given signal."""
        for rule in rules or ():
            if rule.bars <= 0:
                continue
            if not rule.applies_to_symbol(symbol):
                continue
            if not rule.blocks_signal(signal_side):
                continue
            scope = None if rule.is_portfolio_scoped else symbol
            last = self._last_event.get((scope, rule.trigger))
            if last is None:
                continue
            # The trigger bar counts as bar 0 of the cooldown, so the
            # rule blocks bars (last, last + bars] — i.e. the next
            # ``bars`` bars after the order.
            if bar_index - last < rule.bars:
                return True, rule
        return False, None
