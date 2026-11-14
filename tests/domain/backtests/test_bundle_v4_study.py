"""Tests for the bundle-format v4 study/multi-universe extension.

Covers:

* The new top-level :class:`Universe` dataclass round-trip.
* :class:`Backtest` dataclass round-trip via ``to_dict``/``from_dict``
  for the new ``study_name``, ``study_description``, ``universes``,
  and per-engine ``*_summaries_by_universe`` fields.
* On-disk v4 envelope round-trip via ``save_bundle``/``open_bundle``,
  including the format header bump.
* Backwards-compatible reading of v3 envelopes (synthesized via the
  bundle encoder with ``format_version`` overridden) so existing
  bundles continue to load with empty study/universe defaults.
"""
import os
import shutil
import tempfile
from unittest import TestCase

from investing_algorithm_framework import Backtest, Universe
from investing_algorithm_framework.domain.backtesting import (
    BUNDLE_EXT,
    BUNDLE_FORMAT_VERSION,
    BacktestSummaryMetrics,
    save_bundle,
    open_bundle,
)
from investing_algorithm_framework.domain.backtesting.study import Study
from investing_algorithm_framework.domain.backtesting.bundle import (
    _MAGIC,
    _atomic_write_bytes,
    _encode_payload,
    peek_bundle_format_version,
)


def _make_summary(sharpe: float = 1.0) -> BacktestSummaryMetrics:
    return BacktestSummaryMetrics(sharpe_ratio=sharpe)


class TestUniverseDataclass(TestCase):
    def test_round_trip(self):
        u = Universe(
            key="majors",
            symbols=["BTC", "ETH"],
            trading_symbol="EUR",
            market="BITVAVO",
            metadata={"source": "manual"},
        )
        restored = Universe.from_dict(u.to_dict())
        self.assertEqual(restored.key, "majors")
        self.assertEqual(restored.symbols, ["BTC", "ETH"])
        self.assertEqual(restored.trading_symbol, "EUR")
        self.assertEqual(restored.market, "BITVAVO")
        self.assertEqual(restored.metadata, {"source": "manual"})

    def test_from_dict_handles_none(self):
        self.assertIsNone(Universe.from_dict(None))


class TestBacktestStudyFieldsRoundTrip(TestCase):
    """``Backtest.to_dict``/``from_dict`` must preserve v4 fields."""

    def test_defaults_are_empty(self):
        bt = Backtest(algorithm_id="abc12345")
        self.assertIsNone(bt.get_study())
        self.assertEqual(bt.universes, [])
        self.assertEqual(bt.vector_summaries_by_universe, {})
        self.assertEqual(bt.event_summaries_by_universe, {})

    def test_to_from_dict_round_trip(self):
        majors = Universe(
            key="majors", symbols=["BTC", "ETH"],
            trading_symbol="EUR", market="BITVAVO",
        )
        alts = Universe(
            key="alts", symbols=["LTC", "XRP"],
            trading_symbol="EUR", market="BITVAVO",
        )
        bt = Backtest(
            algorithm_id="abc12345",
            study_name="supertrend_in_sample_v1",
            study_description="BALANCED on majors basket, 2022-2025",
            universes=[majors, alts],
            vector_summaries_by_universe={
                "majors": _make_summary(1.2),
                "alts": _make_summary(0.8),
            },
        )
        restored = Backtest.from_dict(bt.to_dict())
        self.assertEqual(restored.get_study().name, "supertrend_in_sample_v1")
        self.assertEqual(
            restored.get_study().description,
            "BALANCED on majors basket, 2022-2025",
        )
        self.assertEqual(
            [u.key for u in restored.universes], ["majors", "alts"],
        )
        self.assertEqual(
            sorted(restored.vector_summaries_by_universe), ["alts", "majors"],
        )
        self.assertAlmostEqual(
            restored.vector_summaries_by_universe["majors"].sharpe_ratio,
            1.2,
        )


