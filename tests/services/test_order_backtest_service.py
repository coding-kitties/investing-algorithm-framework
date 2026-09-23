from datetime import datetime, timezone
from copy import deepcopy
from itertools import product
import random
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, INDEX_DATETIME, BacktestDateRange
from investing_algorithm_framework.services import OrderBacktestService
from tests.resources import TestBase


class TestNativeEventTransitions(TestCase):
    def setUp(self):
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting
        try:
            self.native = load_native_event_accounting()
        except ImportError:
            self.skipTest('Optional native extension is not installed')

    def test_native_reservations_match_python_heap_order(self):
        from queue import PriorityQueue

        class Candidate:
            def __init__(self, index, opened):
                self.index = index
                self.opened = opened

            def __lt__(self, other):
                return self.opened < other.opened

        randomizer = random.Random(20260923)
        for iteration in range(100):
            with self.subTest(iteration=iteration):
                rows = [(randomizer.randrange(4),
                         randomizer.uniform(0.01, 10),
                         randomizer.choice((False, False, True)))
                        for _ in range(30)]
                queue = PriorityQueue()
                total = 0
                for index, (opened, available, short) in enumerate(rows):
                    if not short:
                        total += available
                        queue.put(Candidate(index, opened))
                amount = total * randomizer.random()
                remaining = amount
                expected = []
                while remaining > 0 and not queue.empty():
                    index = queue.get().index
                    portion = min(remaining, rows[index][1])
                    expected.append((index, portion, rows[index][1] - portion))
                    remaining -= portion
                self.assertEqual(self.native.event_reservation_plan(
                    rows, amount, None), expected)
                with self.assertRaisesRegex(ValueError, 'Not enough'):
                    self.native.event_reservation_plan(rows, total + 1, None)
        self.assertEqual(self.native.event_reservation_plan(
            [(0, 5.0, False)], 3.0, [(0, 1.0), (0, 2.0)]),
            [(0, 1.0, 4.0), (0, 2.0, 2.0)])

    def test_batch_exit_plans_match_sequential_python_exactly(self):
        randomizer = random.Random(20260922)
        for iteration in range(100):
            with self.subTest(iteration=iteration):
                rows = [(
                    randomizer.uniform(0.1, 10),
                    randomizer.uniform(10, 1000),
                    randomizer.uniform(-100, 100),
                    randomizer.uniform(0, 5),
                    randomizer.uniform(0, 5),
                    randomizer.uniform(10, 20),
                ) for _ in range(8)]
                requested = randomizer.sample(range(8), 3)
                filled = randomizer.uniform(0.1, 50)
                price = randomizer.uniform(10, 1000)
                fee = randomizer.uniform(-1, 5)
                remaining = filled
                expected = []
                cost = gain = 0
                for index in requested + [index for index in range(8)
                                          if index not in requested]:
                    if remaining <= 0:
                        break
                    available, opened, previous, fees, entry, entry_size = \
                        rows[index]
                    amount = min(available, remaining)
                    buy_fee = entry * (amount / entry_size)
                    sell_fee = fee * (amount / filled)
                    realized = opened * amount
                    profit = (opened - price) * amount - buy_fee - sell_fee
                    expected.append((
                        index, amount, buy_fee, sell_fee, realized, profit,
                        available - amount, previous + profit,
                        fees + buy_fee + sell_fee,
                    ))
                    cost += realized
                    gain += profit
                    remaining -= amount
                self.assertEqual(self.native.event_cover_plan(
                    rows, requested, filled, price, fee),
                    (expected, cost, gain))

                states = [(row[2], row[3]) for row in rows[:2]]
                allocations = [
                    (index % 2, row[0] + 0.5, row[0], row[1], 15.0,
                     0.1, 0.2, 1.0, row[4], row[5])
                    for index, row in enumerate(rows)
                ]
                current = [list(state) for state in states]
                remaining = filled
                expected = []
                cost = gain = 0
                for index, row in enumerate(allocations):
                    if remaining <= 0:
                        break
                    trade, size, pending, opened, closed, buy, sell, net, \
                        entry, entry_size = row
                    amount = min(pending, remaining)
                    buy_fee = entry * (amount / entry_size)
                    sell_fee = fee * (amount / filled)
                    realized = opened * amount
                    profit = price * amount - realized - buy_fee - sell_fee
                    previous = size - pending
                    close = (closed * previous + price * amount) / \
                        (previous + amount)
                    current[trade][0] += profit
                    current[trade][1] = current[trade][1] + buy_fee + sell_fee
                    expected.append((
                        index, pending - amount, close, buy + buy_fee,
                        sell + sell_fee, net + profit, *current[trade],
                    ))
                    cost += realized
                    gain += profit
                    remaining -= amount
                self.assertEqual(self.native.event_sell_plan(
                    allocations, states, filled, price, fee),
                    (expected, cost, gain))
                for short in (False, True):
                    basis = 12000.0
                    self.assertEqual(self.native.event_exit_aggregates(
                        short, basis, (15.0, 1015.0, 30.0), (cost, gain),
                        (filled, price)),
                        (max(0, basis - cost) if short else basis - cost,
                         15.0 + gain, 1015.0 + gain,
                         30.0 + (cost if short else filled * price)))

    def test_settlement_contract_is_checked_before_scope_entry(self):
        from investing_algorithm_framework.domain.native_event import \
            native_event_scope, native_event_engine

        with patch.object(self.native, 'EVENT_SETTLEMENT_SEMANTICS_VERSION',
                          'older-version'):
            with self.assertRaisesRegex(ValueError, 'settlement version'):
                with native_event_scope('rust'):
                    self.fail('An incompatible engine must not run')
        self.assertIsNone(native_event_engine())

    def test_batch_planners_reject_nonfinite_inputs(self):
        for invalid in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.native.event_cover_plan(
                        [(1.0, invalid, 0.0, 0.0, 0.0, 1.0)],
                        [], 1.0, 10.0, 0.0)
                with self.assertRaises(ValueError):
                    self.native.event_sell_plan(
                        [(0, 1.0, 1.0, invalid, 0.0, 0.0, 0.0,
                          0.0, 0.0, 1.0)], [(0.0, 0.0)], 1.0, 10.0, 0.0)

    def test_risk_paths_match_python_exactly(self):
        from investing_algorithm_framework.domain import TradeStopLoss, \
            TradeTakeProfit
        from investing_algorithm_framework.domain.native_event import \
            native_event_scope

        randomizer = random.Random(20260921)
        prices = [100.0, 105.0, 104.5, 120.0, 114.0, 113.99,
                  95.0, 90.0, 94.5, 94.51]
        prices.extend(randomizer.uniform(70, 140) for _ in range(100))
        for model, short, trailing, active, exhausted, check in product(
                (TradeStopLoss, TradeTakeProfit), (False, True),
                (False, True), (False, True), (False, True), (False, True)):
            with self.subTest(model=model.__name__, short=short,
                              trailing=trailing, active=active,
                              exhausted=exhausted, check=check):
                expected = model(
                    trade_id=1, percentage=5, open_price=100,
                    sell_amount=1, trailing=trailing, is_short=short,
                    active=active,
                )
                expected.sold_amount = 1 if exhausted else 0
                actual = deepcopy(expected)
                for price in prices:
                    date = datetime(2023, 8, 8, tzinfo=timezone.utc)
                    if check:
                        result = expected.has_triggered(price)
                    else:
                        result = expected.update_with_last_reported_price(
                            price, date)
                    with native_event_scope('rust'):
                        observed = (actual.has_triggered(price) if check else
                                    actual.update_with_last_reported_price(
                                        price, date))
                    self.assertEqual(result, observed)
                    self.assertEqual(vars(expected), vars(actual))

    def test_scope_restores_python_after_native_failure(self):
        from investing_algorithm_framework.domain.native_event import \
            native_event_scope, native_event_engine
        from investing_algorithm_framework.domain import TradeStopLoss

        rule = TradeStopLoss(trade_id=1, percentage=5, open_price=100,
                             sell_amount=1)
        with self.assertRaisesRegex(RuntimeError, 'native failed'):
            with native_event_scope('rust'), patch.object(
                    self.native, 'event_risk_transition',
                    side_effect=RuntimeError('native failed')):
                rule.has_triggered(90)
        self.assertIsNone(native_event_engine())
        self.assertTrue(rule.has_triggered(90))


