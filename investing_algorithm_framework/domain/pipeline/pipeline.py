"""Pipeline class — declarative cross-sectional factor container.

Subclass :class:`Pipeline` and declare ``Factor`` / ``Filter`` instances
as class attributes. They are introspected at class-creation time and
exposed as columns of the pipeline output.

A class attribute named ``universe`` is treated as the **root mask** —
every other column is computed only on the symbols where the universe
filter is True. The universe column itself is dropped from the output.

Example::

    class MomentumScreener(Pipeline):
        dollar_volume = AverageDollarVolume(window=30)
        momentum = Returns(window=60)

        universe = dollar_volume.top(100)
        alpha = momentum.rank(mask=universe)
"""
from __future__ import annotations

from datetime import timedelta
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
)

from .factor import Factor
from .filter import Filter

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from investing_algorithm_framework.domain.models.signal import Signal

UNIVERSE_ATTR = "universe"


class Pipeline:
    """Base class for pipelines.

    Subclasses declare ``Factor`` / ``Filter`` instances as class
    attributes. The class is introspected at definition time; the
    declared columns are available via :meth:`columns`.
    """

    # Populated by ``__init_subclass__``. Tuple of (name, factor).
    # Excludes the special ``universe`` column.
    __pipeline_columns__: Tuple[Tuple[str, Factor], ...] = ()
    __pipeline_universe__: Optional[Filter] = None

    #: Optional cadence for re-evaluating the universe filter. When
    #: set, the engine caches the surviving symbol set and reuses it
    #: between refreshes — saving the cost of evaluating the (often
    #: expensive) universe filter every bar. Factors are still
    #: recomputed on every iteration. ``None`` (the default)
    #: re-evaluates the universe every bar.
    refresh_universe_every: ClassVar[Optional[timedelta]] = None

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        columns: List[Tuple[str, Factor]] = []
        universe: Optional[Filter] = None

        # Walk MRO so subclasses inherit columns from their parents,
        # with subclass declarations taking precedence.
        seen: set = set()
        for klass in cls.__mro__:
            if klass in (Pipeline, object):
                continue
            for name, value in vars(klass).items():
                if name.startswith("_") or name in seen:
                    continue
                if not isinstance(value, Factor):
                    continue
                seen.add(name)
                if name == UNIVERSE_ATTR:
                    if not isinstance(value, Filter):
                        raise TypeError(
                            f"{cls.__name__}.universe must be a Filter "
                            f"(e.g. AverageDollarVolume(...).top(100)), "
                            f"got {type(value).__name__}"
                        )
                    universe = value
                else:
                    columns.append((name, value))

        if not columns:
            raise TypeError(
                f"Pipeline subclass {cls.__name__} declares no factor "
                f"columns. Add at least one Factor/Filter class attribute."
            )

        # Preserve declaration order (vars() preserves insertion order in
        # Python 3.7+); columns we just collected respect that order
        # within each class.
        cls.__pipeline_columns__ = tuple(columns)
        cls.__pipeline_universe__ = universe

    # ------------------------------------------------------------------ #
    # Public introspection helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def get_columns(cls) -> Dict[str, Factor]:
        """Return a mapping of output column name → ``Factor``.

        Excludes the optional ``universe`` filter column. Named
        ``get_columns`` (not ``columns``) so subclasses are free to
        declare a class attribute literally named ``columns``.
        """
        return dict(cls.__pipeline_columns__)

    @classmethod
    def get_universe(cls) -> Optional[Filter]:
        """Return the universe ``Filter`` declared on this pipeline,
        or ``None`` if the pipeline has no universe restriction.

        Named ``get_universe`` (not ``universe``) so subclasses can
        declare a class attribute literally named ``universe``.
        """
        return cls.__pipeline_universe__

    @classmethod
    def required_columns(cls) -> List[str]:
        """Union of OHLCV columns required by all factors / the
        universe filter."""
        cols: List[str] = []
        for _, factor in cls.__pipeline_columns__:
            for c in factor.required_columns():
                if c not in cols:
                    cols.append(c)
        if cls.__pipeline_universe__ is not None:
            for c in cls.__pipeline_universe__.required_columns():
                if c not in cols:
                    cols.append(c)
        return cols

    @classmethod
    def required_window(cls) -> int:
        """Maximum lookback (bars) required across all columns."""
        windows = [f.required_window() for _, f in cls.__pipeline_columns__]
        if cls.__pipeline_universe__ is not None:
            windows.append(cls.__pipeline_universe__.required_window())
        return max(windows) if windows else 1

    @classmethod
    def name(cls) -> str:
        """Output key used in the strategy's ``data`` dict."""
        return cls.__name__

    # ------------------------------------------------------------------ #
    # v9.0 Signal hook (#503 collapse)
    # ------------------------------------------------------------------ #
    def to_signals(
        self, frame: Any, context: Any
    ) -> Iterable["Signal"]:
        """Optional hook: turn this pipeline's evaluated ``frame``
        into a stream of :class:`Signal` instances.

        Pipelines that override :meth:`to_signals` become first-class
        signal sources: :class:`CollectSignalsPhase` calls this
        method after :class:`EvaluatePipelinesPhase` has materialised
        the pipeline's output frame, and merges the emitted signals
        with whatever ``TradingStrategy.generate_signals`` returns.
        Pure factor pipelines (RSI, SMA, ...) leave the default
        empty implementation in place and remain frame-only.

        Args:
            frame: The pipeline's evaluated long-form ``polars.DataFrame``
                — same object that is also exposed to ``generate_signals``
                under ``data[self.__class__.__name__]``.
            context: The strategy's :class:`Context`. Provided so
                signal-emitting pipelines can read portfolio /
                positions state when deciding what to emit.

        Yields:
            Zero or more :class:`Signal` instances. The default
            implementation yields nothing.

        Examples:
            Top-decile entry pipeline::

                class TopDecileMomentum(Pipeline):
                    momentum = Returns(window=60)
                    universe = AverageDollarVolume(30).top(200)
                    rank = momentum.rank(mask=universe)

                    def to_signals(self, frame, context):
                        from investing_algorithm_framework import (
                            Signal, SignalSide,
                        )
                        top = frame.filter(pl.col("rank") <= 0.1)
                        for row in top.iter_rows(named=True):
                            yield Signal(
                                symbol=row["symbol"],
                                side=SignalSide.OPEN_LONG,
                                strength=float(row["rank"]),
                                source=self.__class__.__name__,
                            )
        """
        return ()
