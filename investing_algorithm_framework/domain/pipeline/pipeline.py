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
from typing import ClassVar, Dict, List, Optional, Tuple

from .factor import Factor
from .filter import Filter

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
