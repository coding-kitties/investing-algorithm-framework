"""PipelineEngine — Phase 1 (event-driven backtest).

Given a ``Pipeline`` subclass, a ``data_object`` mapping
``data_source_identifier`` → OHLCV ``DataFrame`` (Polars or Pandas),
and an ``as_of`` timestamp, return a wide ``pl.DataFrame`` with one row
per surviving symbol and one column per pipeline output.

Phase 1 is a straightforward eager implementation. Lazy / cached
variants land in Phase 2 (#502).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Type

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain.pipeline.pipeline import Pipeline


# Long-form panel column names used internally by the engine and by all
# built-in factors. Lower-cased to keep Polars expressions tidy.
PANEL_COLUMNS = (
    "datetime", "symbol", "open", "high", "low", "close", "volume",
)


class PipelineEngine:
    """Eager Polars pipeline engine for event-mode backtests."""

    # ------------------------------------------------------------------ #
    # Panel construction
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_panel(
        data_object: Mapping[str, Any],
        symbol_to_identifier: Mapping[str, str],
        as_of: Optional[datetime] = None,
    ) -> pl.DataFrame:
        """Stack per-symbol OHLCV frames into a long-form panel.

        Args:
            data_object: mapping of data-source identifier → OHLCV
                ``pl.DataFrame`` or ``pd.DataFrame`` with columns
                ``Datetime``, ``Open``, ``High``, ``Low``, ``Close``,
                ``Volume``.
            symbol_to_identifier: mapping of symbol → identifier in
                ``data_object``. The symbol column on the panel is set
                from this mapping (so it is independent of how the data
                source was identified internally).
            as_of: if provided, rows with ``Datetime > as_of`` are
                dropped (look-ahead safety).
        """
        frames = []
        for symbol, identifier in symbol_to_identifier.items():
            raw = data_object.get(identifier)
            if raw is None or len(raw) == 0:
                continue
            df = _to_polars(raw)
            df = df.rename({c: c.lower() for c in df.columns})
            # Make sure all required columns exist
            for col in ("datetime", "open", "high", "low", "close", "volume"):
                if col not in df.columns:
                    raise KeyError(
                        f"Data for {symbol!r} (identifier={identifier!r}) "
                        f"is missing required column {col!r}"
                    )
            df = df.with_columns(pl.lit(symbol).alias("symbol"))
            df = df.select(list(PANEL_COLUMNS))
            if as_of is not None:
                df = df.filter(pl.col("datetime") <= pl.lit(as_of))
            frames.append(df)

        if not frames:
            return pl.DataFrame(
                schema={
                    "datetime": pl.Datetime,
                    "symbol": pl.Utf8,
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "close": pl.Float64,
                    "volume": pl.Float64,
                }
            )

        panel = pl.concat(frames, how="vertical_relaxed")
        # Sort by (symbol, datetime) so rolling/shift over("symbol") is
        # well-defined.
        return panel.sort(["symbol", "datetime"])

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    def evaluate_at(
        self,
        pipeline_cls: Type[Pipeline],
        panel: pl.DataFrame,
        as_of: datetime,
    ) -> pl.DataFrame:
        """Return a wide ``(symbol → factor columns)`` frame for ``as_of``.

        Symbols masked out by the pipeline universe are dropped.
        Symbols with no data at ``as_of`` are dropped (NaN row is
        considered "no data").
        """
        if panel.is_empty():
            return self._empty_output(pipeline_cls)

        result = panel.select(["datetime", "symbol"])
        for name, factor in pipeline_cls.get_columns().items():
            values = factor.compute_panel(panel)
            result = result.with_columns(values.alias(name))

        universe = pipeline_cls.get_universe()
        if universe is not None:
            mask = universe.compute_panel(panel)
            result = result.with_columns(mask.alias("__universe__"))
            result = result.filter(pl.col("__universe__"))
            result = result.drop("__universe__")

        # Slice to as_of bar
        result = result.filter(pl.col("datetime") == pl.lit(as_of))
        # Drop datetime column from final output (one row per symbol)
        return result.drop("datetime")

    def evaluate(
        self,
        pipeline_cls: Type[Pipeline],
        data_object: Mapping[str, Any],
        symbol_to_identifier: Mapping[str, str],
        as_of: datetime,
    ) -> pl.DataFrame:
        """Build the panel and evaluate the pipeline at ``as_of``."""
        panel = self.build_panel(
            data_object=data_object,
            symbol_to_identifier=symbol_to_identifier,
            as_of=as_of,
        )
        return self.evaluate_at(pipeline_cls, panel, as_of)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _empty_output(pipeline_cls: Type[Pipeline]) -> pl.DataFrame:
        schema: Dict[str, Any] = {"symbol": pl.Utf8}
        for name in pipeline_cls.get_columns():
            schema[name] = pl.Float64
        return pl.DataFrame(schema=schema)


def _to_polars(frame: Any) -> pl.DataFrame:
    if isinstance(frame, pl.DataFrame):
        return frame
    if isinstance(frame, pd.DataFrame):
        return pl.from_pandas(frame.reset_index(drop=False))
    raise TypeError(
        f"Unsupported data frame type for pipeline: {type(frame).__name__}"
    )
