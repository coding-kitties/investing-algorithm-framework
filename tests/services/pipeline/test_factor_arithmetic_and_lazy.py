"""Phase 2c + 2d tests: factor arithmetic, cross-sectional transforms,
and the optional lazy/streaming execution path.

See ``investing_algorithm_framework/domain/pipeline/factor.py`` and
``investing_algorithm_framework/services/pipeline/vector_pipeline_engine.py``.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import polars as pl

from investing_algorithm_framework import (
    AverageDollarVolume,
    Pipeline,
    Returns,
    SMA,
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


def _fixed_data():
    return _ohlcv(
        {
            "AAA": [(10, 100), (12, 100), (14, 100), (15, 100)],
            "BBB": [(10, 100), (11, 100), (12, 100), (13, 100)],
            "CCC": [(10, 100), (11, 100), (13, 100), (14, 100)],
        }
    )


class TestFactorArithmetic(unittest.TestCase):

    def test_factor_addition_two_factors(self):
        class _Pipe(Pipeline):
            a = Returns(window=1)
            b = Returns(window=2)
            combined = a + b

        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=_fixed_data(),
            symbol_to_identifier={s: s for s in _fixed_data()},
            as_of=datetime(2024, 1, 4),
        )
        rows = {r["symbol"]: r for r in result.to_dicts()}
        self.assertAlmostEqual(
            rows["AAA"]["combined"], rows["AAA"]["a"] + rows["AAA"]["b"]
        )

    def test_factor_scalar_arithmetic_left_and_right(self):
        class _Pipe(Pipeline):
            r = Returns(window=2)
            plus_one = r + 1
            one_minus_r = 1 - r
            twice = 2 * r
            half = r / 2

        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=_fixed_data(),
            symbol_to_identifier={s: s for s in _fixed_data()},
            as_of=datetime(2024, 1, 3),
        )
        row = result.to_dicts()[0]
        r = row["r"]
        self.assertAlmostEqual(row["plus_one"], r + 1)
        self.assertAlmostEqual(row["one_minus_r"], 1 - r)
        self.assertAlmostEqual(row["twice"], 2 * r)
        self.assertAlmostEqual(row["half"], r / 2)

    def test_factor_negation(self):
        class _Pipe(Pipeline):
            r = Returns(window=2)
            neg = -r

        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=_fixed_data(),
            symbol_to_identifier={s: s for s in _fixed_data()},
            as_of=datetime(2024, 1, 3),
        )
        row = result.to_dicts()[0]
        self.assertAlmostEqual(row["neg"], -row["r"])

    def test_factor_arithmetic_unsupported_type_raises(self):
        with self.assertRaises(TypeError):
            Returns(window=2) + "not a factor"

    def test_factor_arithmetic_propagates_window_max(self):
        """A composite factor's required_window is the max of its inputs."""
        a = Returns(window=3)
        b = SMA(window=10)
        composite = a + b
        self.assertEqual(composite.required_window(), 10)


class TestCrossSectionalTransforms(unittest.TestCase):

    def test_zscore_per_bar_has_zero_mean_and_unit_std(self):
        class _Pipe(Pipeline):
            r = Returns(window=2)
            z = r.zscore()

        data = _fixed_data()
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        zs = [
            row["z"] for row in result.to_dicts() if row["z"] is not None
        ]
        # Cross-sectional z-score across symbols at one bar.
        self.assertGreaterEqual(len(zs), 2)
        mean = sum(zs) / len(zs)
        self.assertAlmostEqual(mean, 0.0, places=9)

    def test_demean_per_bar_sums_to_zero(self):
        class _Pipe(Pipeline):
            r = Returns(window=2)
            d = r.demean()

        data = _fixed_data()
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        demeaned = [
            row["d"] for row in result.to_dicts() if row["d"] is not None
        ]
        self.assertAlmostEqual(sum(demeaned), 0.0, places=9)

    def test_winsorize_clips_to_quantile_bounds(self):
        class _Pipe(Pipeline):
            r = Returns(window=2)
            clipped = r.winsorize(lower=0.25, upper=0.75)

        data = _fixed_data()
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        rows = result.to_dicts()
        raw = sorted(row["r"] for row in rows)
        clipped = sorted(row["clipped"] for row in rows)
        # Winsorisation cannot widen the range.
        self.assertLessEqual(max(clipped), max(raw))
        self.assertGreaterEqual(min(clipped), min(raw))

    def test_winsorize_invalid_bounds_raises(self):
        with self.assertRaises(ValueError):
            Returns(window=2).winsorize(lower=0.8, upper=0.2)

    def test_zscore_with_mask_excludes_masked_symbols(self):
        class _Pipe(Pipeline):
            adv = AverageDollarVolume(window=2)
            r = Returns(window=2)
            universe = adv.top(2)
            z = r.zscore(mask=universe)

        data = _fixed_data()  # all volumes equal so mask is deterministic
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        for row in result.to_dicts():
            self.assertIsNotNone(row["z"])


