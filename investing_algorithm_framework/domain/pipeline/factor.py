"""Factor base class and operator stubs for the Pipeline API.

A ``Factor`` represents a per-symbol time-series computation evaluated
on a long-form OHLCV panel. Phase 1 supports a small surface area:

- ``Factor.compute_panel(panel)`` — produces a ``pl.Series`` aligned with
  ``panel`` rows.
- ``Factor.rank(mask=...)`` — cross-sectional rank within each timestamp.
- ``Factor.top(n)`` / ``Factor.bottom(n)`` — boolean filters.

Arithmetic operators, ``zscore``, ``demean`` and other surface area
described in ``docs/design/pipeline-api.md`` are intentionally deferred
to a follow-up issue (Phase 1 polish).
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:  # pragma: no cover - avoid runtime cycle
    from .filter import Filter


class Factor:
    """Base class for all factor expressions.

    Subclasses must override :meth:`compute_panel` and may override
    :attr:`inputs` (the OHLCV columns required) and :attr:`window`.
    """

    inputs: List[str] = ["close"]
    window: int = 1

    def __init__(self, window: Optional[int] = None) -> None:
        if window is not None:
            self.window = window
        if self.window is None or self.window < 1:
            raise ValueError(
                f"{type(self).__name__}.window must be a positive integer, "
                f"got {self.window!r}"
            )

    # ------------------------------------------------------------------ #
    # Required-data introspection
    # ------------------------------------------------------------------ #
    def required_columns(self) -> List[str]:
        """Return the OHLCV columns this factor needs."""
        return list(self.inputs)

    def required_window(self) -> int:
        """Return the lookback (number of bars) this factor needs."""
        return int(self.window)

    # ------------------------------------------------------------------ #
    # Computation
    # ------------------------------------------------------------------ #
    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        """Compute factor values over a long-form OHLCV panel.

        ``panel`` is a ``pl.DataFrame`` with columns ``datetime``,
        ``symbol`` and lower-cased OHLCV columns. The returned ``Series``
        must be aligned with ``panel`` (same length, same row order).
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Cross-sectional ops (Phase 1 surface)
    # ------------------------------------------------------------------ #
    def rank(self, mask: Optional["Filter"] = None) -> "Factor":
        """Cross-sectional rank within each timestamp.

        Returns a new ``Factor`` whose values are integer ranks in
        ``[1, N]`` where ``N`` is the number of symbols in the mask
        (or in the universe if no mask is given) for that bar.
        Symbols outside the mask receive ``NaN``.
        """
        return _Rank(self, mask=mask)

    def top(self, n: int) -> "Filter":
        """Boolean filter: keep the top-``n`` symbols per bar by this
        factor's value."""
        from .filter import _TopN
        return _TopN(self, n)

    def bottom(self, n: int) -> "Filter":
        """Boolean filter: keep the bottom-``n`` symbols per bar by this
        factor's value."""
        from .filter import _BottomN
        return _BottomN(self, n)

    # ------------------------------------------------------------------ #
    # Repr
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{type(self).__name__}(window={self.window})"


class _Rank(Factor):
    """Internal ranked-factor wrapper produced by :meth:`Factor.rank`."""

    def __init__(self, base: Factor, mask: Optional["Filter"] = None) -> None:
        # window/inputs come from the underlying factor; mask may add more
        super().__init__(window=base.required_window())
        self._base = base
        self._mask = mask
        self.inputs = list(base.required_columns())
        if mask is not None:
            for col in mask.required_columns():
                if col not in self.inputs:
                    self.inputs.append(col)
            self.window = max(self.window, mask.required_window())

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        values = self._base.compute_panel(panel)
        df = panel.select(["datetime", "symbol"]).with_columns(
            values.alias("__rank_input__")
        )
        if self._mask is not None:
            mask_values = self._mask.compute_panel(panel)
            df = df.with_columns(
                pl.when(mask_values)
                .then(pl.col("__rank_input__"))
                .otherwise(None)
                .alias("__rank_input__")
            )
        ranked = df.with_columns(
            pl.col("__rank_input__")
            .rank(method="ordinal", descending=False)
            .over("datetime")
            .cast(pl.Float64)
            .alias("__rank__")
        )
        # When mask filtered everything to null in a bar, rank should be null
        ranked = ranked.with_columns(
            pl.when(pl.col("__rank_input__").is_null())
            .then(None)
            .otherwise(pl.col("__rank__"))
            .alias("__rank__")
        )
        return ranked["__rank__"]
