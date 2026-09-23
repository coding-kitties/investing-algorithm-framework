from collections.abc import MutableMapping
from datetime import datetime, timezone
import json
import pickle
import sqlite3
from struct import Struct
from tempfile import TemporaryFile

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import set_committed_value


class EventSnapshotArchive(MutableMapping):
    """Private run-local snapshot spool with a disk-resident ID index."""

    _entry = Struct('<QQ')

    def __init__(self, model, state):
        self.model = model
        self.state = state
        self.pending = {}
        self.highest_id = 0
        self.count = 0
        self.records = TemporaryFile()
        try:
            self.index = TemporaryFile()
        except BaseException:
            self.records.close()
            raise

    def _location(self, identity):
        if not isinstance(identity, int):
            return 0, 0
        if not 1 <= identity <= self.highest_id:
            return 0, 0
        self.index.seek((identity - 1) * self._entry.size)
        data = self.index.read(self._entry.size)
        return self._entry.unpack(data) if data else (0, 0)

    def __contains__(self, identity):
        return identity in self.pending or bool(self._location(identity)[1])

    def __getitem__(self, identity):
        if identity in self.pending:
            return self.pending[identity]
        offset, size = self._location(identity)
        if not size:
            raise KeyError(identity)
        return self._read(offset, size)

    def _read(self, offset, size):
        self.records.seek(offset)
        payload = self.records.read(size)
        if len(payload) != size:
            raise OSError('Truncated event snapshot archive')
        fields, relations = pickle.loads(payload)
        mapper = inspect(self.model)
        value = mapper.class_manager.new_instance()
        value.__dict__.update(fields)
        for key, identities in relations.items():
            relation = mapper.relationships[key]
            table = self.state._table(relation.mapper.class_)
            related = [table[item] for item in identities if item in table]
            set_committed_value(value, key, related)
        return value

    def __setitem__(self, identity, value):
        if type(identity) is not int or identity < 1:
            raise ValueError('Snapshot IDs must be positive integers')
        if identity not in self:
            self.count += 1
        self.highest_id = max(self.highest_id, identity)
        self.pending[identity] = value

    def __delitem__(self, identity):
        if identity not in self:
            raise KeyError(identity)
        self._write_location(identity, 0, 0)
        self.pending.pop(identity, None)
        self.count -= 1

    def __iter__(self):
        for identity in range(1, self.highest_id + 1):
            if identity in self:
                yield identity

    def __len__(self):
        return self.count

    def _write_location(self, identity, offset, size):
        self.index.seek((identity - 1) * self._entry.size)
        self.index.write(self._entry.pack(offset, size))

    def flush(self):
        mapper = inspect(self.model)
        for identity, value in self.pending.items():
            fields = {key: item for key, item in value.__dict__.items()
                      if key != '_sa_instance_state'
                      and key not in mapper.relationships}
            relations = {
                relation.key: [item.id for item in
                               value.__dict__[relation.key]]
                for relation in mapper.relationships
                if relation.uselist and relation.lazy in (
                    'joined', 'selectin', 'subquery')
                and relation.key in value.__dict__
            }
            payload = pickle.dumps((fields, relations),
                                   protocol=pickle.HIGHEST_PROTOCOL)
            self.records.seek(0, 2)
            offset = self.records.tell()
            self.records.write(payload)
            self._write_location(identity, offset, len(payload))
        self.pending.clear()

    def close(self):
        self.pending.clear()
        try:
            self.records.close()
        finally:
            self.index.close()