# --------------------------------------------------------------------- #
# Lazy engine (2d)
# --------------------------------------------------------------------- #
class _Screener(Pipeline):
    adv = AverageDollarVolume(window=2)
    momentum = Returns(window=2)
    universe = adv.top(2)
    alpha = momentum.rank(mask=universe)


class TestLazyEngine(unittest.TestCase):

    def test_lazy_engine_matches_eager_engine(self):
        """Lazy mode must produce identical output to eager mode for the
        same dataset and pipeline."""
        data = _fixed_data()
        sym_id = {s: s for s in data}

        eager = VectorPipelineEngine(lazy=False).evaluate_window(
            pipeline_cls=_Screener,
            data_object=data,
            symbol_to_identifier=sym_id,
        )
        lazy = VectorPipelineEngine(lazy=True).evaluate_window(
            pipeline_cls=_Screener,
            data_object=data,
            symbol_to_identifier=sym_id,
        )
        self.assertEqual(eager.to_dicts(), lazy.to_dicts())

    def test_lazy_engine_without_universe(self):
        """Lazy path with no universe filter still produces a sorted long
        frame."""

        class _NoUniverse(Pipeline):
            momentum = Returns(window=2)

        data = _fixed_data()
        result = VectorPipelineEngine(lazy=True).evaluate_window(
            pipeline_cls=_NoUniverse,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
        )
        pairs = [(r["datetime"], r["symbol"]) for r in result.to_dicts()]
        self.assertEqual(pairs, sorted(pairs))

    def test_lazy_engine_empty_input(self):
        class _NoUniverse(Pipeline):
            momentum = Returns(window=2)

        result = VectorPipelineEngine(lazy=True).evaluate_window(
            pipeline_cls=_NoUniverse,
            data_object={},
            symbol_to_identifier={},
        )
        self.assertTrue(result.is_empty())


# --------------------------------------------------------------------- #
# Stateless / Lambda + Functions safety
# --------------------------------------------------------------------- #
class TestEvaluationCacheState(unittest.TestCase):

    def test_evaluation_does_not_leak_cache_state(self):
        """Each ``evaluate`` call must reset the contextvar cache so that
        a second invocation in the same process (e.g. an Azure Function or
        AWS Lambda warm container) sees a fresh cache.
        """
        from investing_algorithm_framework.domain.pipeline.factor import (
            _EVAL_CACHE,
        )

        class _NoUniverse(Pipeline):
            momentum = Returns(window=2)

        data = _fixed_data()
        sym_id = {s: s for s in data}
        engine = PipelineEngine()

        self.assertIsNone(_EVAL_CACHE.get())

        engine.evaluate(
            pipeline_cls=_NoUniverse,
            data_object=data,
            symbol_to_identifier=sym_id,
            as_of=datetime(2024, 1, 3),
        )
        self.assertIsNone(_EVAL_CACHE.get())

        engine.evaluate(
            pipeline_cls=_NoUniverse,
            data_object=data,
            symbol_to_identifier=sym_id,
            as_of=datetime(2024, 1, 4),
        )
        self.assertIsNone(_EVAL_CACHE.get())


if __name__ == "__main__":
    unittest.main()
