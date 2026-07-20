"""Vector-mode signal bundle for the v9.0 strategy API.

Where :class:`Signal` is a single-bar intent emitted by
:py:meth:`TradingStrategy.generate_signals` and consumed by the
event-driven phase pipeline, :class:`SignalSeries` is the *batched*
equivalent consumed by the vectorised backtest engine
(:class:`VectorBacktestService`).

A strategy that wants to be vector-backtested overrides
:py:meth:`TradingStrategy.generate_signal_series` and yields one
:class:`SignalSeries` per (symbol, side) pair, each carrying a
boolean pandas/polars Series indexed by timestamp. The vector
engine then walks the master timeline once and reads each side's
flag per bar — no Python-level per-bar callbacks required.

Both surfaces are first-class in v9.0; event strategies use
:class:`Signal`, vector-mode strategies use :class:`SignalSeries`,
and the framework provides
:func:`signal_series_from_column` as a thin bridge from a
DataFrame column to a :class:`SignalSeries`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .signal import SignalSide


@dataclass(frozen=True)
class SignalSeries:
    """A boolean time-series intent emitted by a vector-mode strategy.

    A :class:`SignalSeries` is the batched counterpart to
    :class:`Signal`: instead of asserting "fire ``side`` on
    ``symbol`` now", it asserts "fire ``side`` on ``symbol`` on
    every timestamp where ``series`` is truthy". The vector
    backtest engine consumes a stream of these to drive its
    per-bar state machine.

    Attributes:
        symbol: Target symbol of the signal (e.g. ``"BTC"``).
        side: The directional intent. See :class:`SignalSide`.
        series: A boolean Series (pandas or polars) indexed by
            timestamp. Truthy values trigger the corresponding
            side on that bar.
        strength_series: Optional per-bar strength override in
            ``[0.0, 1.0]``. When provided, used by ranking-aware
            sizing in cross-sectional vector engines. When
            ``None`` (default), strength is implicitly ``1.0`` on
            every truthy bar.
        source: Free-form tag identifying the originator of the
            signal (rule name, factor name, ``"ema_cross"``, ...).
        metadata: Arbitrary JSON-serialisable extra context. Copied
            verbatim onto every order created from this series.

    Examples:
        >>> from investing_algorithm_framework import (
        ...     SignalSeries, SignalSide
        ... )
        >>> import pandas as pd
        >>> entry = pd.Series(
        ...     [False, True, False],
        ...     index=pd.date_range("2024-01-01", periods=3),
        ... )
        >>> SignalSeries(
        ...     symbol="BTC",
        ...     side=SignalSide.OPEN_LONG,
        ...     series=entry,
        ...     source="ema_cross",
        ... )  # doctest: +ELLIPSIS
        SignalSeries(symbol='BTC', side=open_long, ...)
    """

    symbol: str
    side: SignalSide
    series: Any
    strength_series: Any = None
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(
                f"SignalSeries.symbol must be a non-empty str, "
                f"got {self.symbol!r}"
            )
        if not isinstance(self.side, SignalSide):
            object.__setattr__(
                self, "side", SignalSide.from_value(self.side)
            )
        if self.series is None:
            raise ValueError(
                "SignalSeries.series must be a pandas or polars Series, "
                "got None"
            )

    def __repr__(self) -> str:  # pragma: no cover - trivial
        src = f" source={self.source!r}" if self.source else ""
        try:
            n = len(self.series)
        except TypeError:
            n = "?"
        return (
            f"SignalSeries(symbol={self.symbol!r}, side={self.side.value}, "
            f"len={n}{src})"
        )
