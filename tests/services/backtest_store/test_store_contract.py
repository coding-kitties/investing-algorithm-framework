"""Parameterised conformance tests that run identical scenarios against
every concrete :class:`BacktestStore` implementation.

The point is to catch divergence early: any future store
(``LocalDirStore``, ``LocalTieredStore``, future remote stores) must
satisfy the exact same behavioural contract here. Any divergence
shows up as a failing subTest with the store class name in the label.

Phase 3d of epic #540.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Callable, List
from unittest import TestCase

from investing_algorithm_framework.domain import (
    Backtest,
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


# (label, factory) pairs — every store kind exercised by the contract.
_STORES: List[tuple] = [
    ("LocalDirStore", lambda root: LocalDirStore(root)),
    ("LocalTieredStore", lambda root: LocalTieredStore(root)),
]


class BacktestStoreContractTest(TestCase):
    """Behavioural contract every :class:`BacktestStore` must satisfy."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = Backtest.open(_FIXTURE)

    def _each_store(self, body: Callable[[BacktestStore, str], None]):
        for label, factory in _STORES:
            with self.subTest(store=label):
                root = tempfile.mkdtemp()
                try:
                    body(factory(root), root)
                finally:
                    shutil.rmtree(root, ignore_errors=True)

    # ------------------------------------------------------------------
    # Protocol conformance
    # ------------------------------------------------------------------
    def test_implements_protocol(self):
        def body(store, _root):
            self.assertIsInstance(store, BacktestStore)
            self.assertIsInstance(store, SupportsCopyFrom)
        self._each_store(body)

    # ------------------------------------------------------------------
    # write / open / exists / delete
    # ------------------------------------------------------------------
    def test_write_then_open_round_trips_algorithm_id(self):
        def body(store, _root):
            handle = store.write(self.fixture, handle="rt")
            loaded = store.open(handle)
            self.assertEqual(loaded.algorithm_id, self.fixture.algorithm_id)
        self._each_store(body)

    def test_summary_only_open(self):
        def body(store, _root):
            store.write(self.fixture, handle="so")
            bt = store.open("so", summary_only=True)
            self.assertEqual(bt.algorithm_id, self.fixture.algorithm_id)
        self._each_store(body)

    def test_exists_reflects_writes(self):
        def body(store, _root):
            self.assertFalse(store.exists("nope"))
            store.write(self.fixture, handle="x")
            self.assertTrue(store.exists("x"))
        self._each_store(body)

    def test_delete_is_idempotent_and_removes_handle(self):
        def body(store, _root):
            store.write(self.fixture, handle="gone")
            store.delete("gone")
            self.assertFalse(store.exists("gone"))
            # Second delete is a no-op, not an error.
            store.delete("gone")
        self._each_store(body)

    def test_open_missing_handle_raises(self):
        def body(store, _root):
            with self.assertRaises(StoreHandleNotFoundError):
                store.open("nope")
        self._each_store(body)

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    def test_iter_handles_returns_written_set(self):
        def body(store, _root):
            store.write(self.fixture, handle="a")
            store.write(self.fixture, handle="b")
            handles = set(store.iter_handles())
            # LocalDirStore returns the relative bundle path; both
            # representations include the bare stem.
            stems = {
                h[: -len(BUNDLE_EXT)] if h.endswith(BUNDLE_EXT) else h
                for h in handles
            }
            self.assertSetEqual(stems, {"a", "b"})
        self._each_store(body)

    def test_len_matches_written_count(self):
        def body(store, _root):
            self.assertEqual(len(store), 0)
            store.write(self.fixture, handle="a")
            store.write(self.fixture, handle="b")
            self.assertEqual(len(store), 2)
        self._each_store(body)

    def test_iter_index_rows_yields_one_per_bundle(self):
        def body(store, _root):
            store.write(self.fixture, handle="a")
            store.write(self.fixture, handle="b")
            rows = list(store.iter_index_rows())
            self.assertEqual(len(rows), 2)
        self._each_store(body)

    # ------------------------------------------------------------------
    # SupportsCopyFrom — every store can act as a copy destination.
    # ------------------------------------------------------------------
    def test_copy_from_local_dir_store(self):
        def body(store, _root):
            src_root = tempfile.mkdtemp()
            try:
                src = LocalDirStore(src_root)
                src.write(self.fixture, handle="alpha")
                src.write(self.fixture, handle="beta")
                n = store.copy_from(src)
                self.assertEqual(n, 2)
                self.assertEqual(len(store), 2)
            finally:
                shutil.rmtree(src_root, ignore_errors=True)
        self._each_store(body)

    def test_copy_from_subset_of_handles(self):
        def body(store, _root):
            src_root = tempfile.mkdtemp()
            try:
                src = LocalDirStore(src_root)
                src.write(self.fixture, handle="x")
                src.write(self.fixture, handle="y")
                src.write(self.fixture, handle="z")
                # Pick a subset using whatever handle vocabulary src
                # exposes for these stems.
                src_handles = list(src.iter_handles())
                pick = [h for h in src_handles if "x" in h or "z" in h]
                n = store.copy_from(src, handles=pick)
                self.assertEqual(n, 2)
                self.assertEqual(len(store), 2)
            finally:
                shutil.rmtree(src_root, ignore_errors=True)
        self._each_store(body)