class TestOrderBacktestService(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000
    }
    initialize = True

    def setUp(self) -> None:
        super(TestOrderBacktestService, self).setUp()

        self.app.container.order_service.override(
            OrderBacktestService(
                trade_service=self.app.container.trade_service(),
                order_repository=self.app.container.order_repository(),
                position_service=self.app.container.position_service(),
                portfolio_repository=self.app.container.portfolio_repository(),
                portfolio_configuration_service=self.app.container.
                portfolio_configuration_service(),
                portfolio_snapshot_service=self.app.container.
                portfolio_snapshot_service(),
                configuration_service=self.app.container.
                configuration_service(),
            )
        )

        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 8),
            end_date=datetime(2023, 8, 10)
        )
        self.app.initialize_backtest_config(backtest_date_range)

        # Add portfolio
        portfolio_service = self.app.container.portfolio_service()
        portfolio_service.create(
            {
                "identifier": "test_portfolio",
                "market": "binance",
                "trading_symbol": "EUR",
                "unallocated": 1000,
                "initialized": True
            }
        )

    def test_native_entry_reservation_and_fill_parity(self):
        try:
            from iaf_confluence_native import EventBroker
        except ImportError:
            self.skipTest('Native broker extension is not installed')
        service = self.app.container.order_service()
        portfolios = self.app.container.portfolio_service()
        positions = self.app.container.position_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        broker = EventBroker(1000.0)
        order = service.create({
            'target_symbol': 'ADA', 'trading_symbol': 'EUR',
            'amount': 4.0, 'order_side': 'BUY', 'price': 100.0,
            'order_type': 'LIMIT', 'portfolio_id': 1,
        })
        native_id = broker.submit('ADA', 0, 4.0, 100.0)
        self.assertEqual(portfolios.get(1).unallocated, broker.cash)
        service.update(order.id, {
            'filled': 1.0, 'remaining': 3.0, 'price': 90.0,
            'order_fee': 2.0,
        })
        broker.fill(native_id, 1.0, 90.0, 2.0)
        self.assertEqual(portfolios.get(1).unallocated, 608.0)
        self.assertEqual(portfolios.get(1).unallocated, broker.cash)
        position = positions.get(order.position_id)
        self.assertEqual(position.amount, broker.position('ADA').amount)
        self.assertEqual(position.cost, broker.position('ADA').cost)
        self.assertEqual(service.get(order.id).order_fee,
                         broker.order(native_id).fees)
        service.cancel_order(service.get(order.id))
        broker.cancel(native_id)
        self.assertEqual(portfolios.get(1).unallocated, broker.cash)
        for amount, price, fill_amount, fill_price in (
            (1.0, 120.0, 0.5, 130.0), (0.5, 140.0, 0.5, 140.0),
        ):
            sell = service.create({
                'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                'amount': amount, 'order_side': 'SELL', 'price': price,
                'order_type': 'LIMIT', 'portfolio_id': 1,
            })
            native_sell = broker.submit('ADA', 1, amount, price)
            self.assertEqual(portfolios.get(1).total_net_gain,
                             broker.position('ADA').realized_gain)
            service.update(sell.id, {
                'filled': fill_amount, 'remaining': amount - fill_amount,
                'price': fill_price, 'order_fee': 1.0,
                'status': 'CLOSED' if amount == fill_amount else 'OPEN',
            })
            broker.fill(native_sell, fill_amount, fill_price, 1.0)
            self.assertEqual(portfolios.get(1).unallocated, broker.cash)
            self.assertEqual(portfolios.get(1).total_net_gain,
                             broker.position('ADA').realized_gain)
            self.assertEqual(positions.get(order.position_id).cost,
                             broker.position('ADA').cost)
            if amount != fill_amount:
                service.cancel_order(service.get(sell.id))
                broker.cancel(native_sell)
            self.assertEqual(positions.get(order.position_id).amount,
                             broker.position('ADA').amount)
        for _ in range(2):
            service.update(order.id, {'order_fee': 4.0})
            broker.update_fee(native_id, 4.0)
            service.update(sell.id, {'order_fee': 2.0})
            broker.update_fee(native_sell, 2.0)
        self.assertEqual(portfolios.get(1).unallocated, broker.cash)
        self.assertEqual(portfolios.get(1).total_net_gain,
                         broker.position('ADA').realized_gain)

        trades = service.trade_service.get_all({'order_id': order.id})
        self.assertEqual(len(trades), broker.number_of_trades)
        native_trade = broker.trade(1)
        trade = trades[0]
        for name in ('amount', 'available_amount', 'open_price',
                     'net_gain', 'total_fees', 'status'):
            self.assertEqual(getattr(trade, name), getattr(native_trade, name),
                             name)
        allocations = service.trade_service.trade_allocation_repository \
            .get_all({'order_id': sell.id})
        native_allocations = broker.order_allocations(native_sell)
        self.assertEqual(len(allocations), len(native_allocations))
        for allocation, native_allocation in zip(
                allocations, native_allocations):
            for name in ('amount', 'amount_pending', 'open_price',
                         'close_price', 'buy_fee', 'sell_fee',
                         'net_gain_contribution'):
                self.assertEqual(getattr(allocation, name),
                                 getattr(native_allocation, name), name)

    def test_memory_accounting_without_sql(self):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        from investing_algorithm_framework.infrastructure.repositories \
            .event_memory import event_memory_scope

        def reject_sql(*args):
            raise AssertionError('Accounting touched SQL')

        event.listen(Engine, 'before_cursor_execute', reject_sql)
        try:
            with event_memory_scope():
                self.app.container.portfolio_service().create({
                    'identifier': 'test_portfolio', 'market': 'binance',
                    'trading_symbol': 'EUR', 'unallocated': 1000,
                    'initialized': True,
                })
                self.test_native_entry_reservation_and_fill_parity()
        finally:
            event.remove(Engine, 'before_cursor_execute', reject_sql)

    def test_rust_archive_accounting(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .event_memory import event_memory_scope
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting

        try:
            native = load_native_event_accounting()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        with event_memory_scope(accounting_backend='rust'):
            self.app.container.portfolio_service().create({
                'identifier': 'test_portfolio', 'market': 'binance',
                'trading_symbol': 'EUR', 'unallocated': 1000,
                'initialized': True,
            })
            with patch.object(native, 'event_order_transition',
                              wraps=native.event_order_transition) as calls, \
                    patch.object(native, 'event_sell_plan',
                                 wraps=native.event_sell_plan) as plans:
                self.test_native_entry_reservation_and_fill_parity()
                self.assertGreater(calls.call_count, 10)
                self.assertEqual(plans.call_count, 2)

    def test_rust_archive_accounting_regressions(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .event_memory import event_memory_scope
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting

        try:
            load_native_event_accounting()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        for scenario in (
            self.test_fees_settle_once_in_cash_and_quote_position,
            self.test_invalid_fees_do_not_mutate_order_or_cash,
            self.test_sell_realizes_only_filled_portion_and_closes_at_fill,
            self.test_unrelated_pending_exit_does_not_delay_trade_close,
        ):
            with self.subTest(scenario=scenario.__name__), \
                    event_memory_scope(accounting_backend='rust'):
                self.app.container.portfolio_service().create({
                    'identifier': 'test_portfolio', 'market': 'binance',
                    'trading_symbol': 'EUR', 'unallocated': 1000,
                    'initialized': True,
                })
                scenario()

    def test_rust_archive_short_fifo_cost_and_fees(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .event_memory import event_memory_scope
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting

        try:
            load_native_event_accounting()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        with event_memory_scope(accounting_backend='rust'):
            self.app.container.portfolio_service().create({
                'identifier': 'test_portfolio', 'market': 'binance',
                'trading_symbol': 'EUR', 'unallocated': 1000,
                'initialized': True,
            })
            self.test_short_fifo_cost_and_fees()

    def test_rust_hedge_explicit_exit_and_partial_cancel_parity(self):
        from investing_algorithm_framework.domain import PositionMode
        from investing_algorithm_framework.infrastructure.repositories \
            .event_memory import event_memory_scope
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting

        try:
            native = load_native_event_accounting()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        service = self.app.container.order_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        results = []
        for backend in ('python', 'rust'):
            with event_memory_scope(accounting_backend=backend), \
                    patch.object(service, '_position_mode',
                                 return_value=PositionMode.HEDGE), \
                    patch.object(service, '_create_order_id',
                                 side_effect=range(1, 100)), \
                    patch.object(native, 'event_cover_plan',
                                 wraps=native.event_cover_plan) as plans:
                self.app.container.portfolio_service().create({
                    'identifier': 'test_portfolio', 'market': 'binance',
                    'trading_symbol': 'EUR', 'unallocated': 1000,
                    'initialized': True,
                    'created_at': datetime(2023, 8, 8, tzinfo=timezone.utc),
                    'updated_at': datetime(2023, 8, 8, tzinfo=timezone.utc),
                })
                entries = []
                for side, price in (('BUY', 10.0), ('BUY', 12.0),
                                    ('SHORT', 15.0), ('SHORT', 16.0)):
                    order = service.create({
                        'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                        'amount': 2.0, 'order_side': side, 'price': price,
                        'order_type': 'LIMIT', 'portfolio_id': 1,
                    })
                    service.update(order.id, {
                        'filled': 2.0, 'remaining': 0, 'status': 'CLOSED',
                        'order_fee': 0.2,
                    })
                    entries.append(order)
                selected = service.trade_service.find({
                    'order_id': entries[1].id})
                sell = service.create({
                    'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                    'amount': 2.0, 'order_side': 'SELL', 'price': 14.0,
                    'order_type': 'LIMIT', 'portfolio_id': 1,
                    'trades': [{'trade_id': selected.id, 'amount': 2.0}],
                })
                service.update(sell.id, {
                    'filled': 0.5, 'remaining': 1.5, 'order_fee': 0.1})
                service.cancel_order(sell)
                selected_short = service.trade_service.find({
                    'order_id': entries[-1].id})
                cover = service.create({
                    'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                    'amount': 3.0, 'order_side': 'COVER', 'price': 11.0,
                    'order_type': 'LIMIT', 'portfolio_id': 1,
                    'trades': [{'trade_id': selected_short.id, 'amount': 2.0}],
                })
                service.update(cover.id, {
                    'filled': 2.5, 'remaining': 0.5, 'order_fee': 0.1})
                self.assertEqual(service.trade_service.get(
                    selected_short.id).available_amount, 0)
                self.assertEqual(service.trade_service.find({
                    'order_id': entries[-2].id}).available_amount, 1.5)
                self.assertEqual(plans.call_count, int(backend == 'rust'))
                service.cancel_order(cover)
                service.update(cover.id, {'order_fee': 0.2})
                service.update(entries[1].id, {'order_fee': 0.4})
                service.update(sell.id, {'order_fee': 0.05})
                results.append({
                    'portfolio': service.portfolio_repository.get(1).to_dict(),
                    'positions': [item.to_dict() for item in
                                  service.position_service.get_all()],
                    'trades': [item.to_dict() for item in
                               service.trade_service.get_all()],
                    'allocations': [
                        {column.key: getattr(item, column.key)
                         for column in item.__mapper__.columns}
                        for item in service.trade_service
                        .trade_allocation_repository.get_all()
                    ],
                })
        self.assertEqual(results[0], results[1])

    def test_fees_settle_once_in_cash_and_quote_position(self):
        service = self.app.container.order_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        order = service.create({
            'target_symbol': 'ADA', 'trading_symbol': 'EUR',
            'amount': 2.0, 'order_side': 'BUY', 'price': 100.0,
            'order_type': 'LIMIT', 'portfolio_id': 1,
        })
        for update, expected in (
            ({'filled': 1.0, 'remaining': 1.0, 'order_fee': 2.0}, 798.0),
            ({'filled': 1.0, 'remaining': 1.0, 'order_fee': 2.0}, 798.0),
            ({'order_fee': 3.0}, 797.0),
            ({'filled': 2.0, 'remaining': 0.0, 'order_fee': 4.0,
              'status': 'CLOSED'}, 796.0),
        ):
            with self.subTest(update=update):
                service.update(order.id, update)
                self.assertEqual(
                    self.app.container.portfolio_service().get(1).unallocated,
                    expected,
                )
                self.assertEqual(
                    self.app.container.position_service().find(
                        {'portfolio': 1, 'symbol': 'EUR'}).amount,
                    expected,
                )

    def test_invalid_fees_do_not_mutate_order_or_cash(self):
        service = self.app.container.order_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        order = service.create({
            'target_symbol': 'ADA', 'trading_symbol': 'EUR',
            'amount': 1, 'order_side': 'BUY', 'price': 100,
            'order_type': 'LIMIT', 'portfolio_id': 1,
        })
        for fee, currency in ((float('nan'), 'EUR'), (-1, 'EUR'), (1, 'ADA')):
            with self.subTest(fee=fee, currency=currency):
                with self.assertRaisesRegex(Exception, 'fee'):
                    service.update(order.id, {
                        'filled': 1, 'order_fee': fee,
                        'order_fee_currency': currency,
                    })
                self.assertEqual(service.get(order.id).filled, 0)
                self.assertEqual(
                    self.app.container.portfolio_service().get(1).unallocated,
                    900,
                )

    def test_sell_realizes_only_filled_portion_and_closes_at_fill(self):
        service = self.app.container.order_service()
        trades = service.trade_service
        portfolios = self.app.container.portfolio_service()
        positions = self.app.container.position_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        buy = service.create({
            'target_symbol': 'ADA', 'trading_symbol': 'EUR',
            'amount': 2.0, 'order_side': 'BUY', 'price': 100.0,
            'order_type': 'LIMIT', 'portfolio_id': 1,
        })
        service.update(buy.id, {
            'filled': 2.0, 'remaining': 0.0, 'status': 'CLOSED',
            'order_fee': 2.0,
        })
        trade = trades.get_all()[0]
        with patch.object(trades, '_dispatch_trade_hook') as hook:
            sell = service.create({
                'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                'amount': 2.0, 'order_side': 'SELL', 'price': 120.0,
                'order_type': 'LIMIT', 'portfolio_id': 1,
            })
            self.assertEqual(trades.get(trade.id).status, 'OPEN')
            self.assertIsNone(trades.get(trade.id).closed_at)
            self.assertEqual(trades.get(trade.id).net_gain, 0.0)
            self.assertEqual(portfolios.get(1).total_net_gain, 0.0)
            self.assertEqual(positions.get(buy.position_id).cost, 200.0)
            hook.assert_not_called()
            service.update(sell.id, {
                'filled': 1.0, 'remaining': 1.0, 'price': 130.0,
                'order_fee': 1.0,
            })
            self.assertEqual(trades.get(trade.id).net_gain, 28.0)
            self.assertEqual(trades.get(trade.id).status, 'OPEN')
            self.assertEqual(portfolios.get(1).unallocated, 927.0)
            self.assertEqual(portfolios.get(1).total_net_gain, 28.0)
            self.assertEqual(positions.get(buy.position_id).cost, 100.0)
            self.assertEqual(hook.call_args.args[0], 'on_trade_updated')
            service.cancel_order(service.get(sell.id))
            self.assertEqual(trades.get(trade.id).available_amount, 1.0)
            self.assertEqual(trades.get(trade.id).net_gain, 28.0)
            self.assertEqual(positions.get(buy.position_id).cost, 100.0)
            final_sell = service.create({
                'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                'amount': 1.0, 'order_side': 'SELL', 'price': 140.0,
                'order_type': 'LIMIT', 'portfolio_id': 1,
            })
            hook.reset_mock()
            service.update(final_sell.id, {
                'filled': 1.0, 'remaining': 0.0, 'status': 'CLOSED',
                'order_fee': 1.0,
            })
            self.assertEqual(trades.get(trade.id).status, 'CLOSED')
            self.assertEqual(trades.get(trade.id).net_gain, 66.0)
            self.assertEqual(portfolios.get(1).unallocated, 1066.0)
            self.assertEqual(positions.get(buy.position_id).cost, 0.0)
            self.assertEqual(hook.call_args.args[0], 'on_trade_closed')
            self.assertEqual(hook.call_count, 1)
            service.update(final_sell.id, {'order_fee': 2.0})
            service.update(buy.id, {'order_fee': 4.0})
            self.assertEqual(trades.get(trade.id).net_gain, 63.0)
            self.assertEqual(portfolios.get(1).unallocated, 1063.0)
            self.assertEqual(portfolios.get(1).total_net_gain, 63.0)

    def test_unrelated_pending_exit_does_not_delay_trade_close(self):
        service = self.app.container.order_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        orders = []
        for symbol in ('ADA', 'DOT'):
            buy = service.create({
                'target_symbol': symbol, 'trading_symbol': 'EUR',
                'amount': 1, 'order_side': 'BUY', 'price': 100,
                'order_type': 'LIMIT', 'portfolio_id': 1,
                'filled': 1, 'remaining': 0, 'status': 'CLOSED',
            })
            sell = service.create({
                'target_symbol': symbol, 'trading_symbol': 'EUR',
                'amount': 1, 'order_side': 'SELL', 'price': 120,
                'order_type': 'LIMIT', 'portfolio_id': 1,
            })
            orders.append((buy, sell))
        service.update(orders[0][1].id, {
            'filled': 1, 'remaining': 0, 'status': 'CLOSED',
        })
        for index, status in enumerate(('CLOSED', 'OPEN')):
            trade = service.trade_service.find({
                'order_id': orders[index][0].id,
            })
            self.assertEqual(trade.status, status)

    def test_short_fifo_cost_and_fees(self):
        service = self.app.container.order_service()
        self.app.container.configuration_service().add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc))
        for price in (100.0, 120.0):
            short = service.create({
                'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                'amount': 1, 'order_side': 'SHORT', 'price': price,
                'order_type': 'LIMIT', 'portfolio_id': 1,
            })
            service.update(short.id, {
                'filled': 1, 'remaining': 0,
                'status': 'CLOSED', 'order_fee': 2,
            })
        for price, cost, gain, cash in (
            (80, 120, 17, 1135), (90, 0, 44, 1044),
        ):
            cover = service.create({
                'target_symbol': 'ADA', 'trading_symbol': 'EUR',
                'amount': 1, 'order_side': 'COVER', 'price': price,
                'order_type': 'LIMIT', 'portfolio_id': 1,
            })
            service.update(cover.id, {
                'filled': 1, 'remaining': 0,
                'status': 'CLOSED', 'order_fee': 1,
            })
            self.assertEqual(
                service.position_service.get(short.position_id).cost, cost,
            )
            portfolio = self.app.container.portfolio_service().get(1)
            self.assertEqual(portfolio.unallocated, cash)
            self.assertEqual(portfolio.total_net_gain, gain)
        service.update(cover.id, {'order_fee': 2})
        self.assertEqual(
            self.app.container.portfolio_service().get(1).total_net_gain, 43,
        )

    def test_create_limit_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            INDEX_DATETIME, datetime(2023, 8, 8, tzinfo=timezone.utc)
        )

        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

    # def test_update_order(self):
    #     order_service = self.app.container.order_service()
    #     configuration_service = self.app.container.configuration_service()
    #     configuration_service.add_value(
    #         BACKTESTING_INDEX_DATETIME,
    #         datetime.utcnow()
    #     )
    #
    #     order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "BUY",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     updated_order = order_service.update(
    #         order.id,
    #         {
    #             "status": "CLOSED",
    #             "filled": 2004.5303357979318,
    #             "remaining": Decimal('0'),
    #         }
    #     )
    #     self.assertEqual(updated_order.amount, 2004.5303357979318)
    #     self.assertEqual(updated_order.filled, 2004.5303357979318)
    #     self.assertEqual(updated_order.remaining, 0)
    #
    #     position_service = self.app.container.position_service()
    #     position = position_service.get(order.position_id)
    #     self.assertEqual(position.amount, 2004.5303357979318)
    #
    # def test_create_limit_buy_order(self):
    #     order_service = self.app.container.order_service()
    #     configuration_service = self.app.container.configuration_service()
    #     configuration_service.add_value(
    #         BACKTESTING_INDEX_DATETIME, datetime.now(tz=timezone.utc)
    #     )
    #     order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "BUY",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     self.assertEqual(1, order_service.count())
    #     self.assertEqual(2004.5303357979318, order.amount)
    #     self.assertEqual(0, order.get_filled())
    #     self.assertEqual(2004.5303357979318, order.get_remaining())
    #     self.assertEqual(0.24262, order.get_price())
    #     self.assertEqual("ADA", order.get_target_symbol())
    #     self.assertEqual("EUR", order.get_trading_symbol())
    #     self.assertEqual("BUY", order.get_order_side())
    #     self.assertEqual("LIMIT", order.get_order_type())
    #     self.assertEqual("OPEN", order.get_status())
    #
    # def test_create_limit_sell_order(self):
    #     order_service = self.app.container.order_service()
    #     configuration_service = self.app.container.configuration_service()
    #     configuration_service.add_value(
    #         BACKTESTING_INDEX_DATETIME,
    #         datetime.utcnow()
    #     )
    #     order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "BUY",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     self.assertEqual(1, order_service.count())
    #     self.assertEqual(2004.5303357979318, order.amount)
    #     self.assertEqual(0, order.get_filled())
    #     self.assertEqual(2004.5303357979318, order.get_remaining())
    #     self.assertEqual(0.24262, order.get_price())
    #     self.assertEqual("ADA", order.get_target_symbol())
    #     self.assertEqual("EUR", order.get_trading_symbol())
    #     self.assertEqual("BUY", order.get_order_side())
    #     self.assertEqual("LIMIT", order.get_order_type())
    #     self.assertEqual("OPEN", order.get_status())
    #
    #     order_service.update(
    #         order.id,
    #         {
    #             "status": "CLOSED",
    #             "filled": 2004.5303357979318,
    #             "remaining": Decimal('0'),
    #         }
    #     )
    #
    #     order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "SELL",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     self.assertEqual(2, order_service.count())
    #     self.assertEqual(2004.5303357979318, order.amount)
    #     self.assertEqual(0, order.get_filled())
    #     self.assertEqual(2004.5303357979318, order.get_remaining())
    #     self.assertEqual(0.24262, order.get_price())
    #     self.assertEqual("ADA", order.get_target_symbol())
    #     self.assertEqual("EUR", order.get_trading_symbol())
    #     self.assertEqual("SELL", order.get_order_side())
    #     self.assertEqual("LIMIT", order.get_order_type())
    #
    #     # Order is synced so is OPEN
    #     self.assertEqual("OPEN", order.get_status())
    #
    # def test_update_buy_order_with_successful_order(self):
    #     pass
    #
    # def test_update_buy_order_with_successful_order_filled(self):
    #     pass
    #
    # def test_update_sell_order_with_successful_order(self):
    #     pass
    #
    # def test_update_sell_order_with_successful_order_filled(self):
    #     pass
    #
    # def test_update_buy_order_with_failed_order(self):
    #     pass
    #
    # def test_update_sell_order_with_failed_order(self):
    #     pass
    #
    # def test_update_buy_order_with_cancelled_order(self):
    #     pass
    #
    # def test_update_sell_order_with_cancelled_order(self):
    #     pass
    #
    # def test_has_executed_buy_order(self):
    #     order_service = self.app.container.order_service()
    #     configuration_service = self.app.container.configuration_service()
    #     configuration_service.add_value(
    #         BACKTESTING_INDEX_DATETIME,
    #         datetime.utcnow()
    #     )
    #
    #     # Create the buy order
    #     order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "BUY",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     self.assertEqual(1, order_service.count())
    #     self.assertEqual(2004.5303357979318, order.amount)
    #     self.assertEqual(0, order.get_filled())
    #     self.assertEqual(2004.5303357979318, order.get_remaining())
    #     self.assertEqual(0.24262, order.get_price())
    #     self.assertEqual("ADA", order.get_target_symbol())
    #     self.assertEqual("EUR", order.get_trading_symbol())
    #     self.assertEqual("BUY", order.get_order_side())
    #     self.assertEqual("LIMIT", order.get_order_type())
    #     self.assertEqual("OPEN", order.get_status())
    #
    #     # Check with ohlcv data with a single row that matches the price
    #     # of the buy order
    #     ohclv = [
    #         {
    #             "Open": 0.24262,
    #             "High": 0.24262,
    #             "Low": 0.24262,
    #             "Close": 0.24262,
    #             "Volume": 0.24262,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertTrue(order_service.has_executed(order, ohlcv_df))
    #
    #     # Check with ohlcv data with a single row that is lower than the
    #     # buy order price
    #     ohclv = [
    #         {
    #             "Open": 0.24162,
    #             "High": 0.24162,
    #             "Low": 0.24162,
    #             "Close": 0.24162,
    #             "Volume": 0.24162,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertTrue(order_service.has_executed(order, ohlcv_df))
    #
    #     # Check with ohlcv data with a single row that is higher than the
    #     # buy order price
    #     ohclv = [
    #         {
    #             "Open": 0.24362,
    #             "High": 0.24362,
    #             "Low": 0.24362,
    #             "Close": 0.24362,
    #             "Volume": 0.24362,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertFalse(order_service.has_executed(order, ohlcv_df))
    #
    #     # Check with multiple rows with all rows having a price higher than
    #     # the buy order price
    #     ohclv = [
    #         {
    #             "Open": 0.24462,
    #             "High": 0.24462,
    #             "Low": 0.24462,
    #             "Close": 0.24462,
    #             "Volume": 0.24462,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         },
    #         {
    #             "Open": 0.24300,
    #             "High": 0.24300,
    #             "Low": 0.24300,
    #             "Close": 0.24300,
    #             "Volume": 0.24300,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertFalse(order_service.has_executed(order, ohlcv_df))
    #
    #     # Check with multiple rows with the first row have a price lower than
    #     # the buy order price
    #     ohclv = [
    #         {
    #             "Open": 0.24162,
    #             "High": 0.24162,
    #             "Low": 0.24162,
    #             "Close": 0.24162,
    #             "Volume": 0.24162,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         },
    #         {
    #             "Open": 0.24200,
    #             "High": 0.24200,
    #             "Low": 0.24200,
    #             "Close": 0.24200,
    #             "Volume": 0.24200,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         },
    #         {
    #             "Open": 0.24300,
    #             "High": 0.24300,
    #             "Low": 0.24300,
    #             "Close": 0.24300,
    #             "Volume": 0.24300,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertTrue(order_service.has_executed(order, ohlcv_df))
    #
    # def test_has_executed_sell_order(self):
    #     order_service = self.app.container.order_service()
    #     configuration_service = self.app.container.configuration_service()
    #     configuration_service.add_value(
    #         BACKTESTING_INDEX_DATETIME,
    #         datetime.now(tz=timezone.utc)
    #     )
    #
    #     # Create the buy order
    #     order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "BUY",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #     self.assertEqual(1, order_service.count())
    #     self.assertEqual(2004.5303357979318, order.amount)
    #     self.assertEqual(0, order.get_filled())
    #     self.assertEqual(2004.5303357979318, order.get_remaining())
    #     self.assertEqual(0.24262, order.get_price())
    #     self.assertEqual("ADA", order.get_target_symbol())
    #     self.assertEqual("EUR", order.get_trading_symbol())
    #     self.assertEqual("BUY", order.get_order_side())
    #     self.assertEqual("LIMIT", order.get_order_type())
    #     self.assertEqual("OPEN", order.get_status())
    #
    #     # Update the buy order to closed
    #     order_service.update(
    #         order.id,
    #         {
    #             "status": "CLOSED",
    #             "filled": 2004.5303357979318,
    #             "remaining": Decimal('0'),
    #         }
    #     )
    #
    #     # Create the sell order
    #     sell_order = order_service.create(
    #         {
    #             "target_symbol": "ADA",
    #             "trading_symbol": "EUR",
    #             "amount": 2004.5303357979318,
    #             "order_side": "SELL",
    #             "price": 0.24262,
    #             "order_type": "LIMIT",
    #             "portfolio_id": 1,
    #             "status": "CREATED",
    #         }
    #     )
    #
    #     # Check with ohlcv data with a single row that matches the price
    #     # of the sell order
    #     ohclv = [
    #         {
    #             "Open": 0.24262,
    #             "High": 0.24262,
    #             "Low": 0.24262,
    #             "Close": 0.24262,
    #             "Volume": 0.24262,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertTrue(order_service.has_executed(sell_order, ohlcv_df))
    #
    #     # Check with ohlcv data with a single row that has higher price then
    #     # the sell order price
    #     ohclv = [
    #         {
    #             "Open": 0.24362,
    #             "High": 0.24362,
    #             "Low": 0.24362,
    #             "Close": 0.24362,
    #             "Volume": 0.24362,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertTrue(order_service.has_executed(sell_order, ohlcv_df))
    #
    #     # Check with ohlcv data with a single row that has lower price then
    #     # the sell order price
    #     ohclv = [
    #         {
    #             "Open": 0.24162,
    #             "High": 0.24162,
    #             "Low": 0.24162,
    #             "Close": 0.24162,
    #             "Volume": 0.24162,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertFalse(order_service.has_executed(sell_order, ohlcv_df))
    #
    #     # Check with multiple rows with all rows having a price lower than
    #     # the sell order price
    #     ohclv = [
    #         {
    #             "Open": 0.24162,
    #             "High": 0.24162,
    #             "Low": 0.24162,
    #             "Close": 0.24162,
    #             "Volume": 0.24162,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         },
    #         {
    #             "Open": 0.24000,
    #             "High": 0.24000,
    #             "Low": 0.24000,
    #             "Close": 0.24000,
    #             "Volume": 0.24000,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertFalse(order_service.has_executed(sell_order, ohlcv_df))
    #
    #     # Check with multiple rows with the first row have a price higher than
    #     # the sell order price
    #     ohclv = [
    #         {
    #             "Open": 0.24300,
    #             "High": 0.24300,
    #             "Low": 0.24300,
    #             "Close": 0.24300,
    #             "Volume": 0.24300,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         },
    #         {
    #             "Open": 0.24162,
    #             "High": 0.24162,
    #             "Low": 0.24162,
    #             "Close": 0.24162,
    #             "Volume": 0.24162,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         },
    #         {
    #             "Open": 0.24000,
    #             "High": 0.24000,
    #             "Low": 0.24000,
    #             "Close": 0.24000,
    #             "Volume": 0.24000,
    #             "Datetime": datetime.now(tz=timezone.utc)
    #         }
    #     ]
    #     ohlcv_df = pl.DataFrame(ohclv)
    #     self.assertTrue(order_service.has_executed(sell_order, ohlcv_df))
