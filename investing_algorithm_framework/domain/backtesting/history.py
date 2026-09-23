from collections.abc import Sequence
import operator
import os
import pickle
from struct import Struct
from tempfile import TemporaryFile
from threading import RLock
from weakref import finalize


class _HistoryFiles:
    def __init__(self):
        self.data = TemporaryFile()
        try:
            self.index = TemporaryFile()
        except BaseException:
            self.data.close()
            raise
        finalize(self, self._close_files, self.data, self.index)

    @staticmethod
    def _close_files(data, index):
        try:
            data.close()
        finally:
            index.close()


def _restore_history(model):
    history = BacktestHistory(model=model)
    history._restoring = True
    return history


class BacktestHistory(Sequence):
    """Read-only, detached result records backed by private temporary files.

    Iteration retains one decoded record at a time. Slices share immutable
    storage; ``list(history)`` explicitly materializes records in memory.
    Temporary files close when the last shared view is collected, or during
    normal interpreter shutdown if histories remain alive until then.
    """

    _offset = Struct('<QQ')

    def __init__(self, records=(), model=None):
        self._model = model
        self._lock = RLock()
        self._files = None
        self._data = None
        self._index = None
        try:
            count = 0
            for record in records:
                if self._data is None:
                    self._files = _HistoryFiles()
                    self._data = self._files.data
                    self._index = self._files.index
                payload = pickle.dumps(
                    record.to_dict() if model is not None else record,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
                offset = self._data.tell()
                self._data.write(payload)
                self._index.write(self._offset.pack(offset, len(payload)))
                count += 1
            if self._data is not None:
                self._data.flush()
                self._index.flush()
            self._selection = range(count)
        except BaseException:
            if self._data is not None:
                self._data.close()
            if self._index is not None:
                self._index.close()
            raise

    def __len__(self):
        return len(self._selection)

    def __getitem__(self, index):
        if isinstance(index, slice):
            view = object.__new__(type(self))
            view.__dict__ = dict(self.__dict__)
            view._selection = self._selection[index]
            return view
        record = self._record_at(index)
        return self._model.from_dict(record) if self._model else record

    def _record_at(self, index):
        identity = self._selection[operator.index(index)]
        raw = self._read_at(
            self._index, self._offset.size, identity * self._offset.size,
        )
        if len(raw) != self._offset.size:
            raise OSError('Truncated backtest history index')
        offset, size = self._offset.unpack(raw)
        payload = self._read_at(self._data, size, offset)
        if len(payload) != size:
            raise OSError('Truncated backtest history record')
        return pickle.loads(payload)

    def __iter__(self):
        for record in self._iter_records():
            yield self._model.from_dict(record) if self._model else record

    def _iter_records(self):
        if self._selection.step != 1:
            for index in range(len(self)):
                yield self._record_at(index)
            return
        payload = b''
        payload_start = 0
        for start in range(self._selection.start, self._selection.stop, 4096):
            count = min(4096, self._selection.stop - start)
            index = self._read_at(
                self._index, count * self._offset.size,
                start * self._offset.size,
            )
            if len(index) != count * self._offset.size:
                raise OSError('Truncated backtest history index')
            for offset, size in self._offset.iter_unpack(index):
                if not (payload_start <= offset and
                        offset + size <= payload_start + len(payload)):
                    payload_start = offset
                    payload = self._read_at(self._data, max(65536, size),
                                            offset)
                relative = offset - payload_start
                record_bytes = payload[relative:relative + size]
                if len(record_bytes) != size:
                    raise OSError('Truncated backtest history record')
                yield pickle.loads(record_bytes)

    def _read_at(self, source, size, offset):
        if hasattr(os, 'pread'):
            return os.pread(source.fileno(), size, offset)
        with self._lock:
            source.seek(offset)
            return source.read(size)

    def __reduce_ex__(self, protocol):
        return (_restore_history, (self._model,), 'sealed', iter(self))

    def append(self, record):
        if not getattr(self, '_restoring', False):
            raise TypeError('Backtest histories are read-only; materialize '
                            'and reassign the history to modify it')
        if self._data is None:
            self._files = _HistoryFiles()
            self._data = self._files.data
            self._index = self._files.index
        payload = pickle.dumps(
            record.to_dict() if self._model else record,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
        offset = self._data.tell()
        self._data.write(payload)
        self._index.write(self._offset.pack(offset, len(payload)))
        self._selection = range(len(self) + 1)

    def extend(self, records):
        if not getattr(self, '_restoring', False):
            raise TypeError('Backtest histories are read-only')
        for record in records:
            self.append(record)

    def __setstate__(self, state):
        if self._data is not None:
            self._data.flush()
            self._index.flush()
        self._restoring = False

    def __copy__(self):
        return self[:]

    def __deepcopy__(self, memo):
        copied = self[:]
        memo[id(self)] = copied
        return copied

    def __eq__(self, other):
        if not isinstance(other, Sequence):
            return NotImplemented
        if len(self) != len(other):
            return False
        return all(before == after for before, after in zip(self, other))

    def materialize(self):
        """Explicitly load detached records into a mutable Python list."""
        return list(self)

    def serialized(self):
        return SerializedHistory(self)

    def __repr__(self):
        return f'{type(self).__name__}(records={len(self)})'


class SerializedHistory(Sequence):
    """Lazy dictionary view consumed by the streaming bundle encoder."""

    def __init__(self, history, transform=None):
        self.history = history
        self.transform = transform

    def __len__(self):
        return len(self.history)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return type(self)(self.history[index], self.transform)
        record = self.history._record_at(index)
        return self.transform(record) if self.transform else record

    def __iter__(self):
        records = self.history._iter_records()
        return map(self.transform, records) if self.transform else records
