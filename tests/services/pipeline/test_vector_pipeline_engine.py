"""VectorPipelineEngine — Phase 2 tests (#502).

Two layers of testing:

1. Unit tests for the vector engine's own public surface
   (full-window output shape, caching, universe handling, empty input).
2. **Equivalence tests** — for a fixed dataset and pipeline, the
   per-bar slice of ``VectorPipelineEngine.evaluate_window`` must equal
   the wide frame returned by the event-mode :class:`PipelineEngine`
   for the same ``as_of``. This is the contract that lets strategies
   move between event and vector runners without rewrites.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import polars as pl

from investing_algorithm_framework import (
    AverageDollarVolume,
    Pipeline,
    Returns,
    Volatility,
)
from investing_algorithm_framework.services.pipeline import (
    PipelineEngine,
    VectorPipelineEngine,
)


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #
def _ohlcv(symbol_to_closes_volumes):
    out = {}
    for sym, bars in symbol_to_closes_volumes.items():
        rows = []
        for i, (close, volume) in enumerate(bars):
            rows.append(
                {
                    "Datetime": datetime(2024, 1, 1) + timedelta(days=i),
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Volume": volume,
                }
            )
        out[sym] = pl.DataFrame(rows)
    return out


class _MomentumScreener(Pipeline):
    adv = AverageDollarVolume(window=2)
    momentum = Returns(window=2)
    universe = adv.top(2)
    alpha = momentum.rank(mask=universe)


def _fixed_data():
    return _ohlcv(
        {
            # adv (mean(close*volume) window=2):
            #   d2: AAA=11*100=avg(10*100,12*100)=1100, BBB=avg(10,11)=10.5,
            #       CCC=avg(10*200,11*200)=2100
            #   d3: AAA=avg(12*100,14*100)=1300, BBB=avg(11,12)=11.5,
            #       CCC=avg(11*200,13*200)=2400
            "AAA": [(10, 100), (12, 100), (14, 100), (15, 100)],
            "BBB": [(10, 1), (11, 1), (12, 1), (13, 1)],
            "CCC": [(10, 200), (11, 200), (13, 200), (14, 200)],
        }
    )


def _normalise(df: pl.DataFrame) -> list:
    """Return an order-stable representation of the frame, with floats
    rounded so equality comparison is robust to fp wiggle."""
    rows = df.sort("symbol").to_dicts()
    out = []
    for row in rows:
        out.append(
            {
                k: (round(v, 9) if isinstance(v, float) else v)
                for k, v in row.items()
            }
        )
    return out


class TestVectorPipelineEngineUnit(unittest.TestCase):

    def test_vector_engine_returns_full_long_frame(self):
        data = _fixed_data()
        engine = VectorPipelineEngine()
        result = engine.evaluate_window(
            pipeline_cls=_MomentumScreener,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
        )

        # Long format: datetime + symbol + 3 factor columns (universe dropped)
        self.assertEqual(
            set(result.columns),
            {"datetime", "symbol", "adv", "momentum", "alpha"},
        )
        rows = result.to_dicts()
        pairs = [(r["datetime"], r["symbol"]) for r in rows]
        self.assertEqual(pairs, sorted(pairs))

    def test_vector_engine_universe_dropped_from_output(self):
        data = _fixed_data()
        engine = VectorPipelineEngine()
        result = engine.evaluate_window(
            pipeline_cls=_MomentumScreener,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
        )
        bbb_bars = result.filter(pl.col("symbol") == "BBB")
        aaa_bars = result.filter(pl.col("symbol") == "AAA")
        self.assertLessEqual(len(bbb_bars), len(aaa_bars))

    def test_vector_engine_empty_input_returns_empty_long_frame(self):
        engine = VectorPipelineEngine()

        class _Single(Pipeline):
            momentum = Returns(window=1)

        result = engine.evaluate_window(
            pipeline_cls=_Single,
            data_object={},
            symbol_to_identifier={},
        )
        self.assertTrue(result.is_empty())
        self.assertEqual(
            set(result.columns), {"datetime", "symbol", "momentum"}
        )

    def test_vector_engine_start_end_bounds_applied(self):
        data = _fixed_data()
        engine = VectorPipelineEngine()
        result = engine.evaluate_window(
            pipeline_cls=_MomentumScreener,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            start=datetime(2024, 1, 3),
            end=datetime(2024, 1, 4),
        )
        distinct_dts = sorted(result["datetime"].unique().to_list())
        self.assertEqual(
            distinct_dts, [datetime(2024, 1, 3), datetime(2024, 1, 4)]
        )

    def test_vector_engine_caches_factor_results(self):
        """A factor reused by ``rank(mask=...)`` should compute once."""
        call_count = {"n": 0}
        original = AverageDollarVolume.compute_panel

        def counting_compute(self, panel):
            call_count["n"] += 1
            return original(self, panel)

        with patch.object(
            AverageDollarVolume, "compute_panel", counting_compute
        ):
            data = _fixed_data()
            engine = VectorPipelineEngine()
            engine.evaluate_window(
                pipeline_cls=_MomentumScreener,
                data_object=data,
                symbol_to_identifier={s: s for s in data},
            )
        # adv is declared once and reused inside universe = adv.top(2).
        # With caching, compute_panel must be called exactly once for the
        # shared instance.
        self.assertEqual(call_count["n"], 1)

    def test_vector_engine_slice_at_returns_event_shape(self):
        data = _fixed_data()
        engine = VectorPipelineEngine()
        long = engine.evaluate_window(
            pipeline_cls=_MomentumScreener,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
        )
        sliced = VectorPipelineEngine.slice_at(long, datetime(2024, 1, 3))
        self.assertNotIn("datetime", sliced.columns)
        self.assertEqual(
            set(sliced.columns), {"symbol", "adv", "momentum", "alpha"}
        )


class TestVectorPipelineEngineEquivalence(unittest.TestCase):

    def test_vector_matches_event_mode_per_bar(self):
        for as_of in (
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
        ):
            with self.subTest(as_of=as_of):
                data = _fixed_data()
                sym_id = {s: s for s in data}

                event_engine = PipelineEngine()
                vector_engine = VectorPipelineEngine()

                event_result = event_engine.evaluate(
                    pipeline_cls=_MomentumScreener,
                    data_object=data,
                    symbol_to_identifier=sym_id,
                    as_of=as_of,
                )

                vector_long = vector_engine.evaluate_window(
                    pipeline_cls=_MomentumScreener,
                    data_object=data,
                    symbol_to_identifier=sym_id,
                    end=as_of,
                )
                vector_sliced = VectorPipelineEngine.slice_at(
                    vector_long, as_of
                )

                self.assertEqual(
                    set(event_result.columns), set(vector_sliced.columns)
                )
                self.assertEqual(
                    _normalise(event_result), _normalise(vector_sliced)
                )

    def test_vector_matches_event_mode_with_volatility_factor(self):
        """Add a heavier factor to widen coverage of the equivalence check."""

        class _MultiFactor(Pipeline):
            adv = AverageDollarVolume(window=2)
            mom = Returns(window=2)
            vol = Volatility(window=3)
            universe = adv.top(2)
            alpha = mom.rank(mask=universe)

        data = _fixed_data()
        sym_id = {s: s for s in data}
        as_of = datetime(2024, 1, 4)

        event_result = PipelineEngine().evaluate(
            pipeline_cls=_MultiFactor,
            data_object=data,
            symbol_to_identifier=sym_id,
            as_of=as_of,
        )
        vector_long = VectorPipelineEngine().evaluate_window(
            pipeline_cls=_MultiFactor,
            data_object=data,
            symbol_to_identifier=sym_id,
            end=as_of,
        )
        vector_sliced = VectorPipelineEngine.slice_at(vector_long, as_of)

        self.assertEqual(
            _normalise(event_result), _normalise(vector_sliced)
        )


if __name__ == "__main__":
    unittest.main()
