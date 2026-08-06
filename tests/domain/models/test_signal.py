"""Unit tests for the v9.0 Signal / SignalSide types."""
from unittest import TestCase

from investing_algorithm_framework import Signal, SignalSide


class TestSignalSide(TestCase):

    def test_is_open_close_long_short_classification(self):
        self.assertTrue(SignalSide.OPEN_LONG.is_open)
        self.assertTrue(SignalSide.SCALE_IN.is_open)
        self.assertTrue(SignalSide.OPEN_SHORT.is_open)
        self.assertFalse(SignalSide.CLOSE_LONG.is_open)
        self.assertFalse(SignalSide.SCALE_OUT.is_open)
        self.assertFalse(SignalSide.CLOSE_SHORT.is_open)

        self.assertTrue(SignalSide.CLOSE_LONG.is_close)
        self.assertTrue(SignalSide.SCALE_OUT.is_close)
        self.assertTrue(SignalSide.CLOSE_SHORT.is_close)

        for side in (
            SignalSide.OPEN_LONG, SignalSide.CLOSE_LONG,
            SignalSide.SCALE_IN, SignalSide.SCALE_OUT,
        ):
            self.assertTrue(side.is_long)
            self.assertFalse(side.is_short)

        for side in (SignalSide.OPEN_SHORT, SignalSide.CLOSE_SHORT):
            self.assertTrue(side.is_short)
            self.assertFalse(side.is_long)

    def test_from_value_accepts_enum_value_and_name(self):
        self.assertEqual(
            SignalSide.from_value("open_long"), SignalSide.OPEN_LONG,
        )
        self.assertEqual(
            SignalSide.from_value("OPEN_LONG"), SignalSide.OPEN_LONG,
        )
        self.assertEqual(
            SignalSide.from_value(SignalSide.OPEN_LONG),
            SignalSide.OPEN_LONG,
        )

    def test_from_value_rejects_unknown(self):
        with self.assertRaises(ValueError):
            SignalSide.from_value("bogus")
        with self.assertRaises(TypeError):
            SignalSide.from_value(42)


class TestSignal(TestCase):

    def test_construct_with_enum_side(self):
        s = Signal(symbol="BTC", side=SignalSide.OPEN_LONG)
        self.assertEqual(s.symbol, "BTC")
        self.assertEqual(s.side, SignalSide.OPEN_LONG)
        self.assertEqual(s.strength, 1.0)
        self.assertEqual(s.source, "")
        self.assertEqual(s.metadata, {})

    def test_construct_with_string_side_coerces(self):
        s = Signal(symbol="BTC", side="open_long")
        self.assertEqual(s.side, SignalSide.OPEN_LONG)

    def test_strength_must_be_in_unit_interval(self):
        with self.assertRaises(ValueError):
            Signal(symbol="BTC", side=SignalSide.OPEN_LONG, strength=1.5)
        with self.assertRaises(ValueError):
            Signal(symbol="BTC", side=SignalSide.OPEN_LONG, strength=-0.1)

    def test_symbol_must_be_nonempty_str(self):
        with self.assertRaises(ValueError):
            Signal(symbol="", side=SignalSide.OPEN_LONG)
        with self.assertRaises(ValueError):
            Signal(symbol=None, side=SignalSide.OPEN_LONG)  # type: ignore[arg-type]

    def test_with_strength_returns_new_instance(self):
        s = Signal("BTC", SignalSide.OPEN_LONG, strength=0.5, source="x")
        s2 = s.with_strength(0.8)
        self.assertEqual(s.strength, 0.5)
        self.assertEqual(s2.strength, 0.8)
        self.assertEqual(s2.source, "x")
        self.assertIsNot(s, s2)

    def test_with_metadata_merges_keys(self):
        s = Signal(
            "BTC", SignalSide.OPEN_LONG, metadata={"a": 1, "b": 2},
        )
        s2 = s.with_metadata(b=20, c=3)
        self.assertEqual(s.metadata, {"a": 1, "b": 2})
        self.assertEqual(s2.metadata, {"a": 1, "b": 20, "c": 3})

    def test_is_frozen(self):
        s = Signal("BTC", SignalSide.OPEN_LONG)
        with self.assertRaises(Exception):
            s.symbol = "ETH"  # type: ignore[misc]
