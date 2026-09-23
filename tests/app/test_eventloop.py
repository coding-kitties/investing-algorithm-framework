from datetime import datetime, timezone, timedelta
from typing import Any
import os
import shutil
from unittest import TestCase
from unittest.mock import Mock, patch

from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, MarketCredential, PortfolioConfiguration, \
    DataProvider, Schedule, TimeUnit
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.services import \
    BacktestTradeOrderEvaluator
from tests.resources import TestBase


class TestNativeScheduledLoop(TestCase):
    def _build_loop(self):
        return EventLoopService(
            context=Mock(), order_service=Mock(), trade_service=Mock(),
            portfolio_service=Mock(), configuration_service=Mock(),
            data_provider_service=Mock(), portfolio_snapshot_service=Mock(),
        )

    def test_native_lifecycle_order_and_failure_boundaries(self):
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting, native_event_scope

        try:
            native = load_native_event_accounting()
        except ImportError:
            self.skipTest('Native extension is not installed')
        phases = ('_prepare_iteration', '_evaluate_iteration',
                  '_run_iteration_task', '_run_iteration_strategy',
                  '_log_next_algorithm_run', '_run_iteration_scheduled',
                  '_finish_iteration')
        for failure in (None, *phases):
            for strategies in ([], ['first', 'second']):
                with self.subTest(failure=failure, strategies=strategies):
                    outcomes = []
                    for backend in ('python', 'rust'):
                        loop = self._build_loop()
                        events = []

                        def phase(name):
                            def execute(*args):
                                events.append((name, args))
                                if name == failure:
                                    raise RuntimeError(name)
                                return {'date': 123}
                            return execute

                        for name in phases:
                            setattr(loop, name, phase(name))
                        with native_event_scope(backend), patch.object(
                            native, 'run_event_iteration',
                            wraps=native.run_event_iteration,
                        ) as calls:
                            try:
                                loop._run_iteration(
                                    strategies, ['task'], [('first', 'hook')])
                            except RuntimeError as exc:
                                self.assertEqual(str(exc), failure)
                            self.assertEqual(calls.call_count,
                                             int(backend == 'rust'))
                        if failure in [entry[0] for entry in events]:
                            self.assertEqual(events[-1][0], failure)
                        outcomes.append(events)
                    self.assertEqual(*outcomes)
                    if failure is None:
                        expected = list(phases[:3]) if not strategies else [
                            *phases[:4], phases[3], *phases[4:]]
                        self.assertEqual([entry[0] for entry in events],
                                         expected)

    def test_native_market_refresh_and_failure_order(self):
        from investing_algorithm_framework.domain.native_event import \
            load_native_event_accounting, native_event_scope

        try:
            load_native_event_accounting()
        except ImportError:
            self.skipTest('Native extension is not installed')
        order = Mock(symbol='BTC')
        trade = Mock(symbol='BTC')
        frame = Mock()
        frame.is_empty.return_value = False
        for failure in (None, 'fill', 'mark', 'take_profit', 'stop_loss'):
            outcomes = []
            for backend in ('python', 'rust'):
                events = []
                evaluator = object.__new__(BacktestTradeOrderEvaluator)
                evaluator.trade_service = Mock()

                def record(name):
                    events.append(name)
                    if name == failure:
                        raise RuntimeError(name)

                def candidates(query):
                    self.assertEqual(query, {'status': 'OPEN'})
                    self.assertEqual(events, ['fill'])
                    events.append('refresh')
                    return [trade]

                evaluator.trade_service.get_all.side_effect = candidates
                evaluator._check_has_executed = lambda *args: record('fill')
                evaluator._mark_market_trade = lambda *args: record('mark')
                evaluator._check_take_profits = lambda: record('take_profit')
                evaluator._check_stop_losses = lambda: record('stop_loss')
                with native_event_scope(backend):
                    try:
                        evaluator.evaluate([], [order], {'BTC': frame})
                    except RuntimeError as exc:
                        self.assertEqual(str(exc), failure)
                expected = ['fill', 'refresh', 'mark', 'take_profit',
                            'stop_loss']
                if failure is not None:
                    expected = expected[:expected.index(failure) + 1]
                self.assertEqual(events, expected)
                outcomes.append(events)
            self.assertEqual(*outcomes)

    def _exercise(self, backend, fail=False):
        loop = self._build_loop()
        events = []
        loop._configuration_service = Mock()
        loop._configuration_service.add_value.side_effect = \
            lambda key, value: events.append(('clock', value))
        loop._get_strategies = lambda ids: ids
        loop._get_tasks_by_ids = lambda ids: ids
        loop._snapshots = []
        loop._portfolio_snapshot_service = Mock()
        loop._portfolio_snapshot_service.save_all.side_effect = \
            lambda values: events.append(('flush', list(values)))
        loop.cleanup = lambda: events.append(('cleanup',))

        def iteration(**kwargs):
            events.append(('tick', kwargs))
            if fail:
                raise RuntimeError('callback failed')
            loop._snapshots.append('snapshot')

        loop._run_iteration = iteration
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        schedule = {
            start + timedelta(hours=1): {
                'strategy_ids': ['second', 'first'], 'task_ids': ['task'],
                'scheduled_function_calls': [('second', 'rebalance')],
            },
            start: {'strategy_ids': [], 'task_ids': []},
        }
        def execute():
            loop.start(
                schedule=schedule, event_schedule_backend=backend,
                snapshot_batch_size=1,
                resource_check=lambda: events.append(('guard',)),
            )

        if fail:
            with self.assertRaisesRegex(RuntimeError, 'callback failed'):
                execute()
        else:
            with patch(
                'investing_algorithm_framework.app.eventloop.tqdm',
            ) as progress_factory:
                execute()
            progress = progress_factory.return_value.__enter__.return_value
            self.assertEqual(progress.update.call_count, len(schedule))
            progress_factory.return_value.__exit__.assert_called_once()
            self.assertEqual(events[-1], ('cleanup',))
            self.assertEqual(sum(item[0] == 'guard' for item in events), 4)
            self.assertEqual(sum(item[0] == 'flush' for item in events), 2)
        return events

    def test_native_callback_order_and_failure_parity(self):
        try:
            from investing_algorithm_framework.app.native_schedule import \
                load_native_schedule
            load_native_schedule()
        except ImportError:
            self.skipTest('Native extension is not installed')
        for fail in (False, True):
            with self.subTest(fail=fail):
                self.assertEqual(self._exercise('python', fail),
                                 self._exercise('rust', fail))
                self.assertEqual(self._exercise('python', fail),
                                 self._exercise('auto', fail))

    def test_missing_extension_fallback_is_before_first_tick(self):
        with patch(
            'investing_algorithm_framework.app.native_schedule.'
            'load_native_schedule', side_effect=ImportError('missing'),
        ):
            self.assertEqual(self._exercise('python'), self._exercise('auto'))
            with self.assertRaises(ImportError):
                self._exercise('rust')

    def test_native_schedule_rejects_unsorted_before_callbacks(self):
        try:
            from investing_algorithm_framework.app.native_schedule import \
                load_native_schedule
            runner = load_native_schedule()
        except ImportError:
            self.skipTest('Native extension is not installed')
        callback = Mock()
        runner([], callback)
        callback.assert_not_called()
        for times in ([2, 1], [1, 1]):
            with self.assertRaisesRegex(ValueError, 'strictly increasing'):
                runner(times, callback)
            callback.assert_not_called()
        runner([-1, 0, 1], callback)
        self.assertEqual(
            [item.args for item in callback.call_args_list],
            [(0, -1), (1, 0), (2, 1)],
        )

    def test_timestamp_normalization_preserves_microseconds(self):
        from investing_algorithm_framework.app.native_schedule import \
            prepare_native_schedule, NativeScheduleUnsupported
        offset = timezone(timedelta(hours=2))
        times = [
            datetime(1969, 12, 31, 23, 59, 59, 999999),
            datetime(1970, 1, 1, 2, tzinfo=offset),
            datetime(1970, 1, 1, 0, 0, 0, 1, tzinfo=timezone.utc),
        ]
        with patch(
            'investing_algorithm_framework.app.native_schedule.'
            'load_native_schedule', return_value=Mock(),
        ):
            _, timestamps = prepare_native_schedule(times, 'rust')
            self.assertEqual(timestamps, [-1, 0, 1])
            for unsupported in (['invalid'], times[::-1], [
                datetime.min.replace(tzinfo=offset),
            ]):
                self.assertEqual(
                    prepare_native_schedule(unsupported, 'auto'), (None, None),
                )
                with self.assertRaises(NativeScheduleUnsupported):
                    prepare_native_schedule(unsupported, 'rust')


