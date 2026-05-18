"""Tests for the :class:`BacktestStore` Protocol and :class:`LocalDirStore`
adapter (epic #540 phase 3a)."""
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
    StoreError,
    StoreHandleNotFoundError,
    SupportsCopyFrom,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


class TestLocalDirStore(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = LocalDirStore(self.tmp)

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
    # write / open / exists / delete
    # ------------------------------------------------------------------
    def test_write_returns_handle_and_creates_bundle_file(self):
        handle = self.store.write(self.fixture, handle="run_a")
        self.assertEqual(handle, "run_a" + BUNDLE_EXT)
        self.assertTrue((Path(self.tmp) / handle).is_file())

    def test_write_default_handle_uses_algorithm_id_when_set(self):
        handle = self.store.write(self.fixture)
        # Fixture has an algorithm_id; the handle must derive from it.
        self.assertTrue(handle.endswith(BUNDLE_EXT))
        if self.fixture.algorithm_id:
            self.assertIn(str(self.fixture.algorithm_id), handle)

    def test_open_round_trip_matches_algorithm_id(self):
        handle = self.store.write(self.fixture, handle="rt")
        loaded = self.store.open(handle)
        self.assertEqual(loaded.algorithm_id, self.fixture.algorithm_id)

    def test_open_summary_only_skips_bulk_decode(self):
        handle = self.store.write(self.fixture, handle="so")
        loaded = self.store.open(handle, summary_only=True)
        self.assertEqual(loaded.algorithm_id, self.fixture.algorithm_id)

    def test_exists_true_after_write_false_after_delete(self):
        handle = self.store.write(self.fixture, handle="ed")
        self.assertTrue(self.store.exists(handle))
        self.assertIn(handle, self.store)
        self.store.delete(handle)
        self.assertFalse(self.store.exists(handle))
        self.assertNotIn(handle, self.store)

    def test_open_missing_handle_raises(self):
        with self.assertRaises(StoreHandleNotFoundError):
            self.store.open("nope.iafbt")

    def test_delete_missing_handle_is_noop(self):
        # Must not raise.
        self.store.delete("never_existed.iafbt")

    # ------------------------------------------------------------------
    # iter_handles / __len__ / iter_index_rows
    # ------------------------------------------------------------------
    def test_iter_handles_and_len(self):
        self.assertEqual(len(self.store), 0)
        self.store.write(self.fixture, handle="a")
        self.store.write(self.fixture, handle="sub/b")
        self.assertEqual(len(self.store), 2)
        handles = sorted(self.store.iter_handles())
        self.assertIn("a" + BUNDLE_EXT, handles)
        self.assertIn(os.path.join("sub", "b" + BUNDLE_EXT), handles)

    def test_iter_index_rows_yields_typed_rows_with_relative_paths(self):
        self.store.write(self.fixture, handle="r1")
        self.store.write(self.fixture, handle="r2")
        rows = list(self.store.iter_index_rows())
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIsInstance(row, BacktestIndexRow)
            self.assertIsNotNone(row.bundle_path)
            # bundle_path is relative to root, so it must not be absolute.
            self.assertFalse(os.path.isabs(row.bundle_path))

    def test_iter_index_rows_creates_sidecar_index(self):
        self.store.write(self.fixture, handle="cached")
        list(self.store.iter_index_rows())
        sidecar = Path(self.tmp) / "index.sqlite"
        self.assertTrue(sidecar.is_file())

    def test_iter_index_rows_without_index_works(self):
        nostore = LocalDirStore(self.tmp, use_index=False)
        nostore.write(self.fixture, handle="nox")
        rows = list(nostore.iter_index_rows())
        self.assertEqual(len(rows), 1)
        self.assertFalse((Path(self.tmp) / "index.sqlite").is_file())

    # ------------------------------------------------------------------
    # security: handle escape attempts
    # ------------------------------------------------------------------
    def test_handle_escape_rejected(self):
        with self.assertRaises(StoreError):
            self.store.write(self.fixture, handle="../escape")

    def test_absolute_handle_rejected(self):
        # Absolute paths get re-anchored by Path() to the abs root and
        # then escape the store root, so they must be rejected.
        with self.assertRaises(StoreError):
            self.store.write(self.fixture, handle="/etc/passwd")

    # ------------------------------------------------------------------
    # SupportsCopyFrom
    # ------------------------------------------------------------------
    def test_copy_from_other_store(self):
        src = LocalDirStore(tempfile.mkdtemp())
        try:
            src.write(self.fixture, handle="x")
            src.write(self.fixture, handle="y")
            n = self.store.copy_from(src)
            self.assertEqual(n, 2)
            self.assertEqual(len(self.store), 2)
            self.assertTrue(self.store.exists("x"))
            self.assertTrue(self.store.exists("y"))
        finally:
            shutil.rmtree(src.root, ignore_errors=True)

    def test_copy_from_with_handle_subset(self):
        src = LocalDirStore(tempfile.mkdtemp())
        try:
            src.write(self.fixture, handle="keep")
            src.write(self.fixture, handle="skip")
            n = self.store.copy_from(src, handles=["keep"])
            self.assertEqual(n, 1)
            self.assertTrue(self.store.exists("keep"))
            self.assertFalse(self.store.exists("skip"))
        finally:
            shutil.rmtree(src.root, ignore_errors=True)

    # ------------------------------------------------------------------
    # ergonomics
    # ------------------------------------------------------------------
    def test_handle_normalization_adds_bundle_suffix(self):
        # Caller may omit the .iafbt suffix and the store adds it.
        self.store.write(self.fixture, handle="no_suffix")
        self.assertTrue(self.store.exists("no_suffix"))
        self.assertTrue(self.store.exists("no_suffix" + BUNDLE_EXT))

    def test_root_is_created_if_missing(self):
        new_root = os.path.join(self.tmp, "deep", "nested", "store")
        s = LocalDirStore(new_root)
        self.assertTrue(Path(new_root).is_dir())
        self.assertEqual(len(s), 0)