class TestBundleV4Envelope(TestCase):
    """End-to-end v4 envelope writer + reader."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_save_emits_v4_header(self):
        bt = Backtest(algorithm_id="abc12345")
        path = save_bundle(bt, os.path.join(self.tmp, "x" + BUNDLE_EXT))
        with open(path, "rb") as fh:
            head = fh.read(8)
        self.assertEqual(head[:4], _MAGIC)
        self.assertEqual(
            int.from_bytes(head[4:8], "little"), BUNDLE_FORMAT_VERSION,
        )
        self.assertEqual(BUNDLE_FORMAT_VERSION, 5)
        self.assertEqual(peek_bundle_format_version(path), 5)

    def test_round_trip_preserves_study_and_universes(self):
        majors = Universe(
            key="majors", symbols=["BTC", "ETH"],
            trading_symbol="EUR", market="BITVAVO",
        )
        alts = Universe(
            key="alts", symbols=["LTC", "XRP"],
            trading_symbol="EUR", market="BITVAVO",
        )
        bt = Backtest(
            algorithm_id="abc12345",
            parameters={"ema_period": 50},
            tag="balanced_winners",
            study_name="supertrend_in_sample_v1",
            study_description="OOS validation",
            universes=[majors, alts],
            vector_summaries_by_universe={
                "majors": _make_summary(1.2),
                "alts": _make_summary(0.8),
            },
        )
        path = save_bundle(bt, os.path.join(self.tmp, "x" + BUNDLE_EXT))
        loaded = open_bundle(path)

        self.assertEqual(loaded.get_study().name, "supertrend_in_sample_v1")
        self.assertEqual(loaded.get_study().description, "OOS validation")
        self.assertEqual([u.key for u in loaded.universes], ["majors", "alts"])
        self.assertEqual(loaded.universes[0].symbols, ["BTC", "ETH"])
        self.assertEqual(loaded.universes[1].market, "BITVAVO")
        self.assertAlmostEqual(
            loaded.vector_summaries_by_universe["majors"].sharpe_ratio, 1.2,
        )
        self.assertAlmostEqual(
            loaded.vector_summaries_by_universe["alts"].sharpe_ratio, 0.8,
        )
        # The pre-v4 top-level fields must still round-trip.
        self.assertEqual(loaded.algorithm_id, "abc12345")
        self.assertEqual(loaded.parameters, {"ema_period": 50})
        self.assertEqual(loaded.tag, "balanced_winners")


class TestBundleV3BackwardCompat(TestCase):
    """v3 envelopes (no study/universe keys) must load cleanly under v4."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_v3_envelope_loads_with_empty_v4_defaults(self):
        # Hand-built minimal v3 envelope: no ``study_name`` /
        # ``study_description`` / ``universes`` / per-engine
        # ``summaries_by_universe`` keys. Encoded with ``format_version
        # =3`` directly via the low-level helpers so we don't depend on
        # write-time v3 support.
        from pathlib import Path

        doc = {
            "format_version": 3,
            "algorithm_id": "legacyv3",
            "tag": "legacy",
            "risk_free_rate": None,
            "strategy_ids": ["LegacyStrategy"],
            "parameters": {"ema_period": 50},
            "metadata": {"note": "v3-fixture"},
            "monte_carlo_tests": None,
        }
        payload = _encode_payload(doc, format_version=3)
        target = Path(self.tmp) / ("legacyv3" + BUNDLE_EXT)
        _atomic_write_bytes(target, payload)

        loaded = open_bundle(target)
        self.assertEqual(loaded.algorithm_id, "legacyv3")
        self.assertEqual(loaded.parameters, {"ema_period": 50})
        self.assertEqual(loaded.tag, "legacy")
        # v4 defaults: explicitly empty, never raise.
        self.assertIsNone(loaded.get_study())
        self.assertEqual(loaded.universes, [])
        self.assertEqual(loaded.vector_summaries_by_universe, {})
        self.assertEqual(loaded.event_summaries_by_universe, {})

    def test_resaved_v3_bundle_is_upgraded_to_v4(self):
        # Encode a v3 envelope, write it, then resave via the public
        # writer. The resulting file must be v4 and round-trip the
        # original fields.
        from pathlib import Path

        doc = {
            "format_version": 3,
            "algorithm_id": "upgrademe",
            "tag": "legacy",
            "risk_free_rate": None,
            "strategy_ids": [],
            "parameters": {"ema": 12},
            "metadata": {},
            "monte_carlo_tests": None,
        }
        payload = _encode_payload(doc, format_version=3)
        target = Path(self.tmp) / ("upgrademe" + BUNDLE_EXT)
        _atomic_write_bytes(target, payload)
        self.assertEqual(peek_bundle_format_version(target), 3)

        loaded = open_bundle(target)
        # v3 bundles have no study; create one then rename it.
        loaded.add_study(Study(name="after-upgrade"))
        save_bundle(loaded, target)

        self.assertEqual(peek_bundle_format_version(target), 5)
        reloaded = open_bundle(target)
        self.assertEqual(reloaded.algorithm_id, "upgrademe")
        self.assertEqual(reloaded.parameters, {"ema": 12})
        self.assertEqual(reloaded.get_study().name, "after-upgrade")
