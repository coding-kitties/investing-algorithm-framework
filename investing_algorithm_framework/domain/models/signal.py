"""Typed signal / intent objects emitted by trading strategies (v9.0).

A :class:`Signal` is a declarative *intent* — "I would like to open a
long position in BTC with strength 0.8 because the EMA-cross fired".
It is **not** an order. The framework's phase pipeline
(see ``services/strategy_phases/``) turns a stream of signals into
orders by applying conflict resolution, position sizing, risk budget,
and execution policy.

Strategies emit signals by overriding
:py:meth:`investing_algorithm_framework.app.strategy.TradingStrategy.generate_signals`,
which returns an :class:`~typing.Iterable` of :class:`Signal` objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .score_card import ScoreCard, SCORE_CARD_METADATA_KEY


class SignalSide(Enum):
    """The directional intent carried by a :class:`Signal`.

    The six values cover every state transition the framework
    supports per symbol:

    * ``OPEN_LONG`` — open a new long position (BUY).
    * ``CLOSE_LONG`` — fully exit an existing long position (SELL).
    * ``SCALE_IN`` — add to an existing long position (BUY).
    * ``SCALE_OUT`` — partially close an existing long position (SELL).
    * ``OPEN_SHORT`` — open a new short position (SELL-to-open).
    * ``CLOSE_SHORT`` — fully exit an existing short position
      (BUY-to-cover, i.e. COVER).

    See ``ConflictPolicy`` for how competing sides on the same
    symbol are arbitrated.
    """

    OPEN_LONG = "open_long"
    CLOSE_LONG = "close_long"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"
    OPEN_SHORT = "open_short"
    CLOSE_SHORT = "close_short"

    @property
    def is_open(self) -> bool:
        """True for sides that *open* or *add to* a position."""
        return self in (
            SignalSide.OPEN_LONG,
            SignalSide.SCALE_IN,
            SignalSide.OPEN_SHORT,
        )

    @property
    def is_close(self) -> bool:
        """True for sides that *close* or *partially close* a position."""
        return self in (
            SignalSide.CLOSE_LONG,
            SignalSide.SCALE_OUT,
            SignalSide.CLOSE_SHORT,
        )

    @property
    def is_long(self) -> bool:
        """True for sides that operate on a long position."""
        return self in (
            SignalSide.OPEN_LONG,
            SignalSide.CLOSE_LONG,
            SignalSide.SCALE_IN,
            SignalSide.SCALE_OUT,
        )

    @property
    def is_short(self) -> bool:
        """True for sides that operate on a short position."""
        return self in (SignalSide.OPEN_SHORT, SignalSide.CLOSE_SHORT)

    @classmethod
    def from_value(cls, value: "SignalSide | str") -> "SignalSide":
        """Coerce a string or :class:`SignalSide` into a :class:`SignalSide`.

        Accepts both the enum value (``"open_long"``) and the enum
        name (``"OPEN_LONG"``).
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                try:
                    return cls[value]
                except KeyError as exc:  # pragma: no cover - rare path
                    raise ValueError(
                        f"Unknown SignalSide: {value!r}"
                    ) from exc
        raise TypeError(
            f"Cannot coerce {type(value).__name__} to SignalSide"
        )


@dataclass(frozen=True)
class Signal:
    """A directional intent emitted by a strategy or pipeline.

    Signals are **immutable**; once emitted they are consumed by the
    phase pipeline. Use :meth:`with_metadata` or :meth:`with_strength`
    to derive a new signal with adjusted attributes.

    Attributes:
        symbol: Target symbol of the signal (e.g. ``"BTC"``). Should
            match the strategy's :pyattr:`symbols` list.
        side: The directional intent. See :class:`SignalSide`.
        strength: A confidence/conviction score in ``[0.0, 1.0]``.
            Used by :class:`SizePositionsPhase` for top-N ranking
            when a risk budget cannot fund every signal at full size.
            Defaults to ``1.0``.
        source: Free-form tag identifying the originator of the
            signal (rule name, pipeline name, factor name, ...). Used
            by the trace/explain machinery to attribute outcomes.
            Defaults to ``""``.
        metadata: Arbitrary, JSON-serialisable extra context. Survives
            into ``Order.metadata`` when the signal is executed.
            Defaults to an empty mapping.

    Examples:
        >>> from investing_algorithm_framework import Signal, SignalSide
        >>> Signal(symbol="BTC", side=SignalSide.OPEN_LONG, strength=0.8)
        Signal(symbol='BTC', side=<SignalSide.OPEN_LONG: 'open_long'>, ...)
    """

    symbol: str
    side: SignalSide
    strength: float = 1.0
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(
                f"Signal.symbol must be a non-empty str, got {self.symbol!r}"
            )
        # Coerce strings to SignalSide for ergonomic construction.
        if not isinstance(self.side, SignalSide):
            object.__setattr__(
                self, "side", SignalSide.from_value(self.side)
            )
        if not (0.0 <= float(self.strength) <= 1.0):
            raise ValueError(
                f"Signal.strength must be in [0.0, 1.0], "
                f"got {self.strength!r}"
            )

    def with_strength(self, strength: float) -> "Signal":
        """
        Return a copy of this signal with a new ``strength``.
        """
        return Signal(
            symbol=self.symbol,
            side=self.side,
            strength=strength,
            source=self.source,
            metadata=dict(self.metadata),
        )

    def with_metadata(self, **extra: Any) -> "Signal":
        """Return a copy of this signal with additional metadata
        merged in. New keys override existing ones."""
        merged = dict(self.metadata)
        merged.update(extra)
        return Signal(
            symbol=self.symbol,
            side=self.side,
            strength=self.strength,
            source=self.source,
            metadata=merged,
        )

    def with_score_card(self, score_card: ScoreCard) -> "Signal":
        """Return a copy of this signal with ``score_card`` attached
        under the reserved ``metadata["score_card"]`` key.

        A :class:`ScoreCard` is a small, versioned, JSON-only object
        that records *why* this signal fired (or, for a rejected
        signal, what its inputs were) — e.g. the indicator values a
        strategy computed before deciding to emit it. Because
        ``Signal.metadata`` already flows into ``Order.metadata`` for
        an executed signal, and every signal (approved or rejected)
        is captured in ``RunReport.signals``, this is enough for any
        external tool to render the reasoning behind a decision
        without strategy-specific code — see
        :class:`~investing_algorithm_framework.domain.models.score_card.ScoreCard`
        for the full design rationale.
        """
        return self.with_metadata(
            **{SCORE_CARD_METADATA_KEY: score_card.to_dict()}
        )

    def __repr__(self) -> str:  # pragma: no cover - trivial
        src = f" source={self.source!r}" if self.source else ""
        return (
            f"Signal(symbol={self.symbol!r}, side={self.side.value}, "
            f"strength={self.strength:.3f}{src})"
        )
