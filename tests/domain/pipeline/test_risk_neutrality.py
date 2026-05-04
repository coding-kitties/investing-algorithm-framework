"""Tests for risk-neutrality primitives (#504).

Covers:
- ``StaticPerSymbol`` broadcasting
- ``CrossSectionalMean``
- ``Factor.zscore(groups=...)`` and ``Factor.demean(groups=...)``
- ``RollingBeta``
- ``Neutralize`` (cross-sectional OLS residualisation)
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import numpy as np
import polars as pl

from investing_algorithm_framework import (
    AverageDollarVolume,
    CrossSectionalMean,
    Neutralize,
    Pipeline,
    Returns,
    RollingBeta,
    StaticPerSymbol,
)
from investing_algorithm_framework.services.pipeline import PipelineEngine


def _ohlcv(symbol_to_closes):
    out = {}
    for sym, closes in symbol_to_closes.items():
        rows = []
        for i, close in enumerate(closes):
            rows.append(
                {
                    "Datetime": datetime(2024, 1, 1) + timedelta(days=i),
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Volume": 100,
                }
            )
        out[sym] = pl.DataFrame(rows)
    return out


class TestStaticPerSymbol(unittest.TestCase):

    def test_static_per_symbol_broadcasts_dict(self):
        class _Pipe(Pipeline):
            sectors = StaticPerSymbol(
                {"AAA": "TECH", "BBB": "FIN", "CCC": "TECH"}
            )
            # Need a numeric column so the pipeline produces output.
            r = Returns(window=1)

        data = _ohlcv(
            {
                "AAA": [10, 11, 12],
                "BBB": [10, 11, 12],
                "CCC": [10, 11, 12],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        rows = {row["symbol"]: row["sectors"] for row in result.to_dicts()}
        self.assertEqual(
            rows, {"AAA": "TECH", "BBB": "FIN", "CCC": "TECH"}
        )

    def test_static_per_symbol_default_for_missing(self):
        factor = StaticPerSymbol({"AAA": 1.0}, default=0.0)
        self.assertEqual(factor._mapping, {"AAA": 1.0})
        self.assertEqual(factor._default, 0.0)

    def test_static_per_symbol_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            StaticPerSymbol([("AAA", "TECH")])  # type: ignore[arg-type]


class TestSectorNeutralTransforms(unittest.TestCase):

    def test_demean_with_groups_is_sector_relative(self):
        """With sector groups, mean of demeaned values is zero *within
        each sector* per bar, not across the whole universe."""

        class _Pipe(Pipeline):
            sectors = StaticPerSymbol(
                {"AAA": "T", "BBB": "T", "CCC": "F", "DDD": "F"}
            )
            r = Returns(window=1)
            sector_neutral = r.demean(groups=sectors)

        data = _ohlcv(
            {
                "AAA": [10, 11, 12],
                "BBB": [10, 11, 13],
                "CCC": [10, 11, 14],
                "DDD": [10, 11, 15],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        by_sector = {"T": [], "F": []}
        for row in result.to_dicts():
            by_sector[row["sectors"]].append(row["sector_neutral"])
        for vals in by_sector.values():
            self.assertAlmostEqual(sum(vals), 0.0, places=9)

    def test_zscore_with_groups_dict_argument(self):
        """Passing a dict directly (not a StaticPerSymbol) works."""

        class _Pipe(Pipeline):
            r = Returns(window=1)
            z = r.zscore(
                groups={"AAA": "T", "BBB": "T", "CCC": "F", "DDD": "F"}
            )

        data = _ohlcv(
            {
                "AAA": [10, 11, 12],
                "BBB": [10, 11, 13],
                "CCC": [10, 11, 14],
                "DDD": [10, 11, 15],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        zs = [
            row["z"] for row in result.to_dicts() if row["z"] is not None
        ]
        self.assertEqual(len(zs), 4)
        # In each 2-symbol sector the z-scores must be +/- 1
        # (or null if std=0).
        pairs = sorted(zs)
        self.assertAlmostEqual(pairs[0], -pairs[-1], places=9)


class TestCrossSectionalMean(unittest.TestCase):

    def test_cross_sectional_mean_equals_average_per_bar(self):
        class _Pipe(Pipeline):
            r = Returns(window=1)
            market = CrossSectionalMean(r)

        data = _ohlcv(
            {
                "AAA": [10, 11, 12],
                "BBB": [10, 12, 14],
                "CCC": [10, 13, 16],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        rows = result.to_dicts()
        expected = sum(row["r"] for row in rows) / len(rows)
        for row in rows:
            self.assertAlmostEqual(row["market"], expected)


class TestRollingBeta(unittest.TestCase):

    def test_rolling_beta_of_market_with_itself_is_one(self):
        """Beta of any series against itself is identically 1 (where
        variance is non-zero)."""

        class _Pipe(Pipeline):
            r = Returns(window=1)
            beta = RollingBeta(r, r, window=5)

        data = _ohlcv(
            {
                "AAA": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
                "BBB": [10, 12, 14, 16, 18, 20, 22, 24, 26, 28],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 10),
        )
        for row in result.to_dicts():
            if row["beta"] is not None:
                self.assertAlmostEqual(row["beta"], 1.0, places=6)

    def test_rolling_beta_zero_variance_yields_null(self):
        """When the market series has zero variance over the window,
        beta is null (not inf)."""

        class _Pipe(Pipeline):
            r = Returns(window=1)
            # Use a CrossSectionalMean of a constant-return series \u2014
            # variance will be zero except at the boundary.
            beta = RollingBeta(r, CrossSectionalMean(r), window=5)

        data = _ohlcv(
            {
                "AAA": [10] * 10,  # zero returns -> zero variance
                "BBB": [10] * 10,
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 10),
        )
        for row in result.to_dicts():
            self.assertIsNone(row["beta"])

    def test_rolling_beta_window_validation(self):
        with self.assertRaises(ValueError):
            RollingBeta(Returns(1), Returns(1), window=1)


class TestNeutralize(unittest.TestCase):

    def test_neutralize_residuals_are_orthogonal_to_exposures(self):
        """Residuals from OLS must be orthogonal to the design matrix in
        each bar (a fundamental property of least-squares)."""

        class _Pipe(Pipeline):
            r = Returns(window=1)
            size = StaticPerSymbol(
                {"AAA": 1.0, "BBB": 2.0, "CCC": 3.0, "DDD": 4.0}
            )
            residual = Neutralize(r, exposures=[size])

        data = _ohlcv(
            {
                "AAA": [10, 11, 12],
                "BBB": [10, 12, 14],
                "CCC": [10, 13, 16],
                "DDD": [10, 14, 18],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        rows = result.to_dicts()
        residuals = np.array([row["residual"] for row in rows])
        sizes = np.array([row["size"] for row in rows])
        # With an intercept, residuals must sum to zero AND be orthogonal
        # to the size column.
        self.assertAlmostEqual(residuals.sum(), 0.0, places=9)
        self.assertAlmostEqual((residuals * sizes).sum(), 0.0, places=9)

    def test_neutralize_rank_deficient_bar_yields_null(self):
        """When fewer surviving symbols than exposures+intercept, the
        bar's residuals are null (system is under-determined)."""

        class _Pipe(Pipeline):
            r = Returns(window=1)
            e1 = StaticPerSymbol({"AAA": 1.0, "BBB": 2.0})
            e2 = StaticPerSymbol({"AAA": 3.0, "BBB": 4.0})
            # 2 exposures + intercept = 3 parameters, only 2 symbols ->
            # under-determined.
            residual = Neutralize(r, exposures=[e1, e2])

        data = _ohlcv({"AAA": [10, 11, 12], "BBB": [10, 12, 14]})
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        for row in result.to_dicts():
            self.assertIsNone(row["residual"])

    def test_neutralize_with_market_factor_strips_beta(self):
        """Neutralizing returns against an equal-weighted market return
        leaves residuals whose dot product with the market is zero."""

        class _Pipe(Pipeline):
            r = Returns(window=1)
            market = CrossSectionalMean(r)
            residual = Neutralize(r, exposures=[market])

        data = _ohlcv(
            {
                "AAA": [10, 11, 12, 13, 14],
                "BBB": [10, 12, 13, 15, 16],
                "CCC": [10, 13, 14, 16, 18],
                "DDD": [10, 9, 11, 10, 12],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 5),
        )
        rows = result.to_dicts()
        residuals = np.array([row["residual"] for row in rows])
        market = np.array([row["market"] for row in rows])
        self.assertAlmostEqual((residuals * market).sum(), 0.0, places=9)

    def test_neutralize_requires_at_least_one_exposure(self):
        with self.assertRaises(ValueError):
            Neutralize(Returns(1), exposures=[])

    def test_neutralize_with_mask_excludes_filtered_symbols(self):
        class _Pipe(Pipeline):
            adv = AverageDollarVolume(window=1)
            r = Returns(window=1)
            size = StaticPerSymbol(
                {"AAA": 1.0, "BBB": 2.0, "CCC": 3.0, "DDD": 4.0}
            )
            universe = adv.top(3)
            residual = Neutralize(r, exposures=[size], mask=universe)

        data = _ohlcv(
            {
                "AAA": [10, 11, 12],
                "BBB": [10, 12, 14],
                "CCC": [10, 13, 16],
                "DDD": [10, 14, 18],
            }
        )
        result = PipelineEngine().evaluate(
            pipeline_cls=_Pipe,
            data_object=data,
            symbol_to_identifier={s: s for s in data},
            as_of=datetime(2024, 1, 3),
        )
        # Universe filter drops one symbol -- surviving rows must have
        # non-null residuals (3 symbols, 1 exposure + intercept = 2 params).
        for row in result.to_dicts():
            self.assertIsNotNone(row["residual"])


if __name__ == "__main__":
    unittest.main()
