"""Unit tests for VectorBacktestService._bucket_signal_series (v9.0)."""
import unittest

import pandas as pd

from investing_algorithm_framework import SignalSeries, SignalSide
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_backtest_service import VectorBacktestService


def _series(values):
    return pd.Series(
        values, index=pd.date_range("2024-01-01", periods=len(values))
    )


class TestBucketSignalSeries(unittest.TestCase):
    def test_buckets_each_side_by_symbol(self):
        stream = [
            SignalSeries("BTC", SignalSide.OPEN_LONG, _series([True, False])),
            SignalSeries("BTC", SignalSide.CLOSE_LONG, _series([False, True])),
            SignalSeries("ETH", SignalSide.OPEN_LONG, _series([True, True])),
        ]
        buy, sell, si, so, sh, cv = \
            VectorBacktestService._bucket_signal_series(stream)
        self.assertEqual(set(buy.keys()), {"BTC", "ETH"})
        self.assertEqual(set(sell.keys()), {"BTC"})
        self.assertIsNone(si)
        self.assertIsNone(so)
        self.assertIsNone(sh)
        self.assertIsNone(cv)

    def test_returns_none_when_short_pair_missing(self):
        stream = [
            SignalSeries("BTC", SignalSide.OPEN_LONG, _series([True])),
        ]
        _, _, _, _, sh, cv = \
            VectorBacktestService._bucket_signal_series(stream)
        self.assertIsNone(sh)
        self.assertIsNone(cv)

    def test_collects_short_and_cover_when_emitted(self):
        stream = [
            SignalSeries("ETH", SignalSide.OPEN_SHORT, _series([True])),
            SignalSeries("ETH", SignalSide.CLOSE_SHORT, _series([False])),
        ]
        _, _, _, _, sh, cv = \
            VectorBacktestService._bucket_signal_series(stream)
        self.assertIsNotNone(sh)
        self.assertIsNotNone(cv)
        self.assertEqual(set(sh.keys()), {"ETH"})
        self.assertEqual(set(cv.keys()), {"ETH"})

    def test_collects_scale_in_and_scale_out(self):
        stream = [
            SignalSeries("BTC", SignalSide.SCALE_IN, _series([True])),
            SignalSeries("BTC", SignalSide.SCALE_OUT, _series([False])),
        ]
        _, _, si, so, _, _ = \
            VectorBacktestService._bucket_signal_series(stream)
        self.assertEqual(set(si.keys()), {"BTC"})
        self.assertEqual(set(so.keys()), {"BTC"})

    def test_empty_stream(self):
        buy, sell, si, so, sh, cv = \
            VectorBacktestService._bucket_signal_series([])
        self.assertEqual(buy, {})
        self.assertEqual(sell, {})
        self.assertIsNone(si)
        self.assertIsNone(so)
        self.assertIsNone(sh)
        self.assertIsNone(cv)

    def test_last_wins_per_symbol_side(self):
        first = _series([True, False])
        second = _series([False, True])
        stream = [
            SignalSeries("BTC", SignalSide.OPEN_LONG, first),
            SignalSeries("BTC", SignalSide.OPEN_LONG, second),
        ]
        buy, *_ = VectorBacktestService._bucket_signal_series(stream)
        self.assertIs(buy["BTC"], second)


if __name__ == "__main__":
    unittest.main()
