"""Helpers for converting vectorised indicator columns into
:class:`Signal` streams.

The v9.0 strategy API is built around
:py:meth:`TradingStrategy.generate_signals` returning an iterable of
:class:`Signal` objects. Most existing strategies compute boolean
"entry" / "exit" columns on a DataFrame with pandas or polars and
then check the latest row. :func:`signals_from_column` and
:func:`signals_from_panel` are the canonical bridges between that
indicator code and the new signal API.

These helpers are the *only* place in the framework that knows how
to read "the latest row" of a DataFrame. Strategies that use them
do not need to touch ``.iloc[-1]`` or ``.tail(1)`` themselves.
"""
from __future__ import annotations

from typing import Any, Iterator, Mapping, Optional, Union

from .signal import Signal, SignalSide
from .signal_series import SignalSeries

# Type alias for any DataFrame-ish object with an ``iloc[-1]`` or
# ``tail(1)`` accessor. Pandas and polars both qualify; we duck-type
# rather than import either, so the framework keeps its optional-deps
# story intact.
_FrameLike = Any


def _latest_truthy(frame: _FrameLike, column: str) -> tuple[bool, float]:
    """Return ``(is_truthy, value)`` for the last row of ``frame[column]``.

    Works on both pandas and polars frames. Returns
    ``(False, 0.0)`` if the frame is empty, the column is missing,
    or the value is null. The numeric ``value`` is returned so
    callers can route it into ``Signal.strength`` when the column
    is a continuous score rather than a boolean.
    """
    if frame is None:
        return False, 0.0

    # pandas path
    if hasattr(frame, "iloc"):
        try:
            if len(frame) == 0:
                return False, 0.0
        except TypeError:
            return False, 0.0
        if column not in getattr(frame, "columns", []):
            return False, 0.0
        value = frame[column].iloc[-1]
        # Treat NaN / None as falsy.
        try:
            import math

            if isinstance(value, float) and math.isnan(value):
                return False, 0.0
        except Exception:  # pragma: no cover - defensive
            pass
        return bool(value), float(value) if value is not None else 0.0

    # polars path — DataFrame exposes ``.columns`` and ``.row``.
    if hasattr(frame, "row") and hasattr(frame, "columns"):
        try:
            if frame.height == 0:
                return False, 0.0
        except AttributeError:
            return False, 0.0
        if column not in frame.columns:
            return False, 0.0
        # polars: last value of a column.
        try:
            value = frame[column][-1]
        except Exception:  # pragma: no cover - defensive
            return False, 0.0
        if value is None:
            return False, 0.0
        try:
            import math

            if isinstance(value, float) and math.isnan(value):
                return False, 0.0
        except Exception:  # pragma: no cover
            pass
        return bool(value), float(value) if value is not None else 0.0

    raise TypeError(
        f"Unsupported frame type for signals_from_column: "
        f"{type(frame).__name__}. Expected a pandas.DataFrame or "
        f"polars.DataFrame."
    )


