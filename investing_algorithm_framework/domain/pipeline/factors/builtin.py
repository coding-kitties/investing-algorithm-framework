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
from typing import List

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


class AverageDollarVolume(Factor):
    """Mean of ``close * volume`` over the trailing ``window`` bars."""

    inputs: List[str] = ["close", "volume"]

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        return panel.with_columns(
            (pl.col("close") * pl.col("volume"))
            .rolling_mean(window_size=self.window)
            .over("symbol")
            .alias("__adv__")
        )["__adv__"]


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
