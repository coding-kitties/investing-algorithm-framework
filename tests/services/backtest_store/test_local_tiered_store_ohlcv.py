"""Tests for Tier-3 content-addressed OHLCV chunks in
:class:`LocalTieredStore` (epic #540 phase 3c)."""
from __future__ import annotations

import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework.domain import Backtest, BUNDLE_EXT
from investing_algorithm_framework.services.backtest_store import (
    LocalTieredStore,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


def _make_ohlcv(symbol: str, *, n: int = 4, base: float = 100.0) -> dict:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {
            "Datetime": idx,
            "Open": [base + i for i in range(n)],
            "High": [base + i + 0.5 for i in range(n)],
            "Low": [base + i - 0.5 for i in range(n)],
            "Close": [base + i + 0.25 for i in range(n)],
            "Volume": [1000 + i for i in range(n)],
        }
    )
    return {f"{symbol}:1h": df}


class TestLocalTieredStoreOhlcv(TestCase):
    """OHLCV content-addressed chunk store (Tier-3)."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = LocalTieredStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _backtest_with_ohlcv(self, symbol: str) -> Backtest:
        # Deep-copy the fixture and attach a synthetic OHLCV blob.
        bt = deepcopy(self.fixture)
        bt.ohlcv = _make_ohlcv(symbol)
        return bt

    # ------------------------------------------------------------------
    # Bundles without OHLCV must not create the chunk dir.
    # ------------------------------------------------------------------
    def test_no_ohlcv_no_chunk_dir(self):
        self.store.write(self.fixture, handle="plain")
        self.assertFalse((Path(self.tmp) / "ohlcv").is_dir())
        self.assertEqual(self.store.ohlcv_stats()["stored_blobs"], 0)

    # ------------------------------------------------------------------
    # Tier-3 layout & dedup
    # ------------------------------------------------------------------
    def test_ohlcv_chunks_written_to_shared_store(self):
        bt = self._backtest_with_ohlcv("BTC/EUR")
        self.store.write(bt, handle="r1")
        chunks = list((Path(self.tmp) / "ohlcv").iterdir())
        self.assertEqual(len(chunks), 1)
        # Filename is <sha256>.parquet — 64 hex chars + .parquet.
        name = chunks[0].name
        self.assertTrue(name.endswith(".parquet"))
        self.assertEqual(len(name) - len(".parquet"), 64)

    def test_identical_ohlcv_is_deduplicated_across_handles(self):
        bt1 = self._backtest_with_ohlcv("BTC/EUR")
        # Different algorithm_id but identical OHLCV bytes.
        bt2 = self._backtest_with_ohlcv("BTC/EUR")
        self.store.write(bt1, handle="a")
        self.store.write(bt2, handle="b")
        chunks = sorted((Path(self.tmp) / "ohlcv").iterdir())
        self.assertEqual(
            len(chunks), 1,
            "identical OHLCV must be stored exactly once",
        )
        stats = self.store.ohlcv_stats()
        self.assertEqual(stats["stored_blobs"], 1)
        self.assertEqual(stats["referenced_blobs"], 1)
        self.assertEqual(stats["orphan_blobs"], 0)
        self.assertEqual(stats["missing_blobs"], 0)

    def test_different_ohlcv_yields_separate_chunks(self):
        self.store.write(
            self._backtest_with_ohlcv("BTC/EUR"), handle="btc",
        )
        # Different base price -> different bytes -> different hash.
        bt2 = self._backtest_with_ohlcv("ETH/EUR")
        bt2.ohlcv = _make_ohlcv("ETH/EUR", base=2000.0)
        self.store.write(bt2, handle="eth")
        chunks = sorted((Path(self.tmp) / "ohlcv").iterdir())
        self.assertEqual(len(chunks), 2)
        self.assertEqual(self.store.ohlcv_stats()["stored_blobs"], 2)

    # ------------------------------------------------------------------
    # Round-trip via canonical bundle still resolves OHLCV.
    # ------------------------------------------------------------------
    def test_open_resolves_ohlcv_from_shared_store(self):
        bt = self._backtest_with_ohlcv("BTC/EUR")
        self.store.write(bt, handle="rt")
        loaded = self.store.open("rt")
        self.assertIn("BTC/EUR:1h", loaded.ohlcv)
        df = loaded.ohlcv["BTC/EUR:1h"]
        self.assertEqual(len(df), 4)

    # ------------------------------------------------------------------
    # Garbage collection
    # ------------------------------------------------------------------
    def test_delete_keeps_shared_ohlcv_until_gc(self):
        bt1 = self._backtest_with_ohlcv("BTC/EUR")
        bt2 = self._backtest_with_ohlcv("BTC/EUR")
        self.store.write(bt1, handle="a")
        self.store.write(bt2, handle="b")
        self.store.delete("a")
        # The chunk is still referenced by handle 'b' -> must stay.
        self.assertEqual(
            self.store.ohlcv_stats()["stored_blobs"], 1,
        )
        self.assertEqual(self.store.ohlcv_stats()["orphan_blobs"], 0)

    def test_garbage_collect_ohlcv_removes_orphans(self):
        bt = self._backtest_with_ohlcv("BTC/EUR")
        self.store.write(bt, handle="solo")
        # Delete the only referencing bundle.
        self.store.delete("solo")
        stats = self.store.ohlcv_stats()
        self.assertEqual(stats["stored_blobs"], 1)
        self.assertEqual(stats["orphan_blobs"], 1)

        # Dry-run lists but does not delete.
        orphans = self.store.garbage_collect_ohlcv(dry_run=True)
        self.assertEqual(len(orphans), 1)
        self.assertEqual(self.store.ohlcv_stats()["stored_blobs"], 1)

        removed = self.store.garbage_collect_ohlcv()
        self.assertEqual(len(removed), 1)
        self.assertEqual(self.store.ohlcv_stats()["stored_blobs"], 0)
        self.assertEqual(self.store.ohlcv_stats()["orphan_blobs"], 0)

    # ------------------------------------------------------------------
    # iter_ohlcv_hashes / ohlcv_referenced_hashes — input for the
    # dedup-upload negotiate step (docs/design/ohlcv-dedup-protocol.md).
    # ------------------------------------------------------------------
    def test_iter_ohlcv_hashes_lists_referenced_chunks(self):
        self.store.write(
            self._backtest_with_ohlcv("BTC/EUR"), handle="a",
        )
        self.store.write(
            self._backtest_with_ohlcv("BTC/EUR"), handle="b",
        )
        hashes = list(self.store.iter_ohlcv_hashes())
        # Two references to the same hash (one per bundle).
        self.assertEqual(len(hashes), 2)
        self.assertEqual(len(set(hashes)), 1)
        # Hashes are bare hex digests.
        for h in hashes:
            self.assertEqual(len(h), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_referenced_hashes_set_dedups(self):
        bt = self._backtest_with_ohlcv("BTC/EUR")
        self.store.write(bt, handle="a")
        self.store.write(bt, handle="b")
        self.assertEqual(len(self.store.ohlcv_referenced_hashes()), 1)