def signals_from_column(
    frame: _FrameLike,
    column: str,
    *,
    side: Union[SignalSide, str],
    symbol: str,
    source: str = "",
    strength: Optional[float] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Iterator[Signal]:
    """Yield a single :class:`Signal` if ``frame[column]`` is truthy
    on the latest row.

    This is the canonical bridge between vectorised indicator code
    and the v9.0 :class:`Signal` API. A pandas/polars DataFrame
    carries the indicator series; this helper inspects its last row
    and emits at most one signal.

    Args:
        frame: A pandas or polars DataFrame containing ``column``.
            If the frame is empty, the column is missing, or the
            latest value is null/NaN, no signal is emitted.
        column: Name of the column to read. Treated as truthy
            unless ``strength`` is provided (in which case the
            column is read as a numeric score).
        side: The :class:`SignalSide` to emit. Accepts the enum or
            its string value (``"open_long"``).
        symbol: The symbol the emitted :class:`Signal` should
            reference.
        source: Free-form tag identifying the originator of the
            signal. Common values: rule name, factor name,
            ``"ema_cross"``, ``"rsi_oversold"``.
        strength: Optional override for :pyattr:`Signal.strength`.
            When ``None`` (default) the strength is ``1.0`` if the
            column is truthy. When set explicitly, the value is
            used directly (must be in ``[0, 1]``).
        metadata: Optional metadata to attach to the emitted signal.

    Yields:
        Zero or one :class:`Signal`. The function is a generator so
        it composes cleanly with :py:meth:`itertools.chain` inside
        :py:meth:`TradingStrategy.generate_signals`.

    Examples:
        Long-only EMA crossover::

            def generate_signals(self, context, data):
                df = data["BTC/EUR_1d"]
                df["entry"] = df["ema_fast"] > df["ema_slow"]
                df["exit"]  = df["ema_fast"] < df["ema_slow"]
                yield from signals_from_column(
                    df, "entry", side=SignalSide.OPEN_LONG,
                    symbol="BTC", source="ema_cross",
                )
                yield from signals_from_column(
                    df, "exit", side=SignalSide.CLOSE_LONG,
                    symbol="BTC", source="ema_cross",
                )

        With a continuous score as strength::

            yield from signals_from_column(
                df, "momentum_score", side=SignalSide.OPEN_LONG,
                symbol="BTC", strength=df["momentum_score"].iloc[-1],
            )
    """
    is_truthy, value = _latest_truthy(frame, column)
    if not is_truthy:
        return

    if strength is None:
        emit_strength = 1.0
    else:
        emit_strength = float(strength)

    yield Signal(
        symbol=symbol,
        side=SignalSide.from_value(side),
        strength=emit_strength,
        source=source,
        metadata=dict(metadata) if metadata else {},
    )


def signals_from_panel(
    panel: Mapping[str, _FrameLike],
    column: str,
    *,
    side: Union[SignalSide, str],
    source: str = "",
    strength_column: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Iterator[Signal]:
    """Yield one :class:`Signal` per symbol in a per-symbol DataFrame
    panel where the latest row of ``column`` is truthy.

    The complement to :func:`signals_from_column` for strategies
    that hold a ``Mapping[symbol, DataFrame]`` — typical of
    cross-sectional strategies. Each frame is inspected the same
    way; an optional ``strength_column`` lets the caller drive
    :pyattr:`Signal.strength` from a numeric score column on the
    same frame (e.g. a momentum factor used for top-N ranking).

    Args:
        panel: Mapping from symbol to per-symbol DataFrame.
        column: Boolean column to inspect on each frame's last row.
        side: The :class:`SignalSide` to emit for matches.
        source: Free-form originator tag.
        strength_column: If set, read the strength from this
            column on the same row instead of using ``1.0``.
        metadata: Optional metadata attached to every emitted
            signal.

    Yields:
        One :class:`Signal` per symbol whose ``column`` is truthy
        on the latest row.

    Examples:
        Cross-sectional momentum entry, ranked by score::

            scores = {sym: build_factor_frame(df) for sym, df in panel.items()}
            yield from signals_from_panel(
                scores, "is_top_decile",
                side=SignalSide.OPEN_LONG,
                strength_column="momentum_zscore",
                source="xs_momentum",
            )
    """
    side_enum = SignalSide.from_value(side)
    for symbol, frame in panel.items():
        is_truthy, _ = _latest_truthy(frame, column)
        if not is_truthy:
            continue

        if strength_column is not None:
            _, raw = _latest_truthy(frame, strength_column)
            # Clamp to [0, 1] so user-provided z-scores don't
            # violate Signal's invariant.
            emit_strength = max(0.0, min(1.0, float(raw)))
        else:
            emit_strength = 1.0

        yield Signal(
            symbol=symbol,
            side=side_enum,
            strength=emit_strength,
            source=source,
            metadata=dict(metadata) if metadata else {},
        )


def signal_series_from_column(
    frame: _FrameLike,
    column: str,
    *,
    side: Union[SignalSide, str],
    symbol: str,
    source: str = "",
    strength_column: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> SignalSeries:
    """Build a :class:`SignalSeries` from a boolean column on a frame.

    The vector-mode counterpart to :func:`signals_from_column`.
    Where :func:`signals_from_column` peeks at the latest row and
    yields zero-or-one :class:`Signal`, this helper packages the
    *entire* boolean column into a single :class:`SignalSeries`
    bound for the vector backtest engine.

    Args:
        frame: A pandas or polars DataFrame containing ``column``.
        column: Name of the boolean column to lift into the
            series. The dtype need not be strict ``bool``; any
            truthy value triggers the corresponding side on that
            bar.
        side: The :class:`SignalSide` to emit. Accepts the enum or
            its string value.
        symbol: The symbol the emitted :class:`SignalSeries` should
            reference.
        source: Free-form originator tag (rule name, factor name).
        strength_column: Optional name of a numeric column on the
            same frame to attach as :pyattr:`SignalSeries.strength_series`.
            Useful for ranking-aware sizing in cross-sectional
            vector strategies.
        metadata: Optional metadata attached to the emitted series.

    Returns:
        A :class:`SignalSeries` with ``series`` set to the named
        column (pandas Series for pandas frames, polars Series for
        polars frames). The returned series shares the frame's
        index — no copy is made.

    Raises:
        TypeError: If ``frame`` is neither a pandas nor a polars
            DataFrame.
        KeyError: If ``column`` (or ``strength_column``) does not
            exist on the frame.

    Examples:
        >>> # pandas frame with an 'entry' boolean column
        >>> ss = signal_series_from_column(
        ...     df, "entry",
        ...     side=SignalSide.OPEN_LONG, symbol="BTC",
        ...     source="ema_cross",
        ... )
    """
    if frame is None:
        raise ValueError(
            "signal_series_from_column requires a non-None frame"
        )

    # pandas path
    if hasattr(frame, "iloc"):
        if column not in getattr(frame, "columns", []):
            raise KeyError(
                f"Column {column!r} not found on pandas frame"
            )
        series = frame[column]
        strength_series = None
        if strength_column is not None:
            if strength_column not in frame.columns:
                raise KeyError(
                    f"Strength column {strength_column!r} not found"
                )
            strength_series = frame[strength_column]
    # polars path
    elif hasattr(frame, "columns") and hasattr(frame, "row"):
        if column not in frame.columns:
            raise KeyError(
                f"Column {column!r} not found on polars frame"
            )
        series = frame[column]
        strength_series = None
        if strength_column is not None:
            if strength_column not in frame.columns:
                raise KeyError(
                    f"Strength column {strength_column!r} not found"
                )
            strength_series = frame[strength_column]
    else:
        raise TypeError(
            f"Unsupported frame type for signal_series_from_column: "
            f"{type(frame).__name__}. Expected pandas.DataFrame or "
            f"polars.DataFrame."
        )

    return SignalSeries(
        symbol=symbol,
        side=SignalSide.from_value(side),
        series=series,
        strength_series=strength_series,
        source=source,
        metadata=dict(metadata) if metadata else {},
    )
