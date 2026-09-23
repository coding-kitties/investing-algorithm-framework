"""Attempt-isolated synchronous recording with bounded batch admission."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil

from .base import StoreError, StoreHandleNotFoundError


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'[A-Za-z0-9_-]{1,128}', value):
        raise StoreError('Identifiers must be 1-128 ASCII letters/digits/_/-')
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(64 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class _LimitedFile:
    def __init__(self, output, limit):
        self.output = output
        self.limit = limit

    @property
    def closed(self):
        return self.output.closed

    def writable(self):
        return True

    def tell(self):
        return self.output.tell()

    def write(self, data):
        if self.tell() + len(data) > self.limit:
            raise StoreError('Encoded chunk exceeds max_chunk_bytes')
        return self.output.write(data)

    def flush(self):
        self.output.flush()


class LocalRunWriter:
    """One producer per attempt. Oversized batches are rejected, never split.

    Limits bound retained Arrow buffers, admitted rows and encoded chunk bytes,
    not process RSS or Arrow/compressor allocator workspace. append_batch is
    synchronous and retains no batches after return. A failed I/O operation
    poisons the attempt; abort it and retry with a new attempt ID.
    """

    def __init__(self, store, run_id, attempt_id, schemas, *,
                 max_batch_bytes=8 * 1024 * 1024, max_batch_rows=8192,
                 max_chunk_bytes=16 * 1024 * 1024, metadata=None,
                 definition_ids=(), compression_level=3, retention='full'):
        import pyarrow as arrow

        self.store = store
        self.handle = f'{_identifier(run_id)}/{_identifier(attempt_id)}'
        self.path = store.root / 'streams' / run_id / attempt_id
        if not self.path.resolve().is_relative_to(store.root):
            raise StoreError('Stream path escapes store')
        if retention not in ('none', 'compact', 'full'):
            raise StoreError('Unknown retention policy')
        for limit in (max_batch_bytes, max_batch_rows, max_chunk_bytes):
            if type(limit) is not int or limit <= 0:
                raise StoreError('Limits must be positive integers')
        valid_level_type = type(compression_level) is int
        if not valid_level_type or not 1 <= compression_level <= 19:
            raise StoreError('Zstandard compression level must be 1..19')
        if not 1 <= len(schemas) <= 16:
            raise StoreError('Require 1..16 record schemas')
        self.schemas = dict(schemas)
        encoded_schemas = {}
        for kind, schema in self.schemas.items():
            _identifier(kind)
            if not isinstance(schema, arrow.Schema) or len(
                    set(schema.names)) != len(schema):
                raise StoreError('Require Arrow schemas with unique fields')
            payload = schema.serialize()
            if payload.size > 16384:
                raise StoreError('Schema exceeds 16 KiB')
            encoded_schemas[kind] = base64.b64encode(payload).decode('ascii')
        if len(definition_ids) > 256:
            raise StoreError('At most 256 definition references per attempt')
        for identity in definition_ids:
            store.get_definition(identity)
        self.manifest = {
            'version': 1, 'run_id': run_id, 'attempt_id': attempt_id,
            'schemas': encoded_schemas, 'definition_ids': list(definition_ids),
            'metadata': metadata or {}, 'compression': 'zstd',
            'retention': retention,
            'compression_level': compression_level,
            'limits': {'batch_bytes': max_batch_bytes,
                       'batch_rows': max_batch_rows,
                       'chunk_bytes': max_chunk_bytes},
        }
        if len(_json(self.manifest)) > 64 * 1024:
            raise StoreError('Run metadata and schemas exceed 64 KiB')
        self.manifest = json.loads(_json(self.manifest))
        self.max_batch_bytes = max_batch_bytes
        self.max_batch_rows = max_batch_rows
        self.max_chunk_bytes = max_chunk_bytes
        self.compression_level = compression_level
        self.counts = {kind: 0 for kind in schemas}
        self.chunk_count = 0
        self.peak_batch_bytes = 0
        self._state = 'open'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError as exc:
            raise StoreError(
                'Attempt exists; reopen committed or use a new ID'
            ) from exc
        (self.path / 'chunks').mkdir()
        (self.path / 'chunks.jsonl').touch(exist_ok=False)
        _sync_directory(self.path.parent)
        _sync_directory(self.path.parent.parent)
        _sync_directory(store.root)

    def _require_open(self):
        if self._state != 'open':
            raise StoreError(f'Writer is {self._state}')

    def append_batch(self, kind, batch):
        import pyarrow as arrow
        import pyarrow.compute as compute
        import pyarrow.parquet as parquet

        self._require_open()
        if self.manifest['retention'] == 'none':
            raise StoreError('Recording disabled for this attempt')
        if kind not in self.schemas or not isinstance(
                batch, arrow.RecordBatch):
            raise StoreError('Require a registered kind and Arrow RecordBatch')
        if not batch.schema.equals(self.schemas[kind], check_metadata=True):
            raise StoreError('Batch schema mismatch')
        batch.validate(full=True)
        if any(not field.nullable and column.null_count
               for field, column in zip(batch.schema, batch.columns)):
            raise StoreError('Null in required field')
        size = batch.get_total_buffer_size()
        if size > self.max_batch_bytes or batch.num_rows > self.max_batch_rows:
            raise StoreError('Oversized batch; produce smaller owned batches')
        if batch.num_rows == 0:
            return
        self.peak_batch_bytes = max(self.peak_batch_bytes, size)
        name = f'chunks/{self.chunk_count:012d}.parquet'
        target = self.path / name
        try:
            with target.open('xb') as output:
                parquet.write_table(
                    arrow.Table.from_batches([batch]),
                    _LimitedFile(output, self.max_chunk_bytes),
                    compression='zstd',
                    compression_level=self.compression_level,
                    use_dictionary=False, write_statistics=False,
                    data_page_size=65536, write_batch_size=1024,
                    row_group_size=self.max_batch_rows,
                )
                output.flush()
                os.fsync(output.fileno())
            timestamp_range = None
            if 'timestamp_us' in batch.schema.names:
                column = batch.column(
                    batch.schema.get_field_index('timestamp_us'))
                if arrow.types.is_int64(column.type):
                    bounds = compute.min_max(column).as_py()
                    timestamp_range = [bounds['min'], bounds['max']]
            entry = {
                'path': name, 'kind': kind, 'rows': batch.num_rows,
                'arrow_bytes': size, 'file_bytes': target.stat().st_size,
                'sha256': _digest(target),
                'timestamp_range_us': timestamp_range,
            }
            with (self.path / 'chunks.jsonl').open('ab') as index:
                index.write(_json(entry) + b'\n')
                index.flush()
                os.fsync(index.fileno())
            self.chunk_count += 1
            self.counts[kind] += batch.num_rows
        except BaseException:
            self._state = 'failed'
            raise

    def flush(self):
        self._require_open()
        try:
            with (self.path / 'chunks.jsonl').open('rb') as index:
                os.fsync(index.fileno())
            _sync_directory(self.path / 'chunks')
            _sync_directory(self.path)
        except BaseException:
            self._state = 'failed'
            raise

    def commit(self):
        if self._state == 'committed':
            return self.handle
        self._require_open()
        try:
            self.flush()
            manifest = dict(self.manifest, chunks=self.chunk_count,
                            counts=self.counts,
                            index_sha256=_digest(self.path / 'chunks.jsonl'))
            temporary = self.path / 'manifest.pending'
            with temporary.open('xb') as output:
                output.write(_json(manifest))
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, self.path / 'manifest.json')
            _sync_directory(self.path)
            self._state = 'committed'
            return self.handle
        except BaseException:
            self._state = 'failed'
            raise

    def abort(self):
        if (self.path / 'manifest.json').exists():
            raise StoreError('Cannot abort a published attempt')
        if self._state == 'aborted':
            return
        shutil.rmtree(self.path)
        _sync_directory(self.path.parent)
        self._state = 'aborted'

    def __enter__(self):
        self._require_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._state != 'committed' and not (
                self.path / 'manifest.json').exists():
            self.abort()


def stream_path(store, handle):
    parts = handle.split('/')
    if len(parts) != 2:
        raise StoreError('Expected run/attempt handle')
    candidate = store.root / 'streams' / \
        _identifier(parts[0]) / _identifier(parts[1])
    if not candidate.resolve().is_relative_to(store.root):
        raise StoreError('Stream path escapes store')
    return candidate


def discard_attempt(store, handle, *, producer_stopped=False):
    """Explicit orphan cleanup, never an age-based race with a live worker."""
    if producer_stopped is not True:
        raise StoreError('Confirm producer_stopped before removing an attempt')
    path = stream_path(store, handle)
    if (path / 'manifest.json').exists():
        raise StoreError('Cannot discard a published attempt')
    if path.exists():
        shutil.rmtree(path)
        _sync_directory(path.parent)


def read_manifest(store, handle):
    path = stream_path(store, handle)
    try:
        with (path / 'manifest.json').open('rb') as source:
            payload = source.read(128 * 1024 + 1)
    except FileNotFoundError as exc:
        raise StoreHandleNotFoundError(handle) from exc
    if len(payload) > 128 * 1024:
        raise StoreError('Oversized manifest')
    try:
        manifest = json.loads(payload)
        if manifest['version'] != 1 or handle != (
            f"{manifest['run_id']}/{manifest['attempt_id']}"
        ):
            raise StoreError('Invalid manifest identity/version')
        if _digest(path / 'chunks.jsonl') != manifest['index_sha256']:
            raise StoreError('Chunk index checksum mismatch')
        for identity in manifest['definition_ids']:
            store.get_definition(identity)
        return manifest
    except (KeyError, ValueError, OSError) as exc:
        raise StoreError('Invalid or incomplete stream manifest') from exc


def iter_batches(store, handle, kind=None):
    import pyarrow as arrow
    import pyarrow.parquet as parquet

    manifest = read_manifest(store, handle)
    path = stream_path(store, handle)
    schemas = {
        name: arrow.ipc.read_schema(
            arrow.BufferReader(
                base64.b64decode(value)))
        for name, value in manifest['schemas'].items()
    }
    if kind is not None and kind not in schemas:
        raise StoreError('Unknown record kind')
    counts = {name: 0 for name in schemas}
    chunks = 0
    with (path / 'chunks.jsonl').open('rb') as index:
        while True:
            line = index.readline(8193)
            if not line:
                break
            if len(line) > 8192:
                raise StoreError('Oversized chunk index entry')
            entry = json.loads(line)
            if entry['path'] != f'chunks/{chunks:012d}.parquet':
                raise StoreError('Invalid chunk sequence/path')
            target = path / entry['path']
            if target.is_symlink():
                raise StoreError('Chunk symlinks are not supported')
            if (target.stat().st_size != entry['file_bytes']
                    or entry['file_bytes'] > manifest['limits']['chunk_bytes']
                    or _digest(target) != entry['sha256']):
                raise StoreError('Chunk checksum/size mismatch')
            counts[entry['kind']] += entry['rows']
            chunks += 1
            if kind is not None and entry['kind'] != kind:
                continue
            table = parquet.ParquetFile(target).read()
            schema_matches = table.schema.equals(
                schemas[entry['kind']], check_metadata=True
            )
            if not schema_matches or table.num_rows != entry['rows']:
                raise StoreError('Chunk schema/count mismatch')
            yield from table.to_batches(
                max_chunksize=manifest['limits']['batch_rows']
            )
    if counts != manifest['counts'] or chunks != manifest['chunks']:
        raise StoreError('Manifest totals mismatch')