class EventAccountingArchive(EventSnapshotArchive):
    """Disk-backed accounting rows without retained lazy back-references."""

    _query_fields = (
        'status', 'order_id', 'trade_id', 'position_id', 'target_symbol',
        'trading_symbol', 'strategy_id', 'order_side', 'order_type',
        'price', 'amount', 'external_id', 'created_at',
    )

    def __init__(self, model, state):
        super().__init__(model, state)
        self.revision = 0
        self.locations = None
        from investing_algorithm_framework.domain.native_event import \
            native_event_engine
        native = native_event_engine()
        self.native_index = native is not None
        try:
            if self.native_index:
                self.locations = native.EventArchiveIndex()
                return
            self.locations = sqlite3.connect('')
            self.locations.execute('PRAGMA cache_size = -64')
            self.locations.execute('PRAGMA mmap_size = 0')
            self.locations.execute('PRAGMA temp_store = FILE')
            self.locations.execute(
                'CREATE TABLE locations (sequence INTEGER PRIMARY KEY, '
                'identity TEXT UNIQUE, offset INTEGER, size INTEGER, '
                + ', '.join(self._query_fields) + ')')
            for field in ('status', 'order_id', 'trade_id', 'position_id',
                          'created_at'):
                self.locations.execute(
                    f'CREATE INDEX by_{field} ON locations ({field})')
        except BaseException:
            if self.locations is not None:
                self.locations.close()
            super().close()
            raise

    def _location(self, identity):
        if type(identity) is not int:
            return 0, 0
        if self.native_index:
            return self.locations.location(str(identity)) or (0, 0)
        row = self.locations.execute(
            'SELECT offset, size FROM locations WHERE identity = ?',
            (str(identity),),
        ).fetchone()
        return row or (0, 0)

    def _write_location(self, identity, offset, size):
        self.revision += 1
        value = self.pending.get(identity)
        if self.native_index:
            encoded = None if value is None else json.dumps([
                self._query_value(getattr(value, field, None))
                for field in self._query_fields
            ], allow_nan=False)
            self.locations.write(str(identity), offset, size, encoded)
            return
        if value is not None:
            fields = [self._query_value(getattr(value, field, None))
                      for field in self._query_fields]
            assignments = ', '.join(f'{field} = ?'
                                    for field in self._query_fields)
            self.locations.execute(
                f'UPDATE locations SET {assignments} WHERE identity = ?',
                (*fields, str(identity)),
            )
        self.locations.execute(
            'UPDATE locations SET offset = ?, size = ? WHERE identity = ?',
            (offset, size, str(identity)),
        )

    def __setitem__(self, identity, value):
        super().__setitem__(identity, value)
        self.revision += 1
        if self.native_index:
            self.locations.insert(str(identity))
            return
        self.locations.execute(
            'INSERT OR IGNORE INTO locations (identity, offset, size) '
            'VALUES (?, 0, 0)', (str(identity),),
        )

    def __iter__(self):
        cursor = (self.locations.select([], '[]', 0, True)
                  if self.native_index else self.locations.execute(
                      'SELECT identity FROM locations ORDER BY sequence'))
        try:
            for row in cursor:
                identity = int(row[0])
                if identity in self:
                    yield identity
        finally:
            cursor.close()

    @staticmethod
    def _query_value(value):
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.astimezone(timezone.utc)
            return value.isoformat(timespec='microseconds')
        return getattr(value, 'value', value)

    def select(self, params, *, order=False, ascending=False):
        self.flush()
        clauses = ['size > 0']
        fields = []
        parameters = []
        columns = inspect(self.model).columns
        for key in params:
            column = 'created_at' if key == 'created_at_gt' else key
            if (column not in columns
                    or (column not in self._query_fields and key != 'id')):
                continue
            value = params.get(key)
            if value is None:
                continue
            field = 'identity' if key == 'id' else key
            fields.append(field)
            clauses.append('created_at > ?' if key == 'created_at_gt'
                           else f'{field} = ?')
            parameters.append(str(value) if key == 'id'
                              else self._query_value(value))
        ordering = 'sequence'
        if order:
            direction = 'ASC' if ascending else 'DESC'
            ordering = (
                f'created_at {direction}, target_symbol, trading_symbol, '
                'strategy_id, order_side, order_type, price, amount, '
                'length(identity), identity'
            )
        if self.native_index:
            cursor = self.locations.select(
                fields, json.dumps(parameters, allow_nan=False),
                (1 if ascending else -1) if order else 0, False)
        else:
            cursor = self.locations.execute(
                'SELECT identity, offset, size FROM locations WHERE '
                + ' AND '.join(clauses) + f' ORDER BY {ordering}', parameters,
            )
        revision = self.revision
        try:
            for identity, offset, size in cursor:
                yield (self._read(offset, size) if revision == self.revision
                       else self[int(identity)])
        finally:
            cursor.close()

    def close(self):
        try:
            self.locations.close()
        finally:
            super().close()

    def flush(self):
        for value in self.pending.values():
            for relation in inspect(type(value)).relationships:
                if relation.uselist or not relation.back_populates:
                    continue
                parent = value.__dict__.get(relation.key)
                if parent is None:
                    continue
                reverse = inspect(type(parent)).relationships[
                    relation.back_populates]
                if reverse.lazy == 'dynamic':
                    continue
                if reverse.lazy in ('joined', 'selectin', 'subquery'):
                    continue
                related = parent.__dict__.get(reverse.key, ())
                if reverse.uselist:
                    set_committed_value(parent, reverse.key, [
                        item for item in related if item.id != value.id
                    ])
            for relation in inspect(type(value)).relationships:
                if relation.lazy not in ('joined', 'selectin', 'subquery'):
                    value.__dict__.pop(relation.key, None)
        super().flush()
        if not self.native_index:
            self.locations.commit()