class CustomFeedDataProvider(DataProvider):

    def has_data(self, data_source: DataSource, start_date: datetime = None,
                 end_date: datetime = None) -> bool:
        pass

    def prepare_backtest_data(self, backtest_start_date,
                              backtest_end_date) -> None:
        pass

    def get_data(self, date: datetime = None, start_date: datetime = None,
                 end_date: datetime = None, save: bool = False) -> Any:
        pass

    def get_backtest_data(self, backtest_index_date: datetime,
                          backtest_start_date: datetime = None,
                          backtest_end_date: datetime = None) -> Any:
        pass

    def copy(self, data_source: DataSource) -> "DataProvider":
        pass


class StrategyForTesting(TradingStrategy):
    data_sources = [
        DataSource(
            identifier="DOT/EUR_2h",
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="DOT/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
    ]
    schedule = Schedule.every(2, TimeUnit.HOUR)
    def run_strategy(self, context, data):
        pass

class StrategyForTestingTwo(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="ETH/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="custom_feed_data"
        ),
    ]
    schedule = Schedule.every(4, TimeUnit.HOUR)
    def run_strategy(self, context, data):
        pass


class StrategyForTestingThree(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="twitter_data"
        ),
    ]
    schedule = Schedule.every(1, TimeUnit.DAY)
    def run_strategy(self, context, market_data):
        pass


