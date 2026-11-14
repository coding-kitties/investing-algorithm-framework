"""Bounded adapter for existing engine signal reports and result artifacts."""
import json
from contextlib import contextmanager
from uuid import uuid4

from .base import StoreError
from .local_tiered_store import LocalTieredStore


class SignalRecorder:
    """One producer; append does not retain the source report objects."""

    def __init__(self, root, *, engine, metadata=None, batch_bytes=262144,
                 batch_rows=1024, max_record_bytes=65536):
        import pyarrow as arrow

        for value in (batch_bytes, batch_rows, max_record_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError('Recording limits must be positive integers')
        if max_record_bytes + 4 > batch_bytes:
            raise ValueError('Record limit must fit in the batch byte limit')
        self.store = LocalTieredStore(root)
        self.schema = arrow.schema([
            arrow.field('payload', arrow.binary(), nullable=False),
        ], metadata={b'iaf.record_kind': b'engine_signal_report',
                     b'iaf.record_version': b'1'})
        self.writer = self.store.begin_run(
            engine, uuid4().hex, {'signal_report': self.schema},
            metadata=metadata, max_batch_bytes=batch_bytes + 4,
            max_batch_rows=batch_rows,
        )
        self.batch_bytes = batch_bytes
        self.batch_rows = batch_rows
        self.max_record_bytes = max_record_bytes
        self._payloads = []
        self._bytes = 0
        self.count = 0
        self.peak_buffer_bytes = 0

    def append(self, report):
        from investing_algorithm_framework.domain.backtesting.bundle import (
            _msgpack_default,
        )

        self.writer._require_open()
        try:
            payload = json.dumps(
                report, default=_msgpack_default,
                separators=(',', ':'), allow_nan=False,
            ).encode()
        except (ValueError, TypeError) as exc:
            raise StoreError('Cannot encode signal report') from exc
        if len(payload) > self.max_record_bytes:
            raise StoreError('Signal report exceeds max_record_bytes')
        size = len(payload) + 4
        if self._bytes + size > self.batch_bytes:
            self.flush()
        self._payloads.append(payload)
        self._bytes += size
        self.count += 1
        self.peak_buffer_bytes = max(self.peak_buffer_bytes, self._bytes)
        if len(self._payloads) >= self.batch_rows:
            self.flush()

    def flush(self):
        import pyarrow as arrow

        self.writer._require_open()
        if not self._payloads:
            return
        batch = arrow.RecordBatch.from_arrays([
            arrow.array(self._payloads, type=arrow.binary()),
        ], schema=self.schema)
        self.writer.append_batch('signal_report', batch)
        self._payloads.clear()
        self._bytes = 0

    def commit(self):
        if self.writer._state != 'committed':
            self.flush()
        return self.writer.commit()

    def abort(self):
        self.writer.abort()
        self._payloads.clear()
        self._bytes = 0

    def reference(self):
        return {'version': 1, 'handle': self.writer.handle,
                'kind': 'signal_report', 'count': self.count}

    def __enter__(self):
        self.writer.__enter__()
        return self

    def __exit__(self, *args):
        return self.writer.__exit__(*args)


def iter_signal_reports(root, reference):
    if (reference.get('version') != 1
            or reference.get('kind') != 'signal_report'):
        raise StoreError('Unsupported signal report reference')
    count = 0
    store = LocalTieredStore(root)
    for batch in store.iter_run_batches(reference['handle'], 'signal_report'):
        for payload in batch.column(0):
            count += 1
            yield json.loads(payload.as_py())
    if count != reference['count']:
        raise StoreError('Signal report count mismatch')


@contextmanager
def recording_session(root, engine, metadata=None):
    if root is None:
        yield None
        return
    try:
        with SignalRecorder(
                root, engine=engine, metadata=metadata) as recorder:
            yield recorder
    except OSError as exc:
        raise StoreError('Signal recording session failed') from exc
