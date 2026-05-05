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

from contextvars import ContextVar
from typing import Dict, List, Optional, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:  # pragma: no cover - avoid runtime cycle
    from .filter import Filter


# Per-evaluation memoisation cache (Phase 2 / #502). The pipeline
# engines push a fresh dict here while evaluating a panel; nested
# factors (``_Rank._base``, ``_TopN._base``, …) consult it via
# :meth:`Factor.evaluate` so that a factor instance shared between a
# pipeline column and a universe filter is computed only once.
_EVAL_CACHE: ContextVar[Optional[Dict[tuple, pl.Series]]] = ContextVar(
    "_pipeline_factor_eval_cache", default=None
)


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
    # Cached evaluation (Phase 2 / #502)
    # ------------------------------------------------------------------ #
    def evaluate(self, panel: pl.DataFrame) -> pl.Series:
        """Compute and cache this factor's values on ``panel``.

        Identical to :meth:`compute_panel` when called outside an
        engine context. When a pipeline engine has installed an
        evaluation cache (via the ``_EVAL_CACHE`` context var), the
        result is memoised by ``(id(panel), id(self))`` so that the
        same factor instance reused as both a column and a filter is
        only computed once per panel.
        """
        cache = _EVAL_CACHE.get()
        if cache is None:
            return self.compute_panel(panel)
        key = (id(panel), id(self))
        cached = cache.get(key)
        if cached is not None:
            return cached
        values = self.compute_panel(panel)
        cache[key] = values
        return values

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
    # Cross-sectional transforms (Phase 2 / #502)
    # ------------------------------------------------------------------ #
    def zscore(
        self,
        mask: Optional["Filter"] = None,
        groups=None,
    ) -> "Factor":
        """Cross-sectional z-score within each timestamp.

        Returns ``(x - mean) / std`` computed over the symbols at each
        bar. With ``mask``, symbols outside the mask are excluded from
        the mean/std and receive ``null`` in the output.

        ``groups`` enables **group-relative** (e.g. sector-neutral)
        normalisation: the statistic is computed within each
        ``(datetime, group)`` cell instead of across all symbols. It
        accepts:

        - a ``dict[str, Any]`` mapping ``symbol`` → group label —
          internally wrapped in :class:`StaticPerSymbol`,
        - a :class:`Factor` returning a categorical value per row
          (e.g. a slow-moving fundamental bucket).
        """
        return _Zscore(self, mask=mask, groups=groups)

    def demean(
        self,
        mask: Optional["Filter"] = None,
        groups=None,
    ) -> "Factor":
        """Cross-sectional mean removal within each timestamp.

        Returns ``x - mean(x)`` computed over the symbols at each bar.
        With ``mask``, symbols outside the mask are excluded from the
        mean and receive ``null`` in the output.

        ``groups`` (same shape as in :meth:`zscore`) enables
        group-relative demeaning — e.g. sector neutrality.
        """
        return _Demean(self, mask=mask, groups=groups)

    def winsorize(
        self,
        lower: float = 0.01,
        upper: float = 0.99,
        mask: Optional["Filter"] = None,
    ) -> "Factor":
        """Cross-sectional winsorisation within each timestamp.

        Clips values below the ``lower`` quantile and above the
        ``upper`` quantile (computed per bar). Both bounds are in
        ``[0, 1]`` with ``lower < upper``.
        """
        if not (0.0 <= lower < upper <= 1.0):
            raise ValueError(
                f"winsorize requires 0 <= lower < upper <= 1, "
                f"got lower={lower}, upper={upper}"
            )
        return _Winsorize(self, lower=lower, upper=upper, mask=mask)

    # ------------------------------------------------------------------ #
    # Arithmetic (Phase 2 / #502) — composes Factors into expression trees
    # ------------------------------------------------------------------ #
    def __neg__(self) -> "Factor":
        return _UnaryOp(self, op="neg")

    def __add__(self, other) -> "Factor":
        return _BinaryOp(self, other, op="add")

    def __radd__(self, other) -> "Factor":
        return _BinaryOp(other, self, op="add")

    def __sub__(self, other) -> "Factor":
        return _BinaryOp(self, other, op="sub")

    def __rsub__(self, other) -> "Factor":
        return _BinaryOp(other, self, op="sub")

    def __mul__(self, other) -> "Factor":
        return _BinaryOp(self, other, op="mul")

    def __rmul__(self, other) -> "Factor":
        return _BinaryOp(other, self, op="mul")

    def __truediv__(self, other) -> "Factor":
        return _BinaryOp(self, other, op="div")

    def __rtruediv__(self, other) -> "Factor":
        return _BinaryOp(other, self, op="div")

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
        values = self._base.evaluate(panel)
        df = panel.select(["datetime", "symbol"]).with_columns(
            values.alias("__rank_input__")
        )
        if self._mask is not None:
            mask_values = self._mask.evaluate(panel)
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