class TestEventloopService(TestBase):
    initialize = False
    market_credentials = [
        MarketCredential(
            market="bitvavo",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    external_balances = {
        "EUR": 1000
    }
    portfolio_configurations = [
        PortfolioConfiguration(
            market="bitvavo",
            trading_symbol="EUR",
            initial_balance=1000
        )
    ]


    def test_initialize(self):
        self.app.initialize_config()
        self.app.initialize_storage()
        self.app.initialize_services()
        self.app.initialize_portfolios()
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=self.app.container.data_provider_service(),
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
        )
        self.app.add_strategy(
            StrategyForTesting(),
        )
        self.app.add_strategy(
            StrategyForTestingTwo(),
        )
        self.app.add_strategy(
            StrategyForTestingThree(),
        )
        event_loop_service.initialize(
            trade_order_evaluator=BacktestTradeOrderEvaluator(
                trade_service=self.app.container.trade_service(),
                order_service=self.app.container.order_service(),
                trade_stop_loss_service=self.app.container.trade_stop_loss_service(),
                trade_take_profit_service=self.app.container.trade_take_profit_service(),
            ),
            algorithm=self.app.get_algorithm()
        )
        self.assertEqual(len(event_loop_service.next_run_times), 3)
        self.assertEqual(len(event_loop_service.data_sources), 5)

        # Each entry tracks last_run (None until first execution).
        for strategy in event_loop_service.strategies:
            self.assertIn(
                strategy.strategy_id,
                event_loop_service.next_run_times
            )
            self.assertIsNone(
                event_loop_service
                .next_run_times[strategy.strategy_id]["last_run"]
            )

    def test_get_data_sources_for_iteration(self):
        correct_data_sources = [
            DataSource(
                data_type=DataType.OHLCV,
                warmup_window=200,
                symbol="ETH/EUR",
                time_frame="2h",
                market="bitvavo"
            ),
            DataSource(
                data_type=DataType.CUSTOM,
                data_provider_identifier="custom_feed_data"
            ),
            DataSource(
                data_type=DataType.OHLCV,
                warmup_window=200,
                symbol="DOT/EUR",
                time_frame="2h",
                market="bitvavo"
            )
        ]

        data_sources = EventLoopService._get_data_sources_for_iteration(
            [
                DataSource(
                    data_type=DataType.OHLCV,
                    warmup_window=200,
                    symbol="DOT/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.CUSTOM,
                    data_provider_identifier="custom_feed_data"
                ),
                DataSource(
                    data_type=DataType.OHLCV,
                    warmup_window=200,
                    symbol="ETH/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.OHLCV,
                    warmup_window=200,
                    symbol="ETH/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.CUSTOM,
                    data_provider_identifier="custom_feed_data"
                ),
            ],
        )

        self.assertEqual(data_sources, set(correct_data_sources))

    def tearDown(self) -> None:
        super().tearDown()

        databases_directory = os.path.join(
            self.resource_directory, "databases"
        )
        backtest_databases_directory = os.path.join(
            self.resource_directory, "backtest_databases"
        )

        if os.path.exists(databases_directory):
            shutil.rmtree(databases_directory, ignore_errors=True)

        if os.path.exists(backtest_databases_directory):
            shutil.rmtree(backtest_databases_directory, ignore_errors=True)
