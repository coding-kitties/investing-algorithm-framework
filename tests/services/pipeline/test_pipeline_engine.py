"""End-to-end tests for the eager Phase 1 PipelineEngine."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import polars as pl

from investing_algorithm_framework import (
    AverageDollarVolume,
    Pipeline,
    Returns,
)
from investing_algorithm_framework.services.pipeline import PipelineEngine


def _ohlcv(symbol_to_closes_volumes):
    """Build a ``data_object`` (identifier → polars DataFrame).

    Identifier == symbol for these tests.
    """
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


class TestPipelineEngine(unittest.TestCase):

    def test_engine_evaluates_pipeline_and_applies_universe(self):
        data = _ohlcv(
            {
                "AAA": [(10, 100), (12, 100), (14, 100)],   # adv=1300
                "BBB": [(10, 1), (11, 1), (12, 1)],          # adv=11.5 -> dropped
                "CCC": [(10, 200), (11, 200), (13, 200)],    # adv=2400
            }
        )
        symbol_to_identifier = {s: s for s in data}
        as_of = datetime(2024, 1, 3)

        engine = PipelineEngine()
        result = engine.evaluate(
            pipeline_cls=_MomentumScreener,
            data_object=data,
            symbol_to_identifier=symbol_to_identifier,
            as_of=as_of,
        )

        self.assertEqual(
            set(result.columns), {"symbol", "adv", "momentum", "alpha"}
        )
        rows = {r["symbol"]: r for r in result.to_dicts()}
        self.assertEqual(set(rows), {"AAA", "CCC"})
        # Momentum at as_of is close[t]/close[t-2] - 1
        self.assertAlmostEqual(rows["AAA"]["momentum"], 0.4)
        self.assertAlmostEqual(rows["CCC"]["momentum"], 0.3)
        # alpha = ascending ordinal rank within universe → CCC=1, AAA=2
        self.assertEqual(rows["CCC"]["alpha"], 1.0)
        self.assertEqual(rows["AAA"]["alpha"], 2.0)

    def test_engine_no_lookahead_extra_future_bars_do_not_change_result(self):
        """Adding bars strictly after ``as_of`` must not affect output."""
        closes_short = [(10, 100), (12, 100), (14, 100)]
        closes_long = closes_short + [(20, 100), (25, 100)]

        class _Single(Pipeline):
            momentum = Returns(window=2)

        engine = PipelineEngine()
        as_of = datetime(2024, 1, 3)

        short = engine.evaluate(
            pipeline_cls=_Single,
            data_object=_ohlcv({"AAA": closes_short}),
            symbol_to_identifier={"AAA": "AAA"},
            as_of=as_of,
        )
        long = engine.evaluate(
            pipeline_cls=_Single,
            data_object=_ohlcv({"AAA": closes_long}),
            symbol_to_identifier={"AAA": "AAA"},
            as_of=as_of,
        )
        self.assertEqual(short.to_dicts(), long.to_dicts())

    def test_engine_handles_pandas_data_frames(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed")

        class _Single(Pipeline):
            momentum = Returns(window=1)

        bars = [
            {
                "Datetime": datetime(2024, 1, 1) + timedelta(days=i),
                "Open": c, "High": c, "Low": c, "Close": c, "Volume": 1.0,
            }
            for i, c in enumerate([10, 11, 12])
        ]
        data = {"AAA": pd.DataFrame(bars)}

        engine = PipelineEngine()
        result = engine.evaluate(
            pipeline_cls=_Single,
            data_object=data,
            symbol_to_identifier={"AAA": "AAA"},
            as_of=datetime(2024, 1, 3),
        )
        rows = result.to_dicts()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "AAA")
        self.assertAlmostEqual(rows[0]["momentum"], 12.0 / 11.0 - 1.0)

    def test_engine_empty_panel_returns_empty_frame(self):
        engine = PipelineEngine()

        class _Single(Pipeline):
            momentum = Returns(window=1)

        result = engine.evaluate(
            pipeline_cls=_Single,
            data_object={},
            symbol_to_identifier={},
            as_of=datetime(2024, 1, 3),
        )
        self.assertTrue(result.is_empty())
        self.assertEqual(set(result.columns), {"symbol", "momentum"})

    def test_engine_missing_required_column_raises(self):
        """A data source missing a required OHLCV column must error loudly."""
        bad = {
            "AAA": pl.DataFrame(
                [
                    {"Datetime": datetime(2024, 1, 1), "Close": 10.0}
                    # Missing Open/High/Low/Volume
                ]
            )
        }

        class _Single(Pipeline):
            momentum = Returns(window=1)

        engine = PipelineEngine()
        with self.assertRaises(KeyError):
            engine.evaluate(
                pipeline_cls=_Single,
                data_object=bad,
                symbol_to_identifier={"AAA": "AAA"},
                as_of=datetime(2024, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()