# --------------------------------------------------------------------- #
# Phase 2 expression-tree wrappers (#502): arithmetic + cross-sectional
# transforms. Each wrapper composes existing factors into a new factor
# without losing the per-evaluation cache (they call ``evaluate`` on
# their children, not ``compute_panel``).
# --------------------------------------------------------------------- #
def _coerce_operand(operand) -> "Factor":
    """Wrap a scalar operand in a :class:`_Constant` so binary ops
    can treat ``factor + 1`` and ``factor + other_factor`` uniformly.
    """
    if isinstance(operand, Factor):
        return operand
    if isinstance(operand, (int, float)):
        return _Constant(float(operand))
    raise TypeError(
        f"Unsupported operand type for Factor arithmetic: "
        f"{type(operand).__name__}"
    )


def _coerce_groups(groups) -> Optional["Factor"]:
    """Normalise the ``groups`` argument of cross-sectional transforms
    into a :class:`Factor` (or ``None``).

    Accepts ``None``, a ``dict[symbol, group]`` mapping (auto-wrapped
    in :class:`StaticPerSymbol`), or any pre-existing :class:`Factor`.
    """
    if groups is None:
        return None
    if isinstance(groups, Factor):
        return groups
    if isinstance(groups, dict):
        # Local import to avoid an import cycle at module load: the
        # built-in factors module imports from this file.
        from .factors.builtin import StaticPerSymbol
        return StaticPerSymbol(groups)
    raise TypeError(
        f"Unsupported type for `groups`: {type(groups).__name__}. "
        f"Expected None, dict[str, Any], or Factor."
    )


class _Constant(Factor):
    """A panel-aligned constant series. Window is 1 (no warmup needed)."""

    inputs: List[str] = []

    def __init__(self, value: float) -> None:
        super().__init__(window=1)
        self._value = float(value)

    def required_columns(self) -> List[str]:
        return []

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        return pl.Series(
            "__const__", [self._value] * panel.height, dtype=pl.Float64
        )


class _UnaryOp(Factor):
    """Element-wise unary op (currently only ``neg``)."""

    def __init__(self, base: Factor, op: str) -> None:
        super().__init__(window=base.required_window())
        self._base = base
        self._op = op
        self.inputs = list(base.required_columns())

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        values = self._base.evaluate(panel)
        if self._op == "neg":
            return (-values).rename("__unary__")
        raise ValueError(f"Unknown unary op: {self._op}")  # pragma: no cover


class _BinaryOp(Factor):
    """Element-wise binary arithmetic between two ``Factor``s.

    Either operand may be a scalar; it is auto-wrapped in
    :class:`_Constant`.
    """

    def __init__(self, left, right, op: str) -> None:
        left_f = _coerce_operand(left)
        right_f = _coerce_operand(right)
        super().__init__(
            window=max(
                left_f.required_window(), right_f.required_window()
            )
        )
        self._left = left_f
        self._right = right_f
        self._op = op
        cols: List[str] = list(left_f.required_columns())
        for c in right_f.required_columns():
            if c not in cols:
                cols.append(c)
        self.inputs = cols

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        left = self._left.evaluate(panel)
        right = self._right.evaluate(panel)
        if self._op == "add":
            out = left + right
        elif self._op == "sub":
            out = left - right
        elif self._op == "mul":
            out = left * right
        elif self._op == "div":
            # Polars naturally yields nulls when the divisor is null;
            # division by zero produces inf which we leave as-is so
            # callers can decide what to do (e.g. ``zscore`` will
            # propagate inf and downstream filters can drop it).
            out = left / right
        else:
            raise ValueError(  # pragma: no cover
                f"Unknown binary op: {self._op}"
            )
        return out.rename("__binop__")


