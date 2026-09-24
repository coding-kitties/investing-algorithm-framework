"""Tests for :class:`LocalTieredStore` (epic #540 phase 3b)."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

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
    SupportsRecordDefinitions,
    StoreError,
)


_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources",
    "backtest_reports_for_testing",
    "test_algorithm_backtest",
)


class TestStreamingRuns(TestCase):
    def test_directory_sync_skips_unsupported_windows_open(self):
        from investing_algorithm_framework.services.backtest_store \
            import streaming

        with patch.object(streaming.os, 'name', 'nt'), patch.object(
            streaming.os, 'open', side_effect=PermissionError,
        ) as open_directory, patch.object(streaming.os, 'fsync') as sync:
            streaming._sync_directory(self.directory.name)
        open_directory.assert_not_called()
        sync.assert_not_called()

    def test_directory_sync_closes_posix_descriptor_on_failure(self):
        from investing_algorithm_framework.services.backtest_store \
            import streaming

        for error in (None, OSError('sync failed')):
            with self.subTest(error=error), patch.object(
                streaming.os, 'name', 'posix',
            ), patch.object(
                streaming.os, 'open', return_value=123,
            ) as open_directory, patch.object(
                streaming.os, 'fsync', side_effect=error,
            ) as sync, patch.object(streaming.os, 'close') as close:
                if error is None:
                    streaming._sync_directory(self.directory.name)
                else:
                    with self.assertRaisesRegex(OSError, 'sync failed'):
                        streaming._sync_directory(self.directory.name)
                open_directory.assert_called_once_with(
                    self.directory.name, os.O_RDONLY,
                )
                sync.assert_called_once_with(123)
                close.assert_called_once_with(123)

    def test_vector_engine_streams_identical_signals_and_results(self):
        from scripts.bench_vector_snapshot_events import workload, result_digest
        from investing_algorithm_framework.services.backtest_store.recording \
            import SignalRecorder, iter_signal_reports
        from investing_algorithm_framework.domain.backtesting.backtest_run \
            import _deserialise_signal_events

        for backend in ('python', 'auto'):
            service, arguments = workload(64, 2)
            expected = service.run(**arguments, execution_backend=backend)
            service, arguments = workload(64, 2)
            with SignalRecorder(self.directory.name, engine='vector',
                                batch_rows=3) as recorder:
                result = service.run(**arguments, execution_backend=backend,
                                     signal_recorder=recorder)
                self.assertEqual([], result.signal_events)
                reports = list(iter_signal_reports(
                    self.directory.name, result.metadata['signal_history']))
                result.signal_events = _deserialise_signal_events(reports)
                self.assertEqual(result_digest(expected), result_digest(result))

    def test_signal_adapter_bounds_and_roundtrip(self):
        from investing_algorithm_framework.services.backtest_store.recording \
            import SignalRecorder, iter_signal_reports

        with SignalRecorder(self.directory.name, engine='vector',
                            batch_bytes=128, max_record_bytes=64,
                            batch_rows=3) as recorder:
            for sequence in range(100):
                recorder.append({'sequence': sequence})
            recorder.commit()
            self.assertLessEqual(recorder.peak_buffer_bytes, 128)
            self.assertEqual([], recorder._payloads)
            self.assertEqual([{'sequence': value} for value in range(100)],
                             list(iter_signal_reports(
                                 self.directory.name, recorder.reference())))
        with SignalRecorder(self.directory.name, engine='event',
                            batch_bytes=128, max_record_bytes=64) as recorder:
            with self.assertRaises(StoreError):
                recorder.append({'value': 'x' * 100})

    def setUp(self):
        import pyarrow as arrow
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = LocalTieredStore(self.directory.name)
        self.schema = arrow.schema([
            arrow.field('timestamp_us', arrow.int64(), nullable=False),
            arrow.field('value', arrow.float64(), nullable=False),
        ])
        self.batch = arrow.RecordBatch.from_pylist([
            {'timestamp_us': 1, 'value': 100.},
            {'timestamp_us': 2, 'value': 102.},
        ], schema=self.schema)

    def test_bounded_roundtrip_and_commit_visibility(self):
        from investing_algorithm_framework.services.backtest_store import (
            SupportsStreamingRuns,
        )
        self.assertIsInstance(self.store, SupportsStreamingRuns)
        writer = self.store.begin_run('run', 'attempt', {'snapshot': self.schema},
                                      max_batch_bytes=32, max_batch_rows=2)
        for _ in range(10):
            writer.append_batch('snapshot', self.batch)
        self.assertEqual(32, writer.peak_batch_bytes)
        with self.assertRaises(StoreHandleNotFoundError):
            self.store.open_run_manifest(writer.handle)
        handle = writer.commit()
        self.assertEqual(handle, writer.commit())
        manifest = self.store.open_run_manifest(handle)
        self.assertEqual({'snapshot': 20}, manifest['counts'])
        self.assertEqual(10, manifest['chunks'])
        self.assertEqual([self.batch.to_pylist()] * 10, [
            batch.to_pylist() for batch in self.store.iter_run_batches(handle)
        ])
        with self.assertRaises(StoreError):
            writer.append_batch('snapshot', self.batch)
        with self.assertRaises(StoreError):
            writer.abort()

    def test_limits_abort_and_attempt_isolation(self):
        writer = self.store.begin_run('run', 'one', {'snapshot': self.schema},
                                      max_batch_bytes=16)
        with self.assertRaises(StoreError):
            writer.append_batch('snapshot', self.batch)
        self.assertEqual(0, writer.chunk_count)
        with self.assertRaises(StoreError):
            self.store.begin_run('run', 'one', {'snapshot': self.schema})
        writer.abort()
        writer.abort()
        with self.store.begin_run('run', 'two', {'snapshot': self.schema}) as other:
            other.append_batch('snapshot', self.batch)
        self.assertFalse(other.path.exists())

    def test_slice_retains_large_buffer_and_row_limit(self):
        import pyarrow as arrow
        large = arrow.RecordBatch.from_arrays([
            arrow.array(range(1000)), arrow.array([1.] * 1000),
        ], schema=self.schema)
        with self.store.begin_run('run', 'slice', {'snapshot': self.schema},
                                  max_batch_bytes=32) as writer:
            with self.assertRaises(StoreError):
                writer.append_batch('snapshot', large.slice(0, 1))
        with self.store.begin_run('run', 'rows', {'snapshot': self.schema},
                                  max_batch_rows=1) as writer:
            with self.assertRaises(StoreError):
                writer.append_batch('snapshot', self.batch)

    def test_io_failure_poisoning_and_explicit_orphan_cleanup(self):
        from unittest.mock import patch
        writer = self.store.begin_run(
            'run', 'failed', {
                'snapshot': self.schema})
        with patch('pyarrow.parquet.write_table', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                writer.append_batch('snapshot', self.batch)
        with self.assertRaises(StoreError):
            writer.commit()
        with self.assertRaises(StoreHandleNotFoundError):
            self.store.open_run_manifest(writer.handle)
        with self.assertRaises(StoreError):
            self.store.discard_run_attempt(writer.handle)
        self.store.discard_run_attempt(writer.handle, producer_stopped=True)
        self.assertFalse(writer.path.exists())

    def test_encoded_limit_and_manifest_failure(self):
        from unittest.mock import patch
        with self.store.begin_run('run', 'small', {'snapshot': self.schema},
                                  max_chunk_bytes=16) as writer:
            with self.assertRaises((StoreError, OSError)):
                writer.append_batch('snapshot', self.batch)
            with self.assertRaises(StoreError):
                writer.commit()
        with self.store.begin_run('run', 'link', {'snapshot': self.schema}) as writer:
            writer.append_batch('snapshot', self.batch)
            with patch('os.link', side_effect=OSError('publication failed')):
                with self.assertRaises(OSError):
                    writer.commit()
            with self.assertRaises(StoreHandleNotFoundError):
                self.store.open_run_manifest(writer.handle)

    def test_slow_sink_applies_backpressure(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch
        import pyarrow.parquet as parquet
        entered, release = Event(), Event()
        original = parquet.write_table

        def slow_write(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError('Timed out waiting for test release')
            return original(*args, **kwargs)

        with self.store.begin_run('run', 'slow', {'snapshot': self.schema}) as writer:
            with patch('pyarrow.parquet.write_table', side_effect=slow_write):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        writer.append_batch, 'snapshot', self.batch)
                    try:
                        self.assertTrue(entered.wait(5))
                        self.assertFalse(future.done())
                        self.assertEqual(0, writer.chunk_count)
                    finally:
                        release.set()
                    future.result(timeout=5)
            writer.commit()

    def test_move_corruption_and_retry_isolation(self):
        writer = self.store.begin_run('run', 'one', {'snapshot': self.schema})
        writer.append_batch('snapshot', self.batch)
        writer.commit()
        with self.assertRaises(StoreError):
            self.store.discard_run_attempt(
                writer.handle, producer_stopped=True)
        with self.store.begin_run('run', 'two', {'snapshot': self.schema}) as other:
            other.commit()
        moved = Path(self.directory.name) / 'moved'
        shutil.copytree(self.store.root / 'streams', moved / 'streams')
        copy = LocalTieredStore(moved)
        self.assertEqual(self.batch.to_pylist(),
                         next(copy.iter_run_batches(writer.handle)).to_pylist())
        (writer.path / 'chunks' / '000000000000.parquet').write_bytes(b'corrupt')
        with self.assertRaises(StoreError):
            list(self.store.iter_run_batches(writer.handle))
        self.assertEqual([], list(self.store.iter_run_batches(other.handle)))
        (other.path / 'chunks.jsonl').write_bytes(b'corrupt')
        with self.assertRaises(StoreError):
            self.store.open_run_manifest(other.handle)

    def test_canonical_evidence_schema_and_invalid_nulls(self):
        import pyarrow as arrow
        from investing_algorithm_framework.domain.backtesting.record_schemas import (
            record_batch, record_schema,
        )
        schema = record_schema('generic_trace')
        batch = record_batch('generic_trace', [{
            'evaluation_id': 'ev', 'attempt_id': 'evidence', 'sequence': 0,
            'timestamp_us': 123, 'symbol_id': 'BTC', 'strategy_id': 'ema',
            'trace_payload': b'{}',
        }])
        with self.store.begin_run('run', 'evidence', {'generic_trace': schema}) as writer:
            writer.append_batch('generic_trace', batch)
            writer.commit()
        self.assertTrue(
            next(
                self.store.iter_run_batches(
                    writer.handle)).equals(batch))
        invalid = arrow.RecordBatch.from_pylist([
            {'timestamp_us': None, 'value': 1.},
        ], schema=self.schema)
        with self.store.begin_run('run', 'invalid', {'snapshot': self.schema}) as writer:
            with self.assertRaises(StoreError):
                writer.append_batch('snapshot', invalid)

    def test_killed_producer_leaves_only_uncommitted_chunks(self):
        import subprocess
        import sys
        script = '''
import os
import sys
import pyarrow as arrow
from investing_algorithm_framework.services.backtest_store import LocalTieredStore
store = LocalTieredStore(sys.argv[1])
schema = arrow.schema([('value', arrow.int64())])
writer = store.begin_run('crash', 'attempt', {'data': schema})
writer.append_batch('data', arrow.RecordBatch.from_pylist(
    [{'value': 1}], schema=schema))
os._exit(42)
'''
        result = subprocess.run(
            [sys.executable, '-c', script, self.directory.name],
            capture_output=True, timeout=60,
        )
        self.assertEqual(42, result.returncode, result.stderr.decode())
        path = self.store.root / 'streams' / 'crash' / 'attempt'
        self.assertEqual(1, len(list((path / 'chunks').glob('*.parquet'))))
        with self.assertRaises(StoreHandleNotFoundError):
            self.store.open_run_manifest('crash/attempt')
        self.store.discard_run_attempt('crash/attempt', producer_stopped=True)
        self.assertFalse(path.exists())

    def test_flush_uses_writable_handle_and_preserves_index(self):
        with self.store.begin_run(
            'run', 'writable', {'snapshot': self.schema},
        ) as writer:
            writer.append_batch('snapshot', self.batch)
            index_path = writer.path / 'chunks.jsonl'
            expected = index_path.read_bytes()
            original_open = Path.open
            handles = []

            def checked_open(path, *args, **kwargs):
                handle = original_open(path, *args, **kwargs)
                if path == index_path:
                    handles.append(handle)
                    self.addCleanup(handle.close)
                    self.assertTrue(handle.writable())
                return handle

            with patch.object(Path, 'open', checked_open):
                writer.flush()
            self.assertEqual(len(handles), 1)
            self.assertTrue(handles[0].closed)
            self.assertEqual(index_path.read_bytes(), expected)
            handle = writer.commit()
            self.assertEqual([self.batch.to_pylist()], [
                batch.to_pylist()
                for batch in self.store.iter_run_batches(handle)
            ])

    def test_flush_failure_is_not_committable(self):
        from unittest.mock import patch
        with self.store.begin_run('run', 'flush', {'snapshot': self.schema}) as writer:
            writer.append_batch('snapshot', self.batch)
            with patch('os.fsync', side_effect=OSError('fsync failed')):
                with self.assertRaises(OSError):
                    writer.flush()
            with self.assertRaises(StoreError):
                writer.commit()


class TestRecordDefinitions(TestCase):

    def setUp(self):
        from investing_algorithm_framework import (
            ConfluenceCard, PrimaryGroup, condition,
        )
        from investing_algorithm_framework.domain.backtesting.records import (
            CardDefinition,
        )

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = LocalTieredStore(self.directory.name)
        self.definition = CardDefinition.from_card(ConfluenceCard(
            "persisted", PrimaryGroup(condition("price", "gt", value=0)),
        ))

    def test_definition_is_deduplicated_and_portable(self):
        self.assertIsInstance(self.store, SupportsRecordDefinitions)
        identity = self.store.put_definition("card", self.definition.payload)
        self.assertEqual(self.definition.card_id, identity)
        path = self.store._definition_path(identity)
        before = path.stat().st_mtime_ns
        self.assertEqual(identity, self.store.put_definition(
            "card", self.definition.payload
        ))
        self.assertEqual(before, path.stat().st_mtime_ns)
        moved = Path(self.directory.name) / "copy"
        shutil.copytree(self.store.root / "definitions", moved / "definitions")
        self.assertEqual(self.definition.payload,
                         LocalTieredStore(moved).get_definition(identity))
        self.assertEqual([path], list(path.parent.glob("*.json")))
        self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_concurrent_writers_publish_one_complete_definition(self):
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as executor:
            identities = list(executor.map(
                lambda _: self.store.put_definition(
                    "card", self.definition.payload
                ), range(12),
            ))
        self.assertEqual({self.definition.card_id}, set(identities))
        self.assertEqual(self.definition.payload,
                         self.store.get_definition(identities[0]))

    def test_missing_corrupt_and_unsafe_ids_fail(self):
        with self.assertRaises(StoreHandleNotFoundError):
            self.store.get_definition(self.definition.card_id)
        with self.assertRaises(StoreError):
            self.store.get_definition("../../other")
        identity = self.store.put_definition("card", self.definition.payload)
        self.store._definition_path(identity).write_bytes(b'[]')
        with self.assertRaises(StoreError):
            self.store.get_definition(identity)
        with self.assertRaises(StoreError):
            self.store.put_definition("card", self.definition.payload)


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
