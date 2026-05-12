"""Tests for :class:`LocalTieredStore` (epic #540 phase 3b)."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestIndexRow,
    BUNDLE_EXT,
)
from investing_algorithm_framework.services.backtest_store import (
    BacktestStore,
    LocalDirStore,
    LocalTieredStore,
    StoreHandleNotFoundError,
    SupportsCopyFrom,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


class TestLocalTieredStore(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = LocalTieredStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Protocol conformance
    # ------------------------------------------------------------------
    def test_implements_protocol(self):
        self.assertIsInstance(self.store, BacktestStore)

    def test_implements_supports_copy_from(self):
        self.assertIsInstance(self.store, SupportsCopyFrom)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def test_write_creates_three_tiers(self):
        handle = self.store.write(self.fixture, handle="r1")
        root = Path(self.tmp)
        # Tier-0: canonical bundle.
        self.assertTrue((root / "bundles" / (handle + BUNDLE_EXT)).is_file())
        # Tier-1: SQLite index.
        self.assertTrue((root / "index.sqlite").is_file())
        # Tier-2: parquet root exists; per-dataset partitions are only
        # created when there is at least one record to write (the
        # fixture may have empty snapshots/trades/orders).
        self.assertTrue((root / "parquet").is_dir())

    def test_handle_normalization_strips_bundle_suffix(self):
        h1 = self.store.write(self.fixture, handle="with" + BUNDLE_EXT)
        # Stored bare; iter_handles returns bare names.
        self.assertNotIn(BUNDLE_EXT, h1)
        self.assertIn("with", list(self.store.iter_handles()))

    # ------------------------------------------------------------------
    # Round-trip via canonical bundle
    # ------------------------------------------------------------------
    def test_round_trip_preserves_algorithm_id(self):
        self.store.write(self.fixture, handle="rt")
        loaded = self.store.open("rt")
        self.assertEqual(loaded.algorithm_id, self.fixture.algorithm_id)

    def test_summary_only_open(self):
        self.store.write(self.fixture, handle="so")
        bt = self.store.open("so", summary_only=True)
        self.assertEqual(bt.algorithm_id, self.fixture.algorithm_id)

    # ------------------------------------------------------------------
    # Tier-1: index is always in sync
    # ------------------------------------------------------------------
    def test_iter_index_rows_after_write(self):
        self.store.write(self.fixture, handle="a")
        self.store.write(self.fixture, handle="b")
        rows = list(self.store.iter_index_rows())
        self.assertEqual(len(rows), 2)
        handles = {row.bundle_path for row in rows}
        self.assertSetEqual(handles, {"a", "b"})
        for row in rows:
            self.assertIsInstance(row, BacktestIndexRow)

    def test_delete_removes_all_tiers(self):
        self.store.write(self.fixture, handle="gone")
        self.store.delete("gone")
        self.assertFalse(self.store.exists("gone"))
        rows = list(self.store.iter_index_rows())
        self.assertEqual(len(rows), 0)
        # Tier-2 partitions for this handle are removed.
        root = Path(self.tmp)
        for name in ("portfolio_snapshots", "trades", "orders"):
            self.assertFalse(
                (root / "parquet" / name / "run_id=gone").exists()
            )

    def test_len_uses_index(self):
        self.assertEqual(len(self.store), 0)
        self.store.write(self.fixture, handle="x")
        self.store.write(self.fixture, handle="y")
        self.assertEqual(len(self.store), 2)

    # ------------------------------------------------------------------
    # Tier-2: cross-run analytics
    # ------------------------------------------------------------------
    def test_scan_returns_arrow_dataset_when_available(self):
        try:
            import pyarrow  # noqa: F401
            import pyarrow.dataset  # noqa: F401
        except ImportError:
            self.skipTest("pyarrow not installed")
        self.store.write(self.fixture, handle="a")
        self.store.write(self.fixture, handle="b")
        ds = self.store.scan("portfolio_snapshots")
        # Fixture may have empty snapshots; dataset may be None if no
        # sidecar was written. Tolerate both — what we are asserting
        # is that the scan API works when sidecars are present.
        if ds is None:
            return
        table = ds.to_table()
        self.assertIn("run_id", table.column_names)
        # If any rows were written, run_id values are a subset of our
        # two handles.
        if table.num_rows:
            unique = set(table.column("run_id").to_pylist())
            self.assertTrue(unique.issubset({"a", "b"}))

    def test_scan_unknown_dataset_raises(self):
        with self.assertRaises(ValueError):
            self.store.scan("nope")

    # ------------------------------------------------------------------
    # SupportsCopyFrom — interop with LocalDirStore
    # ------------------------------------------------------------------
    def test_copy_from_local_dir_store(self):
        src = LocalDirStore(tempfile.mkdtemp())
        try:
            src.write(self.fixture, handle="alpha")
            src.write(self.fixture, handle="beta")
            n = self.store.copy_from(src)
            self.assertEqual(n, 2)
            self.assertEqual(len(self.store), 2)
            self.assertTrue(self.store.exists("alpha"))
            self.assertTrue(self.store.exists("beta"))
        finally:
            shutil.rmtree(src.root, ignore_errors=True)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def test_rebuild_index_recreates_tier1(self):
        self.store.write(self.fixture, handle="rebuild_me")
        # Drop the sqlite file and rebuild from the bundles.
        (Path(self.tmp) / "index.sqlite").unlink()
        n = self.store.rebuild_index()
        self.assertEqual(n, 1)
        rows = list(self.store.iter_index_rows())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].bundle_path, "rebuild_me")

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------
    def test_open_missing_handle_raises(self):
        with self.assertRaises(StoreHandleNotFoundError):
            self.store.open("nope")

    # ------------------------------------------------------------------
    # Tier-2 with real rows (synthetic, not the fixture)
    # ------------------------------------------------------------------
    def test_tier2_partition_written_when_records_present(self):
        try:
            import pyarrow  # noqa: F401
            import pyarrow.dataset as ds
        except ImportError:
            self.skipTest("pyarrow not installed")

        # Patch decomposers to yield deterministic synthetic records.
        from investing_algorithm_framework.services.backtest_store \
            import decompose

        original = decompose.DATASETS

        def fake_snaps(_bt, run_id):
            return [
                {"ts": 1, "total_value": 100.0, "run_id": run_id},
                {"ts": 2, "total_value": 110.0, "run_id": run_id},
            ]

        def fake_trades(_bt, run_id):
            return [{"trade_id": "t1", "net_gain": 5.0, "run_id": run_id}]

        def fake_orders(_bt, _run_id):
            return []  # exercise the empty branch too

        decompose.DATASETS = (
            ("portfolio_snapshots", fake_snaps),
            ("trades", fake_trades),
            ("orders", fake_orders),
        )
        try:
            self.store.write(self.fixture, handle="synthetic")
            root = Path(self.tmp) / "parquet"
            self.assertTrue(
                (root / "portfolio_snapshots" / "run_id=synthetic").is_dir()
            )
            self.assertTrue(
                (root / "trades" / "run_id=synthetic").is_dir()
            )
            # Empty orders => no partition directory.
            self.assertFalse(
                (root / "orders" / "run_id=synthetic").exists()
            )

            scan = self.store.scan("portfolio_snapshots")
            self.assertIsNotNone(scan)
            tbl = scan.to_table()
            self.assertEqual(tbl.num_rows, 2)
            self.assertIn("run_id", tbl.column_names)
            self.assertEqual(
                set(tbl.column("run_id").to_pylist()), {"synthetic"}
            )
        finally:
            decompose.DATASETS = original