class _CrossSectionalTransform(Factor):
    """Common base for per-bar transforms (zscore / demean / winsorize).

    Subclasses implement :meth:`_transform_per_bar` which receives a
    Polars expression for the (possibly mask-nulled) factor values and
    returns the transformed expression. The base class handles mask
    application and per-``datetime`` grouping.

    When ``groups`` is provided, statistics are computed within each
    ``(datetime, group)`` cell instead of across all symbols at a
    bar — enabling sector-neutral or otherwise group-relative
    transforms. ``groups`` may be a ``dict[symbol, group]`` (wrapped
    in :class:`StaticPerSymbol` automatically) or any :class:`Factor`
    returning a categorical value per row.
    """

    def __init__(
        self,
        base: Factor,
        mask: Optional["Filter"] = None,
        groups=None,
    ) -> None:
        super().__init__(window=base.required_window())
        self._base = base
        self._mask = mask
        self._groups = _coerce_groups(groups)
        cols = list(base.required_columns())
        if mask is not None:
            for c in mask.required_columns():
                if c not in cols:
                    cols.append(c)
            self.window = max(self.window, mask.required_window())
        if self._groups is not None:
            for c in self._groups.required_columns():
                if c not in cols:
                    cols.append(c)
            self.window = max(self.window, self._groups.required_window())
        self.inputs = cols

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def _transform_expr(self) -> pl.Expr:
        raise NotImplementedError  # pragma: no cover

    def _group_keys(self) -> List[str]:
        """Return the columns to group by for the cross-sectional
        statistic. ``["datetime"]`` for the standard case,
        ``["datetime", "__group__"]`` when ``groups`` is set.
        """
        if self._groups is None:
            return ["datetime"]
        return ["datetime", "__group__"]

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        values = self._base.evaluate(panel)
        df = panel.select(["datetime", "symbol"]).with_columns(
            values.alias("__x__")
        )
        if self._mask is not None:
            mask_values = self._mask.evaluate(panel)
            df = df.with_columns(
                pl.when(mask_values)
                .then(pl.col("__x__"))
                .otherwise(None)
                .alias("__x__")
            )
        if self._groups is not None:
            group_values = self._groups.evaluate(panel)
            df = df.with_columns(group_values.alias("__group__"))
        df = df.with_columns(self._transform_expr().alias("__out__"))
        return df["__out__"]


class _Zscore(_CrossSectionalTransform):
    """Cross-sectional z-score per bar (optionally per group)."""

    def _transform_expr(self) -> pl.Expr:
        x = pl.col("__x__")
        keys = self._group_keys()
        mean = x.mean().over(keys)
        std = x.std().over(keys)
        # If std is 0 or null, returning null is the safe choice (it
        # signals "no dispersion" rather than producing inf/NaN that
        # poisons downstream rolling stats).
        return (
            pl.when((std == 0) | std.is_null())
            .then(None)
            .otherwise((x - mean) / std)
        )


class _Demean(_CrossSectionalTransform):
    """Cross-sectional mean removal per bar (optionally per group)."""

    def _transform_expr(self) -> pl.Expr:
        x = pl.col("__x__")
        keys = self._group_keys()
        return x - x.mean().over(keys)


class _Winsorize(_CrossSectionalTransform):
    """Cross-sectional clip-to-quantiles per bar."""

    def __init__(
        self,
        base: Factor,
        lower: float,
        upper: float,
        mask: Optional["Filter"] = None,
    ) -> None:
        super().__init__(base=base, mask=mask)
        self._lower = float(lower)
        self._upper = float(upper)

    def _transform_expr(self) -> pl.Expr:
        x = pl.col("__x__")
        lo = x.quantile(self._lower).over("datetime")
        hi = x.quantile(self._upper).over("datetime")
        return (
            pl.when(x < lo)
            .then(lo)
            .when(x > hi)
            .then(hi)
            .otherwise(x)
        )
