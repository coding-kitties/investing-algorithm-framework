from unittest import TestCase
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import gc
import sqlite3
import tracemalloc
import weakref

from sqlalchemy import inspect

from investing_algorithm_framework.domain import OrderSide, OrderStatus, \
    OrderType
from investing_algorithm_framework.infrastructure.models import \
    SQLOrder, SQLTradeAllocation
from investing_algorithm_framework.infrastructure.repositories.event_memory \
    import event_memory_scope
from investing_algorithm_framework.infrastructure.repositories \
    .order_repository import SQLOrderRepository
from investing_algorithm_framework.infrastructure.repositories \
    .position_repository import SQLPositionRepository
from investing_algorithm_framework.infrastructure.repositories \
    .trade_repository import SQLTradeRepository


class TestEventMemoryState(TestCase):
    def test_created_after_filters_before_decode_in_both_archives(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .event_snapshot_archive import EventAccountingArchive

        watermark = datetime(2026, 1, 2, tzinfo=timezone.utc)
        for backend in ('python', 'rust'):
            with self.subTest(backend=backend):
                if backend == 'rust':
                    from investing_algorithm_framework.domain.native_event \
                        import load_native_event_accounting
                    try:
                        load_native_event_accounting()
                    except ImportError:
                        continue
                orders = SQLOrderRepository()
                with event_memory_scope(accounting_backend=backend) as state:
                    for identity, created_at in enumerate((
                        watermark - timedelta(days=1), watermark,
                        (watermark + timedelta(microseconds=1)).astimezone(
                            timezone(timedelta(hours=-5))),
                        watermark + timedelta(days=1),
                    ), 1):
                        orders.create({
                            'id': identity, 'target_symbol': 'BTC',
                            'trading_symbol': 'EUR',
                            'amount': 1., 'price': 10.,
                            'order_type': OrderType.LIMIT,
                            'order_side': OrderSide.BUY,
                            'created_at': created_at,
                        })
                    table = state.rows[SQLOrder]
                    with patch.object(table, '_read', wraps=table._read) \
                            as decode:
                        selected = orders.get_all({
                            'created_at_gt': watermark,
                            'order_by_created_at_asc': True,
                        })
                        self.assertEqual([row.id for row in selected], [3, 4])
                        self.assertEqual(decode.call_count, 2)
                    self.assertIsInstance(table, EventAccountingArchive)
                    self.assertEqual(orders.get_all({
                        'created_at_gt': watermark + timedelta(days=2),
                    }), [])

    def test_archive_hydration_preserves_history_and_save_tracking(self):
        orders = SQLOrderRepository()
        with event_memory_scope():
            order = orders.create({
                'target_symbol': 'BTC', 'trading_symbol': 'EUR',
                'amount': 1.0, 'price': 10.0,
                'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
            })
            restored = orders.get(order.id)
            loaded = inspect(restored)
            self.assertFalse(loaded.modified)
            self.assertTrue(all(not attribute.history.has_changes()
                                for attribute in loaded.attrs))
            restored.price = 12.0
            self.assertTrue(loaded.attrs.price.history.has_changes())
            self.assertEqual(orders.get(order.id).price, 10.0)
            orders.save(restored)
            saved = orders.get(order.id)
            self.assertEqual(saved.price, 12.0)
            self.assertFalse(inspect(saved).modified)
            self.assertFalse(inspect(saved).attrs.price.history.has_changes())

    def test_native_index_filters_streams_and_observes_updates(self):
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting

        try:
            native = load_native_event_accounting()
        except ImportError:
            self.skipTest('Native extension is not installed')
        orders = SQLOrderRepository()
        with patch('sqlite3.connect', side_effect=AssertionError(
                'Rust archives must not use the Python SQLite driver')):
            with event_memory_scope(accounting_backend='rust') as state:
                for identity in range(1, 301):
                    orders.create({
                        'id': 10**18 + identity, 'target_symbol': 'BTC',
                        'trading_symbol': 'EUR', 'amount': 1.0, 'price': 10.0,
                        'status': OrderStatus.OPEN if identity % 2
                        else OrderStatus.CLOSED,
                        'order_type': OrderType.LIMIT,
                        'order_side': OrderSide.BUY,
                        'created_at': datetime(
                            2026, 1, 1, tzinfo=timezone.utc),
                    })
                table = state.rows[SQLOrder]
                self.assertIsInstance(
                    table.locations, native.EventArchiveIndex)
                selected = table.select({'status': OrderStatus.OPEN},
                                        order=True, ascending=True)
                self.assertEqual(next(selected).id, 10**18 + 1)
                orders.update(10**18 + 3, {'price': 12.0})
                changed = next(selected)
                self.assertEqual((changed.id, changed.price),
                                 (10**18 + 3, 12.0))
                self.assertEqual(len(list(selected)), 148)
                orders.update(10**18 + 5, {'price': 12.0})
                small = table.select({'price': 12.0})
                self.assertEqual(next(small).id, 10**18 + 3)
                orders.update(10**18 + 5, {'price': 13.0})
                self.assertEqual(next(small).price, 13.0)
                self.assertEqual(list(small), [])
                self.assertEqual([item.id for item in table.select({
                    'price': 12.0,
                })], [10**18 + 3])
                self.assertEqual(len(list(table)), 300)
                orders.delete(10**18 + 2)
                self.assertEqual(orders.count(), 299)
                cursor = table.locations.select([], '[]', 0, False)
                next(cursor)
            self.assertTrue(table.records.closed)
            with self.assertRaisesRegex(RuntimeError, 'closed'):
                table.locations.location(str(10**18 + 1))
            cursor.close()

    def test_archive_iteration_observes_interleaved_updates(self):
        orders = SQLOrderRepository()
        with event_memory_scope():
            for identity in range(1, 4):
                orders.create({
                    'id': identity, 'target_symbol': 'BTC',
                    'trading_symbol': 'EUR', 'amount': 1.0, 'price': 10.0,
                    'created_at': datetime(2026, 1, identity,
                                           tzinfo=timezone.utc),
                    'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
                })
            stream = orders.iter_all({'order_by_created_at_asc': True})
            self.assertEqual(next(stream).id, 1)
            orders.update(2, {'price': 12.0})
            changed = next(stream)
            self.assertEqual(changed.id, 2)
            self.assertEqual(changed.price, 12.0)
            self.assertEqual(next(stream).id, 3)
            with self.assertRaises(StopIteration):
                next(stream)

    def test_accounting_selection_reads_locations_in_one_query(self):
        orders = SQLOrderRepository()
        with event_memory_scope() as state:
            for identity in range(1, 11):
                orders.create({
                    'id': identity, 'target_symbol': 'BTC',
                    'trading_symbol': 'EUR', 'amount': 1.0, 'price': 10.0,
                    'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
                })
            table = state.rows[SQLOrder]
            statements = []
            table.locations.set_trace_callback(statements.append)
            selected = list(table.select({}))
            self.assertEqual([item.id for item in selected],
                             list(range(1, 11)))
            self.assertEqual(len(statements), 1, statements)
            selected[0].price = 99.0
            self.assertEqual(orders.get(1).price, 10.0)

    def test_normalization_preserves_both_position_legs(self):
        positions = SQLPositionRepository()
        with event_memory_scope():
            position = positions.create({
                'symbol': 'BTC', 'portfolio_id': 1,
                'long_amount': 2.0, 'long_cost': 20.0,
                'short_amount': 3.0, 'short_cost': 45.0,
            })
            positions.update(position.id, {'long_amount': 1.0})
            restored = positions.get(position.id)
            self.assertEqual(restored.long_amount, 1.0)
            self.assertEqual(restored.short_amount, 3.0)
            self.assertEqual(restored.long_cost, 20.0)
            self.assertEqual(restored.short_cost, 45.0)

    def test_order_archive_filters_before_decode_and_streams_portfolio(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .event_snapshot_archive import EventAccountingArchive

        orders = SQLOrderRepository()
        positions = SQLPositionRepository()
        with event_memory_scope() as state:
            position = positions.create({
                'symbol': 'BTC', 'amount': 0.0, 'portfolio_id': 7,
            })
            for identity in range(1, 1002):
                orders.create({
                    'id': identity, 'target_symbol': 'BTC',
                    'trading_symbol': 'EUR', 'amount': 1.0, 'price': 10.0,
                    'position_id': position.id,
                    'status': OrderStatus.CLOSED if identity < 1001
                    else OrderStatus.OPEN,
                    'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
                    'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc),
                })
            original = EventAccountingArchive._read
            references = []

            def decode(archive, offset, size):
                value = original(archive, offset, size)
                references.append(weakref.ref(value))
                self.assertLess(sum(ref() is not None for ref in references),
                                5)
                return value

            with patch.object(EventAccountingArchive, '_read', decode):
                self.assertEqual(orders.count({'status': OrderStatus.OPEN}), 1)
                self.assertEqual(len(references), 1)
                self.assertEqual(orders.count({'portfolio_id': 7}), 1001)
                self.assertEqual(sum(1 for _ in orders.iter_all({
                    'portfolio_id': 7, 'position': [position.id],
                })), 1001)
            self.assertTrue(all(ref() is None for ref in references))
            self.assertEqual(state.rows[SQLOrder].pending, {})

    def test_accounting_archive_retained_memory_does_not_scale_with_rows(self):
        orders = SQLOrderRepository()
        trades = SQLTradeRepository()
        with event_memory_scope() as state:
            tracemalloc.start()
            try:
                retained = []
                for identity in range(1, 1001):
                    order = orders.create({
                        'id': identity, 'target_symbol': 'BTC',
                        'trading_symbol': 'EUR', 'amount': 1.0, 'price': 10.0,
                        'order_type': OrderType.LIMIT,
                        'order_side': OrderSide.BUY,
                    })
                    trades.create({
                        'buy_order': order, 'target_symbol': 'BTC',
                        'trading_symbol': 'EUR', 'opened_at': order.created_at,
                        'amount': 1.0, 'available_amount': 0.0,
                        'filled_amount': 1.0, 'remaining': 0.0,
                    })
                    del order
                    if identity in (100, 1000):
                        gc.collect()
                        retained.append(tracemalloc.get_traced_memory()[0])
                self.assertLess(retained[1] - retained[0], 256 * 1024)
                self.assertTrue(all(not table.pending
                                    for table in state.rows.values()
                                    if not isinstance(table, dict)))
                table = state.rows[SQLOrder]
            finally:
                tracemalloc.stop()
        self.assertTrue(table.records.closed)
        with self.assertRaises(sqlite3.ProgrammingError):
            table.locations.execute('SELECT 1')

    def test_accounting_archive_sparse_order_ids(self):
        orders = SQLOrderRepository()
        with event_memory_scope() as state:
            for identity in (10**15, 3, 10**16):
                orders.create({
                    'id': identity, 'target_symbol': 'BTC',
                    'trading_symbol': 'EUR', 'amount': 1.0, 'price': 10.0,
                    'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
                })
            self.assertEqual(orders.count(), 3)
            table = state.rows[SQLOrder]
            self.assertEqual(list(table), [10**15, 3, 10**16])
            self.assertLess(table.records.seek(0, 2), 10000)
            self.assertEqual(table.index.seek(0, 2), 0)
            orders.update(10**15, {'price': 12.0})
            self.assertEqual(orders.get(10**15).price, 12.0)
            orders.delete(3)
            self.assertEqual(orders.count(), 2)

    def test_allocation_archive_releases_rows_and_preserves_late_updates(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .trade_allocation_repository import SQLTradeAllocationRepository

        orders = SQLOrderRepository()
        allocations = SQLTradeAllocationRepository()
        references = []
        with event_memory_scope() as state:
            order = orders.create({
                'target_symbol': 'BTC', 'trading_symbol': 'EUR',
                'amount': 1000.0, 'price': 10.0,
                'order_type': OrderType.LIMIT, 'order_side': OrderSide.SELL,
            })
            original = state._clone

            def capture(value, *args, **kwargs):
                if isinstance(value, SQLTradeAllocation):
                    references.append(weakref.ref(value))
                return original(value, *args, **kwargs)

            with patch.object(state, '_clone', side_effect=capture):
                for number in range(1000):
                    allocations.create({
                        'order_id': order.id, 'trade_id': number + 1,
                        'amount': 1.0, 'amount_pending': 0.0,
                        'open_price': 8.0, 'close_price': 10.0,
                        'net_gain_contribution': 2.0,
                    })
            gc.collect()
            self.assertTrue(all(ref() is None for ref in references))
            table = state.rows[SQLTradeAllocation]
            self.assertEqual(table.pending, {})
            self.assertEqual(state.rows[SQLOrder][order.id].trade_allocations,
                             [])
            self.assertEqual(allocations.count({'order_id': order.id}), 1000)
            allocations.update(1, {'sell_fee': 0.25,
                                   'net_gain_contribution': 1.75})
            restored = allocations.find({'trade_id': 1})
            self.assertEqual(restored.sell_fee, 0.25)
            self.assertEqual(restored.net_gain_contribution, 1.75)
            restored.buy_fee = 0.1
            allocations.save(restored)
            self.assertEqual(allocations.get(1).buy_fee, 0.1)
            allocations.delete(2)
            self.assertEqual(allocations.count({'order_id': order.id}), 999)
        self.assertTrue(table.records.closed)
        self.assertTrue(table.index.closed)

    def test_snapshot_archive_releases_rows_and_preserves_updates(self):
        from investing_algorithm_framework.infrastructure.models import \
            SQLPortfolioSnapshot, SQLPositionSnapshot
        from investing_algorithm_framework.infrastructure.repositories \
            .portfolio_snapshot_repository import (
                SQLPortfolioSnapshotRepository,
            )
        from investing_algorithm_framework.infrastructure.repositories \
            .position_snapshot_repository import SQLPositionSnapshotRepository
        from investing_algorithm_framework.infrastructure.repositories \
            .event_snapshot_archive import EventSnapshotArchive

        snapshots = SQLPortfolioSnapshotRepository()
        positions = SQLPositionSnapshotRepository()
        references = []
        flush = EventSnapshotArchive.flush

        def capture_flush(archive):
            references.extend(weakref.ref(value)
                              for value in archive.pending.values())
            flush(archive)

        with event_memory_scope() as state, patch.object(
                EventSnapshotArchive, 'flush', capture_flush):
            for number in range(100):
                snapshot = snapshots.create({
                    'portfolio_id': 'test', 'trading_symbol': 'EUR',
                    'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc),
                    'total_value': float(number),
                    'position_snapshots': [SQLPositionSnapshot(
                        symbol='BTC', amount=1.0, cost=10.0)],
                })
                references.append(weakref.ref(snapshot))
                del snapshot
            gc.collect()
            self.assertTrue(all(
                reference() is None for reference in references))
            table = state.rows[SQLPortfolioSnapshot]
            self.assertEqual(len(table), 100)
            self.assertEqual(table.pending, {})
            self.assertEqual(state.rows[SQLPositionSnapshot].pending, {})
            first = snapshots.get(1)
            self.assertEqual(first.total_value, 0.0)
            self.assertEqual(first.position_snapshots[0].symbol, 'BTC')
            positions.update(first.position_snapshots[0].id, {'amount': 2.0})
            self.assertEqual(
                snapshots.get(1).position_snapshots[0].amount, 2.0)
            first.total_value = 123.0
            snapshots.save(first)
            self.assertEqual(snapshots.get(1).total_value, 123.0)
            self.assertEqual(
                snapshots.get(1).position_snapshots[0].amount, 2.0)
            self.assertEqual(snapshots.get(100).total_value, 99.0)
            edited = snapshots.get(1)
            edited.position_snapshots[0].amount = 4.0
            saved = snapshots.save(edited)
            self.assertEqual(saved.position_snapshots[0].amount, 4.0)
            self.assertEqual(
                snapshots.get(1).position_snapshots[0].amount, 4.0)
            positions.create({
                'portfolio_snapshot_id': 100, 'symbol': 'ETH',
                'amount': 3.0, 'cost': 20.0,
            })
            self.assertEqual(
                [item.symbol for item in
                 snapshots.get(100).position_snapshots],
                ['BTC', 'ETH'],
            )
            self.assertEqual(snapshots.count({'portfolio_id': 'test'}), 100)
            self.assertFalse(snapshots.exists({'portfolio_id': 'other'}))
            self.assertEqual(snapshots.find({'portfolio_id': 'test'}).id, 1)
            self.assertEqual(snapshots.get_all({'portfolio_id': 'other'}), [])
        self.assertTrue(table.records.closed)
        self.assertTrue(table.index.closed)

    def test_snapshot_archive_scope_closes_after_failure(self):
        from investing_algorithm_framework.infrastructure.models import \
            SQLPortfolioSnapshot

        with self.assertRaisesRegex(RuntimeError, 'abort'):
            with event_memory_scope() as state:
                table = state._table(SQLPortfolioSnapshot)
                raise RuntimeError('abort')
        self.assertTrue(table.records.closed)
        self.assertTrue(table.index.closed)

    def test_snapshot_archive_queries_do_not_retain_scanned_rows(self):
        from investing_algorithm_framework.infrastructure.models import \
            SQLPortfolioSnapshot
        from investing_algorithm_framework.infrastructure.repositories \
            .portfolio_snapshot_repository import (
                SQLPortfolioSnapshotRepository,
            )

        snapshots = SQLPortfolioSnapshotRepository()
        references = []
        with event_memory_scope() as state:
            for number in range(1000):
                snapshots.create({
                    'portfolio_id': 'test', 'trading_symbol': 'EUR',
                    'created_at': datetime(2026, 1, 1),
                    'total_value': float(number),
                })
            original = state._matches_attribute

            def matches(value, **kwargs):
                references.append(weakref.ref(value))
                self.assertLess(sum(reference() is not None
                                    for reference in references), 5)
                return original(value, **kwargs)

            with patch.object(state, '_matches_attribute', matches):
                self.assertEqual(
                    snapshots.count({'portfolio_id': 'test'}), 1000)
            self.assertEqual(state.rows[SQLPortfolioSnapshot].pending, {})
            self.assertTrue(all(
                reference() is None for reference in references))

    def test_order_read_does_not_clone_allocation_history(self):
        repository = SQLOrderRepository()
        with event_memory_scope() as state:
            order = repository.create({
                'target_symbol': 'BTC', 'trading_symbol': 'EUR',
                'amount': 100.0, 'price': 10.0,
                'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
            })
            for number in range(100):
                state._adopt(SQLTradeAllocation(
                    order_id=order.id, amount=1.0, amount_pending=0.0,
                    trade_id=number + 1,
                ))
            canonical = state.rows[SQLOrder][order.id]
            self.assertEqual(len(canonical.trade_allocations), 0)
            self.assertEqual(len(state.rows[SQLTradeAllocation]), 100)
            memo = {}
            copied = state._clone(canonical, memo, eager_only=True)
            model_count = sum(isinstance(value, (SQLOrder, SQLTradeAllocation))
                              for value in memo.values())
            self.assertEqual(model_count, 1)
            self.assertIn('trade_allocations', inspect(copied).unloaded)
            self.assertIn('trade_allocations',
                          inspect(repository.get(order.id)).unloaded)
            copied.amount = 1.0
            self.assertEqual(repository.get(order.id).amount, 100.0)

    def test_trade_read_keeps_eager_orders_and_detached_metadata(self):
        orders = SQLOrderRepository()
        trades = SQLTradeRepository()
        with event_memory_scope() as state:
            order = orders.create({
                'target_symbol': 'BTC', 'trading_symbol': 'EUR',
                'amount': 1.0, 'price': 10.0,
                'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
                'metadata': {'nested': {'value': 1}},
            })
            trade = trades.create({
                'buy_order': order, 'target_symbol': 'BTC',
                'trading_symbol': 'EUR', 'opened_at': order.created_at,
                'amount': 1.0, 'available_amount': 1.0,
                'filled_amount': 1.0, 'remaining': 0.0,
            })
            with patch.object(state, '_clone', side_effect=AssertionError(
                    'Decoded archive rows must not be copied again')):
                copied = trades.get(trade.id)
                self.assertEqual(trades.get_all()[0].id, trade.id)
                self.assertEqual(next(trades.iter_all()).id, trade.id)
                self.assertEqual(trades.find({'order_id': order.id}).id,
                                 trade.id)
            self.assertEqual([item.id for item in copied.orders], [order.id])
            self.assertEqual(trades.find({'order_id': order.id}).id, trade.id)
            trades.add_order_to_trade(trade, order)
            self.assertEqual(len(trades.get(trade.id).orders), 1)
            self.assertIn('trades', inspect(copied.orders[0]).unloaded)
            copied.orders[0].metadata['nested']['value'] = 2
            self.assertEqual(
                orders.get(order.id).metadata['nested']['value'], 1)
            copied.orders[0].price = 12.0
            trades.save(copied)
            self.assertEqual(orders.get(order.id).price, 12.0)

    def test_pending_archive_reads_still_detach_nested_objects(self):
        orders = SQLOrderRepository()
        trades = SQLTradeRepository()
        with event_memory_scope() as state:
            order = orders.create({
                'target_symbol': 'BTC', 'trading_symbol': 'EUR',
                'amount': 1.0, 'price': 10.0,
                'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
                'metadata': {'nested': {'value': 1}},
            })
            trade = trades.create({
                'buy_order': order, 'target_symbol': 'BTC',
                'trading_symbol': 'EUR', 'opened_at': order.created_at,
                'amount': 1.0, 'available_amount': 1.0,
                'filled_amount': 1.0, 'remaining': 0.0,
            })
            state._table(SQLOrder)[order.id] = order
            copied = state.get(trades, trade.id)
            copied.orders[0].metadata['nested']['value'] = 99
            self.assertEqual(order.metadata['nested']['value'], 1)
            state.flush_snapshots()
            self.assertEqual(orders.get(order.id).metadata['nested']['value'],
                             1)

    def test_shared_detached_state_and_scope_cleanup(self):
        first = SQLPositionRepository()
        second = SQLPositionRepository()
        target = 'investing_algorithm_framework.infrastructure.repositories.' \
            'repository.Session'
        with patch(target, side_effect=AssertionError('SQL was used')):
            with event_memory_scope():
                created = first.create({
                    'symbol': 'EUR', 'amount': 1000.0, 'portfolio_id': 1,
                })
                before = first.get(created.id)
                updated = second.update(created.id, {'amount': 900.0})
                self.assertEqual(updated.amount, 900.0)
                self.assertEqual(before.amount, 1000.0)
                updated.amount = 1.0
                self.assertEqual(first.get(created.id).amount, 900.0)
            with self.assertRaisesRegex(AssertionError, 'SQL was used'):
                first.get(created.id)
