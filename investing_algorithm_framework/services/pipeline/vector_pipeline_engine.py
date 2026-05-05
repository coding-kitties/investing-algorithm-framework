"""VectorPipelineEngine — Phase 2 (#502).

Materialises the full long-form OHLCV panel and every declared factor
**once** over the entire backtest window, instead of rebuilding the
panel on each event-loop iteration. The resulting long frame can then
be sliced per bar by callers (e.g. the vector backtest service).

Compared to :class:`PipelineEngine`:

- ``evaluate_window`` returns the full ``(datetime, symbol, *factors)``
  long frame for every bar in the panel — not just ``as_of``.
- A per-engine factor-result cache keyed by ``id(factor)`` ensures that
  shared sub-expressions (e.g. a ``Returns`` reused inside
  ``Returns(...).rank(mask=universe)``) are computed only once per
  evaluation.

The public Pipeline / Factor / Filter surface from Phase 1 is reused
unchanged. Strategies that work in event mode also work here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Type

import polars as pl

from investing_algorithm_framework.domain.pipeline.factor import _EVAL_CACHE
from investing_algorithm_framework.domain.pipeline.pipeline import Pipeline

from .pipeline_engine import PANEL_COLUMNS, PipelineEngine


class VectorPipelineEngine:
    """Vector-mode pipeline executor (#502).

    Build the panel and evaluate every declared factor over the full
    window in one shot. The output is a long-form
    ``pl.DataFrame`` with columns
    ``(datetime, symbol, <factor_1>, ..., <factor_n>)``, sorted by
    ``(datetime, symbol)``.

    Universe filtering is applied as in event mode — symbols failing
    the universe mask at a given bar are dropped from that bar's
    output, and the universe column itself is not exposed.

    Args:
        lazy: If ``True``, the result frame is assembled via
            :class:`polars.LazyFrame` and collected with the streaming
            engine at the end. Useful for memory-bound runs over large
            universes. Built-in factors are still computed eagerly per
            symbol (each ``Factor.compute_panel`` returns a ``Series``);
            only the ``with_columns`` / ``filter`` / ``sort`` pipeline
            on the wide result frame is deferred. Default ``False``
            preserves Phase 2a behaviour exactly.
    """

    def __init__(self, lazy: bool = False) -> None:
        self._lazy = bool(lazy)

    # ------------------------------------------------------------------ #
    # Panel construction (delegates to event engine for parity)
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_panel(
        data_object: Mapping[str, Any],
        symbol_to_identifier: Mapping[str, str],
        end: Optional[datetime] = None,
    ) -> pl.DataFrame:
        """Stack per-symbol OHLCV frames into a long-form panel.

        ``end`` is an optional inclusive upper bound (no look-ahead).
        There is intentionally no ``start`` parameter here — the panel
        keeps all earlier bars so factors get full warmup. Callers that
        want to restrict the *output* range should pass ``start`` to
        :meth:`evaluate_window` instead.
        """
        return PipelineEngine.build_panel(
            data_object=data_object,
            symbol_to_identifier=symbol_to_identifier,
            as_of=end,
        )

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    def evaluate_window(
        self,
        pipeline_cls: Type[Pipeline],
        data_object: Mapping[str, Any],
        symbol_to_identifier: Mapping[str, str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pl.DataFrame:
        """Evaluate ``pipeline_cls`` over the full window.

        Returns a long-form frame with one row per ``(datetime, symbol)``
        pair that survives the universe mask, plus one column per
        declared pipeline output factor.

        ``end`` truncates the input panel (no look-ahead). ``start``
        only restricts the *output* — earlier bars remain in the panel
        as warmup so rolling factors compute correctly at ``start``.
        """
        panel = self.build_panel(
            data_object=data_object,
            symbol_to_identifier=symbol_to_identifier,
            end=end,
        )
        result = self.evaluate_panel(pipeline_cls, panel)
        if start is not None and not result.is_empty():
            col_tz = result.schema["datetime"].time_zone
            start_cmp = (
                start.replace(tzinfo=None)
                if col_tz is None and start.tzinfo is not None
                else start
            )
            result = result.filter(pl.col("datetime") >= pl.lit(start_cmp))
        return result

    def evaluate_panel(
        self,
        pipeline_cls: Type[Pipeline],
        panel: pl.DataFrame,
    ) -> pl.DataFrame:
        """Evaluate ``pipeline_cls`` over an already-built ``panel``.

        Exposed separately so callers (e.g. the vector backtest service)
        that already maintain a panel can reuse it without paying the
        rebuild cost.
        """
        if panel.is_empty():
            return self._empty_long_output(pipeline_cls)

        cache: Dict[tuple, pl.Series] = {}
        token = _EVAL_CACHE.set(cache)
        try:
            result = panel.select(["datetime", "symbol"])
            for name, factor in pipeline_cls.get_columns().items():
                values = factor.evaluate(panel)
                result = result.with_columns(values.alias(name))

            universe = pipeline_cls.get_universe()
            if universe is not None:
                mask = universe.evaluate(panel)
                result = result.with_columns(mask.alias("__universe__"))
                if self._lazy:
                    # Stream the filter + drop + sort through Polars'
                    # streaming engine so memory usage stays bounded
                    # on large universes.
                    return self._collect_lazy(
                        result.lazy()
                        .filter(pl.col("__universe__"))
                        .drop("__universe__")
                        .sort(["datetime", "symbol"])
                    )
                result = result.filter(pl.col("__universe__"))
                result = result.drop("__universe__")
        finally:
            _EVAL_CACHE.reset(token)

        if self._lazy:
            return self._collect_lazy(
                result.lazy().sort(["datetime", "symbol"])
            )
        return result.sort(["datetime", "symbol"])

    @staticmethod
    def _collect_lazy(lazy: pl.LazyFrame) -> pl.DataFrame:
        """Collect a :class:`polars.LazyFrame` with the streaming
        engine when available; fall back to a default collect on
        older Polars versions that don't accept
        ``engine="streaming"``.
        """
        try:
            return lazy.collect(engine="streaming")
        except TypeError:
            return lazy.collect()
        except Exception:  # pragma: no cover - polars version drift
            return lazy.collect()

    # ------------------------------------------------------------------ #
    # Slicing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def slice_at(long_result: pl.DataFrame, as_of: datetime) -> pl.DataFrame:
        """Return the wide ``(symbol, *factors)`` frame for one bar.

        Equivalent to what :meth:`PipelineEngine.evaluate` returns. The
        ``datetime`` column is dropped so the shape matches event mode.
        """
        if long_result.is_empty():
            return long_result.drop("datetime") \
                if "datetime" in long_result.columns else long_result
        col_tz = long_result.schema["datetime"].time_zone
        as_of_cmp = (
            as_of.replace(tzinfo=None)
            if col_tz is None and as_of.tzinfo is not None
            else as_of
        )
        sliced = long_result.filter(pl.col("datetime") == pl.lit(as_of_cmp))
        if "datetime" in sliced.columns:
            sliced = sliced.drop("datetime")
        return sliced

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _empty_long_output(pipeline_cls: Type[Pipeline]) -> pl.DataFrame:
        schema: Dict[str, Any] = {
            "datetime": pl.Datetime,
            "symbol": pl.Utf8,
        }
        for name in pipeline_cls.get_columns():
            schema[name] = pl.Float64
        return pl.DataFrame(schema=schema)


__all__ = ["VectorPipelineEngine", "PANEL_COLUMNS"]
