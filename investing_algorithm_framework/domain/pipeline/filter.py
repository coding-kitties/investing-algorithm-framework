"""Filter base class for the Pipeline API.

A ``Filter`` is a ``Factor`` whose values are boolean. It is used as a
mask in cross-sectional ops (``Factor.rank(mask=...)``) and as a
universe selector inside a ``Pipeline``.
"""
from __future__ import annotations

from typing import List

import polars as pl

from .factor import Factor


class Filter(Factor):
    """Base class for boolean filters.

    Subclasses must override :meth:`compute_panel` and return a
    boolean ``pl.Series``.
    """

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        raise NotImplementedError


class _TopN(Filter):
    """Internal filter produced by :meth:`Factor.top`.

    Selects the top-``n`` symbols per bar by the underlying factor's
    value (largest first; ties broken by symbol name for determinism).
    """

    def __init__(self, base: Factor, n: int) -> None:
        super().__init__(window=base.required_window())
        if n < 1:
            raise ValueError(f"top(n) requires n >= 1, got {n}")
        self._base = base
        self._n = int(n)
        self.inputs = list(base.required_columns())

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        values = self._base.compute_panel(panel)
        df = panel.select(["datetime", "symbol"]).with_columns(
            values.alias("__topn_input__")
        )
        # Rank descending so rank 1 = largest. Nulls become null rank.
        ranked = df.with_columns(
            pl.col("__topn_input__")
            .rank(method="ordinal", descending=True)
            .over("datetime")
            .alias("__topn_rank__")
        )
        # Boolean: rank <= n AND value not null
        return (
            (ranked["__topn_rank__"] <= self._n)
            & ranked["__topn_input__"].is_not_null()
        )


class _BottomN(Filter):
    """Internal filter produced by :meth:`Factor.bottom`."""

    def __init__(self, base: Factor, n: int) -> None:
        super().__init__(window=base.required_window())
        if n < 1:
            raise ValueError(f"bottom(n) requires n >= 1, got {n}")
        self._base = base
        self._n = int(n)
        self.inputs = list(base.required_columns())

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        values = self._base.compute_panel(panel)
        df = panel.select(["datetime", "symbol"]).with_columns(
            values.alias("__bottomn_input__")
        )
        ranked = df.with_columns(
            pl.col("__bottomn_input__")
            .rank(method="ordinal", descending=False)
            .over("datetime")
            .alias("__bottomn_rank__")
        )
        return (
            (ranked["__bottomn_rank__"] <= self._n)
            & ranked["__bottomn_input__"].is_not_null()
        )
