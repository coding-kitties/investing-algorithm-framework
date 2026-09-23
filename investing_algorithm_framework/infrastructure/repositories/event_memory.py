from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import partial, wraps
import operator

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import set_committed_value
from werkzeug.datastructures import MultiDict

from investing_algorithm_framework.domain import OperationalException


_active_state = ContextVar('event_memory_state', default=None)


def event_memory_active():
    return _active_state.get() is not None


def event_memory_routed(method):
    @wraps(method)
    def dispatch(repository, *args, **kwargs):
        state = _active_state.get()
        if state is None:
            return method(repository, *args, **kwargs)
        result = getattr(state, method.__name__)(repository, *args, **kwargs)
        state.flush_snapshots()
        return result
    return dispatch


class EventMemoryState:
    """Run-local detached repository state; accounting stays in services."""

    def __init__(self):
        self.rows = {}
        self.next_ids = {}

    def _table(self, model):
        if model.__name__ in (
            'SQLOrder', 'SQLTrade', 'SQLTradeAllocation',
            'SQLTradeStopLoss', 'SQLTradeTakeProfit',
        ):
            from .event_snapshot_archive import EventAccountingArchive

            if model not in self.rows:
                self.rows[model] = EventAccountingArchive(model, self)
            return self.rows[model]
        if model.__name__ in ('SQLPortfolioSnapshot', 'SQLPositionSnapshot'):
            from .event_snapshot_archive import EventSnapshotArchive

            if model not in self.rows:
                self.rows[model] = EventSnapshotArchive(model, self)
            return self.rows[model]
        return self.rows.setdefault(model, {})

    def flush_snapshots(self):
        from .event_snapshot_archive import EventSnapshotArchive

        for table in self.rows.values():
            if isinstance(table, EventSnapshotArchive):
                table.flush()

    def close(self):
        from .event_snapshot_archive import EventSnapshotArchive

        for table in self.rows.values():
            if isinstance(table, EventSnapshotArchive):
                table.close()
        self.rows.clear()

    @classmethod
    def _clone(cls, value, memo=None, *, eager_only=False):
        from investing_algorithm_framework.infrastructure.database import \
            SQLBaseModel

        memo = {} if memo is None else memo
        if id(value) in memo:
            return memo[id(value)]
        if isinstance(value, SQLBaseModel):
            mapper = inspect(type(value))
            copied = mapper.class_manager.new_instance()
            memo[id(value)] = copied
            for key, item in value.__dict__.items():
                if key == '_sa_instance_state':
                    continue
                if key in mapper.relationships:
                    loading = mapper.relationships[key].lazy
                    if loading == 'dynamic' or (
                            eager_only and loading not in (
                                'joined', 'selectin', 'subquery')):
                        continue
                item = cls._clone(item, memo, eager_only=eager_only)
                if key in mapper.attrs:
                    set_committed_value(copied, key, item)
                else:
                    copied.__dict__[key] = item
            return copied
        if isinstance(value, list):
            copied = []
            memo[id(value)] = copied
            copied.extend(cls._clone(item, memo, eager_only=eager_only)
                          for item in value)
            return copied
        if isinstance(value, dict):
            copied = {}
            memo[id(value)] = copied
            copied.update((key, cls._clone(item, memo, eager_only=eager_only))
                          for key, item in value.items())
            return copied
        return deepcopy(value, memo)

    @staticmethod
    def _normalize(value):
        from investing_algorithm_framework.infrastructure.database import \
            SqliteDecimal

        for column in inspect(type(value)).columns:
            current = getattr(value, column.key, None)
            if current is not None and isinstance(column.type, SqliteDecimal):
                set_committed_value(value, column.key, float(current))
        if 'metadata_json' in inspect(type(value)).columns:
            value.init_on_load()

    def _adopt(self, value):
        model = type(value)
        table = self._table(model)
        identity = getattr(value, 'id', None)
        if identity is not None and identity in table:
            return table[identity]
        if identity is None:
            identity = self.next_ids.get(model, 1)
            value.id = identity
        self.next_ids[model] = max(self.next_ids.get(model, 1), identity + 1)
        table[identity] = value
        mapper = inspect(model)
        for column in mapper.columns:
            if getattr(value, column.key, None) is None \
                    and column.default is not None:
                default = column.default
                if default.is_scalar:
                    setattr(value, column.key, deepcopy(default.arg))
        self._normalize(value)
        for relation in mapper.relationships:
            if relation.key in value.__dict__:
                related = getattr(value, relation.key)
                if relation.uselist:
                    setattr(value, relation.key, [
                        self._adopt(item) for item in list(related)
                    ])
                elif related is not None:
                    setattr(value, relation.key, self._adopt(related))
            elif relation.direction.name == 'MANYTOONE':
                for local, remote in relation.local_remote_pairs:
                    identity = getattr(value, local.key, None)
                    related = self._table(relation.mapper.class_).get(identity)
                    if related is not None:
                        reverse = (inspect(type(related)).relationships[
                            relation.back_populates]
                            if relation.back_populates else None)
                        if reverse is not None and reverse.lazy in (
                                'joined', 'selectin', 'subquery'):
                            setattr(value, relation.key, related)
                        else:
                            set_committed_value(value, relation.key, related)
                        self._table(type(related))[related.id] = related
            if relation.direction.name == 'MANYTOONE':
                related = getattr(value, relation.key, None)
                if related is not None:
                    for local, remote in relation.local_remote_pairs:
                        setattr(value, local.key, getattr(related, remote.key))
        return value

    def create(self, repository, data, save=True):
        value = repository.base_class(**self._clone(data))
        if not save:
            return value
        return self._clone(self._adopt(value), eager_only=True)

    def _get(self, repository, identity):
        try:
            return self._table(repository.base_class)[identity]
        except KeyError:
            raise OperationalException(repository.DEFAULT_NOT_FOUND_MESSAGE)

    def get(self, repository, object_id):
        return self._read_result(self._get(repository, object_id))

    def _read_result(self, value):
        from .event_snapshot_archive import EventSnapshotArchive

        if isinstance(self._table(type(value)), EventSnapshotArchive) and \
                not any(table.pending for table in self.rows.values()
                        if isinstance(table, EventSnapshotArchive)):
            return value
        return self._clone(value, eager_only=True)

    def update(self, repository, object_id, data):
        from .repository import convert_datetime_fields

        value = self._get(repository, object_id)
        changes = convert_datetime_fields(self._clone(data), [
            'created_at', 'updated_at', 'closed_at', 'opened_at',
            'triggered_at',
        ])
        for relation in inspect(type(value)).relationships:
            if relation.key in changes:
                related = changes[relation.key]
                changes[relation.key] = (
                    [self._adopt(item) for item in related]
                    if relation.uselist else self._adopt(related)
                )
        value.update(changes)
        self._normalize(value)
        self._table(type(value))[value.id] = value
        return self._clone(self._save(value, set()), eager_only=True)

    def _select(self, repository, query_params=None):
        from investing_algorithm_framework.infrastructure.models import \
            SQLOrder, SQLPosition, SQLPortfolio, SQLTrade

        model = repository.base_class
        params = MultiDict(query_params)
        for key in list(params):
            if params.get(key) is None:
                del params[key]
        from .event_snapshot_archive import (
            EventAccountingArchive, EventSnapshotArchive,
        )

        table = self._table(model)
        values = iter(table.values()) if isinstance(
            table, EventSnapshotArchive) else list(table.values())
        allowed = {
            'SQLPortfolio': {'id', 'market', 'identifier', 'position'},
            'SQLPosition': {
                'id', 'amount', 'symbol', 'portfolio', 'amount_gt',
                'amount_gte', 'amount_lt', 'amount_lte', 'order_id',
            },
            'SQLOrder': {
                'id', 'external_id', 'portfolio_id', 'order_side',
                'order_type', 'status', 'price', 'amount', 'position',
                'target_symbol', 'trading_symbol', 'order_by_created_at_asc',
                'created_at_gt',
            },
            'SQLTrade': {
                'portfolio_id', 'status', 'target_symbol', 'trading_symbol',
                'order_id',
            },
            'SQLTradeAllocation': {'order_id', 'trade_id'},
            'SQLTradeStopLoss': {'trade_id', 'triggered'},
            'SQLTradeTakeProfit': {'trade_id', 'triggered'},
            'SQLPortfolioSnapshot': {
                'portfolio_id', 'created_at', 'created_at_gt',
                'created_at_gte', 'created_at_lt', 'created_at_lte',
            },
            'SQLPositionSnapshot': {'portfolio_snapshot'},
        }.get(model.__name__)
        if allowed is None or set(params) - allowed:
            raise OperationalException(
                f'Unsupported event memory query: {model.__name__} {params}'
            )
        if isinstance(table, EventAccountingArchive):
            values = table.select(
                {key: repository.get_query_param(key, params)
                 for key in params}, order=model is SQLOrder,
                ascending=repository.get_query_param(
                    'order_by_created_at_asc', params),
            )
        for key in params:
            if key == 'order_by_created_at_asc':
                continue
            expected = repository.get_query_param(key, params)
            if expected is None:
                continue
            expected = getattr(expected, 'value', expected)
            if model is SQLOrder and key == 'portfolio_id':
                positions = self._table(SQLPosition)
                values = filter(partial(
                    self._matches_portfolio, positions=positions,
                    expected=expected, trade=False), values)
            elif model is SQLTrade and key == 'portfolio_id':
                if expected not in self._table(SQLPortfolio):
                    raise OperationalException('Portfolio not found')
                positions = self._table(SQLPosition)
                values = filter(partial(
                    self._matches_portfolio, positions=positions,
                    expected=expected, trade=True), values)
            elif key == 'order_id' and model is SQLTrade:
                values = filter(partial(
                    self._matches_order, expected=expected), values)
            elif key == 'order_id' and model is SQLPosition:
                order = self._table(SQLOrder).get(expected)
                values = [value for value in values if order is not None
                          and value.id == order.position_id]
            elif model is SQLPortfolio and key == 'position':
                position = self._table(SQLPosition).get(expected)
                values = [value for value in values
                          if position is not None
                          and value.id == position.portfolio_id]
            elif model is SQLOrder and key == 'position':
                identities = repository.get_query_param(key, params, many=True)
                values = filter(partial(
                    self._matches_attribute, attribute='position_id',
                    compare=lambda actual, expected: actual in expected,
                    expected=identities), values)
            else:
                attribute = {'portfolio': 'portfolio_id',
                             'portfolio_snapshot': 'portfolio_snapshot_id'} \
                    .get(key, key)
                compare = operator.eq
                for suffix, comparison in (
                    ('_gte', operator.ge), ('_lte', operator.le),
                    ('_gt', operator.gt), ('_lt', operator.lt),
                ):
                    if attribute.endswith(suffix):
                        attribute = attribute[:-len(suffix)]
                        compare = comparison
                        break
                if model is SQLPortfolio and key in ('market', 'identifier'):
                    expected = expected.upper()
                values = filter(partial(
                    self._matches_attribute, attribute=attribute,
                    compare=compare, expected=expected), values)
        if model is SQLOrder and not isinstance(table, EventAccountingArchive):
            values = list(values)
            values.sort(key=self._order_key)
            ascending = repository.get_query_param(
                'order_by_created_at_asc', params)
            values.sort(key=lambda value: value.created_at,
                        reverse=not ascending)
        return values

    @staticmethod
    def _matches_portfolio(value, *, positions, expected, trade):
        orders = value.orders if trade else (value,)
        return any(order.position_id in positions
                   and positions[order.position_id].portfolio_id == expected
                   for order in orders)

    @staticmethod
    def _matches_order(value, *, expected):
        return any(order.id == expected for order in value.orders)

    @staticmethod
    def _matches_attribute(value, *, attribute, compare, expected):
        actual = getattr(value, attribute)
        return actual is not None and compare(actual, expected)

    @staticmethod
    def _order_key(value):
        return tuple((getattr(value, key) is not None, getattr(value, key))
                     for key in (
                         'created_at', 'target_symbol', 'trading_symbol',
                         'strategy_id', 'order_side', 'order_type', 'price',
                         'amount', 'id',
                     ))

    def get_all(self, repository, query_params=None):
        return [self._read_result(value)
                for value in self._select(repository, query_params)]

    def iter_all(self, repository, query_params=None, batch_size=256):
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError('batch_size must be a positive integer')
        for value in self._select(repository, query_params):
            yield self._read_result(value)

    def count(self, repository, query_params=None):
        return sum(1 for _ in self._select(repository, query_params))

    def exists(self, repository, query_params):
        return next(iter(self._select(repository, query_params)), None) \
            is not None

    def find(self, repository, query_params):
        if not query_params:
            raise OperationalException('Find requires query parameters')
        value = next(iter(self._select(repository, query_params)), None)
        if value is None:
            raise OperationalException(repository.DEFAULT_NOT_FOUND_MESSAGE)
        return self._read_result(value)

    def add_order_to_trade(self, repository, trade, order):
        stored = self._get(repository, trade.id)
        order = self._table(type(order))[order.id]
        if all(item.id != order.id for item in stored.orders):
            stored.orders.append(order)
            stored.orders.sort(key=self._order_key)
        self._table(type(stored))[stored.id] = stored
        return self._clone(stored, eager_only=True)

    def _save(self, value, visited):
        model = type(value)
        identity = getattr(value, 'id', None)
        stored = self._table(model).get(identity)
        if stored is None:
            return self._adopt(self._clone(value))
        if id(value) in visited:
            return stored
        visited.add(id(value))
        state = inspect(value)
        for attribute in state.mapper.column_attrs:
            key = attribute.key
            if state.attrs[key].history.has_changes():
                set_committed_value(stored, key,
                                    self._clone(getattr(value, key)))
        for relation in state.mapper.relationships:
            if relation.key not in value.__dict__ \
                    or relation.lazy == 'dynamic':
                continue
            related = getattr(value, relation.key)
            if relation.uselist:
                related = [self._save(item, visited) for item in related]
            elif related is not None:
                related = self._save(related, visited)
            if state.attrs[relation.key].history.has_changes():
                setattr(stored, relation.key, related)
            else:
                set_committed_value(stored, relation.key, related)
        self._normalize(stored)
        self._table(model)[identity] = stored
        return stored

    def save(self, repository, object_to_save):
        return self._clone(self._save(object_to_save, set()), eager_only=True)

    def save_objects(self, repository, objects):
        return [self.save(repository, value) for value in objects]

    def delete(self, repository, object_id):
        value = self._get(repository, object_id)
        for relation in inspect(type(value)).relationships:
            if relation.direction.name == 'MANYTOONE':
                setattr(value, relation.key, None)
            elif relation.uselist and relation.lazy != 'dynamic':
                setattr(value, relation.key, [])
        del self._table(repository.base_class)[object_id]
        return self._clone(value, eager_only=True)

    def delete_all(self, repository, query_params):
        if query_params is None:
            raise OperationalException('No parameters are required')
        for value in self._select(repository, query_params):
            self.delete(repository, value.id)

    def update_all(self, repository, query_params, data):
        for value in self._select(repository, query_params):
            self.update(repository, value.id, data)
            self.flush_snapshots()


@contextmanager
def event_memory_scope(accounting_backend='python'):
    if _active_state.get() is not None:
        raise OperationalException(
            'Nested event memory scopes are unsupported')
    state = EventMemoryState()
    token = _active_state.set(state)
    try:
        from investing_algorithm_framework.domain.native_event import \
            native_event_scope
        with native_event_scope(accounting_backend):
            yield state
    finally:
        _active_state.reset(token)
        state.close()
