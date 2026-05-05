"""Built-in factor implementations for Phase 1.

Each factor consumes a long-form OHLCV panel
(columns: ``datetime``, ``symbol``, ``open``, ``high``, ``low``,
``close``, ``volume``) and returns a ``pl.Series`` aligned with the
panel rows.

Per-symbol rolling computations use ``.over("symbol")`` so symbols are
processed independently within a single Polars expression.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

import numpy as np
import polars as pl

from ..factor import Factor


class Returns(Factor):
    """Simple percent return over the trailing ``window`` bars.

    Formula: ``close[t] / close[t - window] - 1``.
    """

    inputs: List[str] = ["close"]

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        return panel.with_columns(
            (
                pl.col("close")
                / pl.col("close").shift(self.window).over("symbol")
                - 1.0
            ).alias("__returns__")
        )["__returns__"]


class AverageTradedValue(Factor):
    """Mean of ``close * volume`` over the trailing ``window`` bars.

    This is a liquidity proxy expressed in the **quote currency** of
    each symbol — for ``BTC/EUR`` the result is in EUR, for
    ``BTC/USDT`` it is in USDT, etc. The factor itself is
    quote-currency agnostic; ``close`` and ``volume`` come straight
    from the OHLCV panel.

    Also exposed as :class:`AverageDollarVolume`, the more familiar
    Quantopian/Zipline name. The two are interchangeable.
    """

    inputs: List[str] = ["close", "volume"]

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        return panel.with_columns(
            (pl.col("close") * pl.col("volume"))
            .rolling_mean(window_size=self.window)
            .over("symbol")
            .alias("__adv__")
        )["__adv__"]


# Backwards-compatible alias. "Dollar volume" is the standard quant
# shorthand for traded value (price * volume) in whatever quote
# currency the symbols use; the name does not imply USD.
AverageDollarVolume = AverageTradedValue


class SMA(Factor):
    """Simple moving average of ``close`` over ``window`` bars."""

    inputs: List[str] = ["close"]

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        return panel.with_columns(
            pl.col("close")
            .rolling_mean(window_size=self.window)
            .over("symbol")
            .alias("__sma__")
        )["__sma__"]


class RSI(Factor):
    """Wilder's Relative Strength Index over ``window`` bars.

    Uses Wilder's smoothing (EMA with ``alpha = 1 / window``) for the
    average gain and loss series.
    """

    inputs: List[str] = ["close"]

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        n = self.window
        # delta = close - close.shift(1) per symbol
        df = panel.with_columns(
            (pl.col("close") - pl.col("close").shift(1).over("symbol"))
            .alias("__delta__")
        )
        df = df.with_columns(
            pl.when(pl.col("__delta__") > 0)
            .then(pl.col("__delta__"))
            .otherwise(0.0)
            .alias("__gain__"),
            pl.when(pl.col("__delta__") < 0)
            .then(-pl.col("__delta__"))
            .otherwise(0.0)
            .alias("__loss__"),
        )
        # Wilder smoothing: EMA with alpha = 1/n. Polars `ewm_mean`
        # supports `alpha=` directly. Use `over("symbol")` to keep
        # symbols independent.
        alpha = 1.0 / n
        df = df.with_columns(
            pl.col("__gain__")
            .ewm_mean(alpha=alpha, adjust=False, min_samples=n)
            .over("symbol")
            .alias("__avg_gain__"),
            pl.col("__loss__")
            .ewm_mean(alpha=alpha, adjust=False, min_samples=n)
            .over("symbol")
            .alias("__avg_loss__"),
        )
        df = df.with_columns(
            pl.when(pl.col("__avg_loss__") == 0)
            .then(100.0)
            .otherwise(
                100.0
                - 100.0
                / (1.0 + pl.col("__avg_gain__") / pl.col("__avg_loss__"))
            )
            .alias("__rsi__")
        )
        return df["__rsi__"]


class Volatility(Factor):
    """Annualised stdev of log returns over ``window`` bars.

    Args:
        window: lookback in bars.
        periods_per_year: number of bars per year (default 252 for
            daily). Override for non-daily timeframes.
    """

    inputs: List[str] = ["close"]

    def __init__(self, window: int, periods_per_year: int = 252) -> None:
        super().__init__(window=window)
        if periods_per_year < 1:
            raise ValueError("periods_per_year must be >= 1")
        self.periods_per_year = int(periods_per_year)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        scale = math.sqrt(self.periods_per_year)
        df = panel.with_columns(
            (
                pl.col("close").log()
                - pl.col("close").shift(1).over("symbol").log()
            ).alias("__logret__")
        )
        df = df.with_columns(
            (
                pl.col("__logret__")
                .rolling_std(window_size=self.window)
                .over("symbol")
                * scale
            ).alias("__vol__")
        )
        return df["__vol__"]


# --------------------------------------------------------------------- #
# Risk / neutrality primitives (#504)
# --------------------------------------------------------------------- #
class StaticPerSymbol(Factor):
    """Broadcast a static per-symbol mapping to every row of the panel.

    Useful as input to risk / neutrality transforms: sector tags,
    country codes, factor-model exposures from a fundamental snapshot,
    or any per-symbol metadata that doesn't change within a single
    pipeline evaluation.

    Args:
        mapping: ``dict[str, Any]`` keyed by symbol. The value may be
            a string (e.g. sector label), int, float, or bool.
        default: Value emitted for symbols missing from ``mapping``.
            Defaults to ``None`` (which becomes a Polars null).

    Example::

        sectors = StaticPerSymbol({
            "AAPL": "TECH", "MSFT": "TECH",
            "JPM": "FIN",  "BAC":  "FIN",
        })
        neutral = my_alpha.zscore(groups=sectors)
    """

    inputs: List[str] = []

    def __init__(
        self,
        mapping: Dict[str, Any],
        default: Any = None,
    ) -> None:
        super().__init__(window=1)
        if not isinstance(mapping, dict):
            raise TypeError(
                f"StaticPerSymbol expects a dict, "
                f"got {type(mapping).__name__}"
            )
        self._mapping = dict(mapping)
        self._default = default

    def required_columns(self) -> List[str]:
        return []

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        symbols = panel.get_column("symbol").to_list()
        values = [self._mapping.get(s, self._default) for s in symbols]
        return pl.Series("__static__", values)


class CrossSectionalMean(Factor):
    """Equal-weighted cross-sectional mean of ``base`` per bar.

    Returns a panel-aligned series where every row at a given
    ``datetime`` carries the mean of ``base`` across the surviving
    symbols at that bar. Combined with :class:`Returns`, this is the
    standard "equal-weighted market return" used as the market leg in
    :class:`RollingBeta`.

    Args:
        base: Source factor whose values are averaged per bar.
        mask: Optional :class:`Filter` restricting which symbols
            contribute to the mean.
    """

    def __init__(self, base: Factor, mask=None) -> None:
        super().__init__(window=base.required_window())
        self._base = base
        self._mask = mask
        cols = list(base.required_columns())
        if mask is not None:
            for c in mask.required_columns():
                if c not in cols:
                    cols.append(c)
            self.window = max(self.window, mask.required_window())
        self.inputs = cols

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

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
        df = df.with_columns(
            pl.col("__x__").mean().over("datetime").alias("__cs_mean__")
        )
        return df["__cs_mean__"]


class RollingBeta(Factor):
    """Per-symbol rolling time-series beta of ``target`` vs ``market``.

    Computes ``cov(target, market) / var(market)`` over the trailing
    ``window`` bars within each symbol. Both ``target`` and
    ``market`` are :class:`Factor` instances evaluated against the
    same panel.

    A typical setup uses :class:`Returns` for the target and
    ``CrossSectionalMean(Returns(...))`` for the market \u2014 i.e. an
    equal-weighted market return computed from the universe itself.

    Args:
        target: Per-symbol time-series factor (e.g. asset returns).
        market: Per-row market series (typically broadcast across
            symbols within a bar via :class:`CrossSectionalMean`).
        window: Lookback in bars for the rolling cov/var.
    """

    def __init__(
        self, target: Factor, market: Factor, window: int = 60
    ) -> None:
        super().__init__(
            window=max(
                target.required_window(),
                market.required_window(),
                window,
            )
        )
        if window < 2:
            raise ValueError("RollingBeta window must be >= 2")
        self._target = target
        self._market = market
        self._beta_window = int(window)
        cols = list(target.required_columns())
        for c in market.required_columns():
            if c not in cols:
                cols.append(c)
        self.inputs = cols

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        t = self._target.evaluate(panel)
        m = self._market.evaluate(panel)
        df = panel.select(["datetime", "symbol"]).with_columns(
            t.alias("__t__"),
            m.alias("__m__"),
        )
        w = self._beta_window
        df = df.with_columns(
            pl.col("__t__")
            .rolling_mean(window_size=w)
            .over("symbol")
            .alias("__et__"),
            pl.col("__m__")
            .rolling_mean(window_size=w)
            .over("symbol")
            .alias("__em__"),
            (pl.col("__t__") * pl.col("__m__"))
            .rolling_mean(window_size=w)
            .over("symbol")
            .alias("__etm__"),
            (pl.col("__m__") * pl.col("__m__"))
            .rolling_mean(window_size=w)
            .over("symbol")
            .alias("__emm__"),
        )
        df = df.with_columns(
            (pl.col("__etm__") - pl.col("__et__") * pl.col("__em__"))
            .alias("__cov__"),
            (pl.col("__emm__") - pl.col("__em__") * pl.col("__em__"))
            .alias("__var__"),
        )
        df = df.with_columns(
            pl.when(
                (pl.col("__var__") == 0) | pl.col("__var__").is_null()
            )
            .then(None)
            .otherwise(pl.col("__cov__") / pl.col("__var__"))
            .alias("__beta__")
        )
        return df["__beta__"]


class Neutralize(Factor):
    """Cross-sectional OLS residualisation per bar.

    For each ``datetime``, fits ``target ~ exposures`` via ordinary
    least squares across the surviving symbols and returns the
    residuals. Subsumes:

    - **Sector neutrality** \u2014 pass sector dummies as ``exposures``
      (or use the ergonomic :meth:`Factor.demean` / :meth:`zscore`
      with ``groups=...`` for the simple one-sector case).
    - **Beta neutralisation** \u2014 pass an equal-weighted market return
      (e.g. ``CrossSectionalMean(Returns(...))``) as the sole
      exposure.
    - **Multi-factor risk models** \u2014 pass [size, value, momentum,
      sector dummies, \u2026] as ``exposures``.

    Symbols masked out (or rows where any exposure is null) are
    excluded from the OLS fit and receive ``null`` in the output.
    Bars where the design matrix is rank-deficient (e.g. fewer
    surviving symbols than exposures) yield ``null`` for every
    symbol at that bar.

    Args:
        target: The factor to residualise.
        exposures: One or more :class:`Factor` instances forming the
            design matrix.
        mask: Optional :class:`Filter` restricting which symbols
            contribute to the regression.
        add_intercept: If ``True`` (default), prepends a column of
            ones to the design matrix so the residuals are zero-mean
            within each bar.
    """

    def __init__(
        self,
        target: Factor,
        exposures: Sequence[Factor],
        mask=None,
        add_intercept: bool = True,
    ) -> None:
        if not exposures:
            raise ValueError(
                "Neutralize requires at least one exposure factor"
            )
        max_w = target.required_window()
        for e in exposures:
            max_w = max(max_w, e.required_window())
        if mask is not None:
            max_w = max(max_w, mask.required_window())
        super().__init__(window=max_w)
        self._target = target
        self._exposures = list(exposures)
        self._mask = mask
        self._add_intercept = bool(add_intercept)
        cols: List[str] = list(target.required_columns())
        for e in self._exposures:
            for c in e.required_columns():
                if c not in cols:
                    cols.append(c)
        if mask is not None:
            for c in mask.required_columns():
                if c not in cols:
                    cols.append(c)
        self.inputs = cols

    def required_columns(self) -> List[str]:
        return list(self.inputs)

    def required_window(self) -> int:
        return int(self.window)

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        t_arr = self._target.evaluate(panel).to_numpy().astype(float)
        e_arrs = [
            e.evaluate(panel).to_numpy().astype(float)
            for e in self._exposures
        ]
        if self._mask is not None:
            mask_arr = self._mask.evaluate(panel).to_numpy().astype(bool)
        else:
            mask_arr = np.ones(len(t_arr), dtype=bool)
        dt = panel.get_column("datetime").to_numpy()

        # Stack exposures column-wise; optionally prepend an
        # intercept so residuals are zero-mean within each bar.
        X_full = np.column_stack(e_arrs)
        if self._add_intercept:
            X_full = np.column_stack(
                [np.ones(len(t_arr), dtype=float), X_full]
            )

        result = np.full(len(t_arr), np.nan, dtype=float)

        # Group rows by datetime via a single sort + boundary scan \u2014
        # avoids the O(B*N) cost of np.where(inv == g) for every bar.
        order = np.argsort(dt, kind="mergesort")
        dt_sorted = dt[order]
        # Bar boundaries: indices where dt changes.
        change = np.concatenate(
            ([True], dt_sorted[1:] != dt_sorted[:-1])
        )
        starts = np.flatnonzero(change)
        ends = np.append(starts[1:], len(dt_sorted))

        n_exposures_effective = X_full.shape[1]
        for s, e in zip(starts, ends):
            idx = order[s:e]
            valid = (
                mask_arr[idx]
                & ~np.isnan(t_arr[idx])
                & ~np.any(np.isnan(X_full[idx]), axis=1)
            )
            if int(valid.sum()) <= n_exposures_effective:
                # Under-determined / rank-deficient: leave as null.
                continue
            idx_v = idx[valid]
            X_v = X_full[idx_v]
            t_v = t_arr[idx_v]
            try:
                beta, *_ = np.linalg.lstsq(X_v, t_v, rcond=None)
            except np.linalg.LinAlgError:  # pragma: no cover - defensive
                continue
            pred = X_v @ beta
            result[idx_v] = t_v - pred

        # Convert NaN sentinels (rank-deficient bars, masked rows) into
        # Polars nulls so downstream consumers can use ``is_null()``
        # uniformly. ``fill_nan(None)`` is the documented way to do
        # this conversion in Polars.
        return pl.Series(
            "__neutralized__", result, dtype=pl.Float64
        ).fill_nan(None)
