"""Tests for the SignalSeries vector-mode signal bundle (v9.0)."""
import unittest

import pandas as pd

from investing_algorithm_framework import (
    SignalSeries,
    SignalSide,
    signal_series_from_column,
)


class TestSignalSeries(unittest.TestCase):
    def _series(self):
        return pd.Series(
            [False, True, False],
            index=pd.date_range("2024-01-01", periods=3),
        )

    def test_construct_with_enum(self):
        ss = SignalSeries(
            symbol="BTC",
            side=SignalSide.OPEN_LONG,
            series=self._series(),
        )
        self.assertEqual(ss.symbol, "BTC")
        self.assertIs(ss.side, SignalSide.OPEN_LONG)
        self.assertEqual(ss.source, "")
        self.assertEqual(dict(ss.metadata), {})
        self.assertIsNone(ss.strength_series)

    def test_coerces_string_side(self):
        ss = SignalSeries(
            symbol="BTC", side="open_long", series=self._series(),
        )
        self.assertIs(ss.side, SignalSide.OPEN_LONG)

    def test_rejects_empty_symbol(self):
        with self.assertRaises(ValueError):
            SignalSeries(
                symbol="", side=SignalSide.OPEN_LONG, series=self._series(),
            )

    def test_rejects_none_series(self):
        with self.assertRaises(ValueError):
            SignalSeries(
                symbol="BTC", side=SignalSide.OPEN_LONG, series=None,
            )

    def test_carries_metadata_and_source(self):
        ss = SignalSeries(
            symbol="BTC",
            side=SignalSide.OPEN_LONG,
            series=self._series(),
            source="ema_cross",
            metadata={"fast": 12, "slow": 26},
        )
        self.assertEqual(ss.source, "ema_cross")
        self.assertEqual(dict(ss.metadata), {"fast": 12, "slow": 26})

    def test_immutable(self):
        ss = SignalSeries(
            symbol="BTC", side=SignalSide.OPEN_LONG, series=self._series(),
        )
        with self.assertRaises(Exception):
            ss.symbol = "ETH"  # frozen dataclass


class TestSignalSeriesFromColumn(unittest.TestCase):
    def _frame(self):
        idx = pd.date_range("2024-01-01", periods=3)
        return pd.DataFrame(
            {"entry": [False, True, False], "score": [0.1, 0.7, 0.2]},
            index=idx,
        )

    def test_pandas_basic(self):
        ss = signal_series_from_column(
            self._frame(), "entry",
            side=SignalSide.OPEN_LONG, symbol="BTC", source="rule",
        )
        self.assertIsInstance(ss, SignalSeries)
        self.assertEqual(ss.symbol, "BTC")
        self.assertEqual(ss.source, "rule")
        self.assertEqual(list(ss.series), [False, True, False])
        self.assertIsNone(ss.strength_series)

    def test_strength_column(self):
        ss = signal_series_from_column(
            self._frame(), "entry",
            side=SignalSide.OPEN_LONG, symbol="BTC",
            strength_column="score",
        )
        self.assertIsNotNone(ss.strength_series)
        self.assertEqual(list(ss.strength_series), [0.1, 0.7, 0.2])

    def test_missing_column_raises(self):
        with self.assertRaises(KeyError):
            signal_series_from_column(
                self._frame(), "missing",
                side=SignalSide.OPEN_LONG, symbol="BTC",
            )

    def test_missing_strength_column_raises(self):
        with self.assertRaises(KeyError):
            signal_series_from_column(
                self._frame(), "entry",
                side=SignalSide.OPEN_LONG, symbol="BTC",
                strength_column="missing",
            )

    def test_none_frame_raises(self):
        with self.assertRaises(ValueError):
            signal_series_from_column(
                None, "entry",
                side=SignalSide.OPEN_LONG, symbol="BTC",
            )

    def test_unsupported_frame_type_raises(self):
        with self.assertRaises(TypeError):
            signal_series_from_column(
                object(), "entry",
                side=SignalSide.OPEN_LONG, symbol="BTC",
            )


if __name__ == "__main__":
    unittest.main()
