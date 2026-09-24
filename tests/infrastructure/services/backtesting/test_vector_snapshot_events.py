from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
import sys
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import patch

import pandas as pd
import numpy as np

from investing_algorithm_framework import (
    PortfolioConfiguration, PositionMode, SignalSeries, SignalSide,
    PositionSize, TradingCost,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    import vector_backtest_service as vector_module
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_backtest_service import _index_snapshot_trade_events
from scripts.bench_vector_snapshot_events import (
    LegacyScan, result_digest, workload,
)


class TestSnapshotTradeEvents(TestCase):
    def test_index_matches_original_scan_including_ties_and_open_trades(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        times = [start + timedelta(hours=index) for index in range(5)]
        trades = [
            SimpleNamespace(opened_at=times[0], closed_at=times[2]),
            SimpleNamespace(opened_at=times[2], closed_at=times[2]),
            SimpleNamespace(opened_at=times[1], closed_at=None),
            SimpleNamespace(opened_at=times[2], closed_at=times[3]),
            SimpleNamespace(opened_at=times[0], closed_at=times[3]),
            SimpleNamespace(opened_at=None, closed_at=None),
        ]
        events = _index_snapshot_trade_events(trades)
        for timestamp in times:
            expected = [trade for trade in trades if (
                trade.opened_at == timestamp or trade.closed_at == timestamp
            )]
            self.assertEqual(expected, events.get(timestamp, []))
        self.assertEqual([trades[0], trades[1], trades[3]], events[times[2]])
        self.assertNotIn(None, events)
        self.assertEqual({}, _index_snapshot_trade_events([]))

    def test_equal_instants_in_different_timezones_share_a_bucket(self):
        utc_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        offset_time = utc_time.astimezone(timezone(timedelta(hours=2)))
        trade = SimpleNamespace(opened_at=offset_time, closed_at=utc_time)
        events = _index_snapshot_trade_events([trade])
        self.assertEqual([trade], events[utc_time])
        self.assertEqual(1, len(events))

    def test_engine_matches_legacy_with_shorts_hedge_sizing_and_deposits(self):
        for mode, dynamic in (
            (PositionMode.NETTING, False),
            (PositionMode.NETTING, True),
            (PositionMode.HEDGE, True),
        ):
            with self.subTest(mode=mode, dynamic=dynamic):
                digests = []
                for factory in (LegacyScan, _index_snapshot_trade_events):
                    service, arguments = workload(64, 3)
                    arguments["portfolio_configuration"] = (
                        PortfolioConfiguration(
                            market="BITVAVO", trading_symbol="EUR",
                            initial_balance=10000, position_mode=mode,
                        )
                    )
                    arguments["dynamic_position_sizing"] = dynamic
                    start = arguments["backtest_date_range"].start_date
                    deposits = [(start + timedelta(hours=16), 250.0)]
                    with patch.object(
                        vector_module, "_index_snapshot_trade_events",
                        wraps=factory,
                    ) as lookup, patch.object(
                        service, "_resolve_deposit_schedule",
                        return_value=deposits,
                    ):
                        result = service.run(**arguments)
                    lookup.assert_called_once()
                    self.assertGreater(len(result.trades), 0)
                    self.assertTrue(any(trade.is_short
                                        for trade in result.trades))
                    self.assertEqual(250.0, sum(
                        snapshot.cash_flow or 0
                        for snapshot in result.portfolio_snapshots
                    ))
                    digests.append(result_digest(result))
                self.assertEqual(digests[0], digests[1])

    def test_parity_digest_detects_portfolio_value_changes(self):
        service, arguments = workload(32, 1)
        result = service.run(**arguments)
        original = result_digest(result)
        snapshots = result.portfolio_snapshots.materialize()
        snapshots[-1].total_value += 0.01
        result.portfolio_snapshots = snapshots
        self.assertNotEqual(original, result_digest(result))


class TestLoopInputs(TestCase):
    def test_simultaneous_symbols_use_deterministic_order(self):
        service, arguments = workload(32, 12)
        result = service.run(**arguments)
        by_timestamp = {}
        for order in result.orders:
            by_timestamp.setdefault(order.created_at, []).append(
                order.target_symbol)
        self.assertTrue(any(len(set(symbols)) > 1
                            for symbols in by_timestamp.values()))
        for symbols in by_timestamp.values():
            self.assertEqual(symbols, sorted(symbols))

    def test_positional_values_preserve_nullable_scalars(self):
        for values, dtype in (([1., float('nan')], 'float64'),
                              ([True, False], 'bool'),
                              ([1., pd.NA], 'Float64'),
                              ([True, pd.NA], 'boolean')):
            series = pd.Series(values, dtype=dtype, index=[7, 3])
            prepared = vector_module._loop_values(series)
            for position in range(len(series)):
                expected = series.iloc[position]
                actual = prepared[position]
                if expected is pd.NA:
                    self.assertIs(actual, pd.NA)
                elif pd.isna(expected):
                    self.assertTrue(pd.isna(actual))
                else:
                    self.assertEqual(expected, actual)
                    self.assertIs(type(expected), type(actual))
        self.assertEqual(0, len(vector_module._loop_values(
            pd.Series([], dtype='float64')
        )))

    def test_engine_matches_pandas_loop_inputs(self):
        for mode, dynamic in (
            (PositionMode.NETTING, False),
            (PositionMode.NETTING, True),
            (PositionMode.HEDGE, True),
        ):
            with self.subTest(mode=mode, dynamic=dynamic):
                digests = []
                for factory in (lambda series: series.iloc,
                                vector_module._loop_values):
                    service, arguments = workload(64, 3)
                    arguments['portfolio_configuration'] = (
                        PortfolioConfiguration(
                            market='BITVAVO', trading_symbol='EUR',
                            initial_balance=10000, position_mode=mode,
                        )
                    )
                    arguments['dynamic_position_sizing'] = dynamic
                    start = arguments['backtest_date_range'].start_date
                    with patch.object(
                        vector_module, '_loop_values', side_effect=factory,
                    ) as prepare, patch.object(
                        service, '_resolve_deposit_schedule',
                        return_value=[(start + timedelta(hours=16), 250.)],
                    ):
                        result = service.run(**arguments)
                    self.assertGreater(prepare.call_count, 0)
                    self.assertTrue(any(trade.is_short
                                        for trade in result.trades))
                    digests.append(result_digest(result))
                self.assertEqual(digests[0], digests[1])


class TestNativeLoopFallback(TestCase):
    def test_unsupported_inputs_are_rejected_before_native_execution(self):
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.vector_native import (
                NativeExecutionUnsupported, native_events,
            )

        for variant in (
            'nan', 'float32', 'nullable', 'nullable_scale', 'simultaneous',
            'scaling_rules', 'cooldowns', 'take_profits', 'stop_losses',
            'slippage', 'large_integer',
        ):
            data = {
                'close': np.array([10., 20.]),
                'trading_cost': TradingCost(),
                'initial_capital_for_trade': 50.,
                'pos_size_obj': PositionSize(fixed_amount=50.),
                'buy_signal': np.array([True, False]),
                'sell_signal': np.array([False, True]),
                'short_signal': np.array([False, False]),
                'cover_signal': np.array([False, False]),
                'scale_in_signal': np.array([False, False]),
                'scale_out_signal': np.array([False, False]),
            }
            strategy = SimpleNamespace()
            if variant == 'nan':
                data['close'][0] = np.nan
            elif variant == 'float32':
                data['close'] = data['close'].astype('float32')
            elif variant == 'nullable':
                data['buy_signal'] = pd.array([True, pd.NA], dtype='boolean')
            elif variant == 'nullable_scale':
                data['scale_out_signal'] = pd.array(
                    [False, pd.NA], dtype='boolean'
                )
            elif variant == 'simultaneous':
                data['short_signal'][0] = True
            elif variant == 'slippage':
                data['trading_cost'].slippage_percentage = 100.
            elif variant == 'large_integer':
                data['initial_capital_for_trade'] = 2 ** 53 + 1
            else:
                setattr(strategy, variant, [object()])
            with self.subTest(variant=variant):
                with self.assertRaises(NativeExecutionUnsupported):
                    native_events(
                        {'ASSET': data}, 2, 100., strategy,
                        dynamic_position_sizing=False, hedge_mode=False,
                        deposit_events=[],
                    )

    def test_missing_extension_and_runtime_errors(self):
        target = (
            'investing_algorithm_framework.infrastructure.services.'
            'backtesting.vector_native.native_events'
        )
        service, arguments = workload(32, 1)
        expected = result_digest(service.run(**arguments))
        with patch(target, side_effect=ImportError('missing')) as native:
            service, arguments = workload(32, 1)
            self.assertEqual(expected, result_digest(service.run(**arguments)))
            native.assert_not_called()
            self.assertEqual(expected, result_digest(service.run(
                **arguments, execution_backend='auto'
            )))
            with self.assertRaises(ImportError):
                service.run(**arguments, execution_backend='rust')
        with patch(target, side_effect=RuntimeError('kernel failure')):
            with self.assertRaisesRegex(RuntimeError, 'kernel failure'):
                service.run(**arguments, execution_backend='auto')
        with self.assertRaises(ValueError):
            service.run(**arguments, execution_backend='typo')


@skipUnless(find_spec('iaf_confluence_native'), 'Native wheel not installed')
class TestNativeRunLoop(TestCase):
    dynamic_modes = (False, True) if sys.version_info >= (3, 12) else (False,)

    def test_full_parity_with_capital_contention_and_random_signals(self):
        for randomized in (False, True):
            for percentage in (0, 20, 60):
                digests = []
                for backend in ('python', 'rust', 'auto'):
                    service, arguments = workload(128, 3)
                    strategy = arguments['strategy']
                    strategy.position_sizes = [PositionSize(
                        symbol=symbol, percentage_of_portfolio=percentage
                    ) for symbol in strategy.symbols]
                    if randomized:
                        def signals(data):
                            random = np.random.default_rng(73)
                            for symbol in strategy.symbols:
                                index = data[f'{symbol}/EUR'].index
                                entries = random.integers(0, 3, len(index))
                                for side, values in (
                                    (SignalSide.OPEN_LONG, entries == 1),
                                    (SignalSide.CLOSE_LONG,
                                     random.random(len(index)) < .4),
                                    (SignalSide.OPEN_SHORT, entries == 2),
                                    (SignalSide.CLOSE_SHORT,
                                     random.random(len(index)) < .4),
                                ):
                                    yield SignalSeries(
                                        symbol=symbol, side=side,
                                        series=pd.Series(values, index=index),
                                    )
                        strategy.generate_signal_series = signals
                    with self.subTest(randomized=randomized,
                                      percentage=percentage, backend=backend):
                        result = service.run(
                            **arguments, execution_backend=backend
                        )
                        digests.append(result_digest(result))
                self.assertEqual(digests[0], digests[1])
                self.assertEqual(digests[0], digests[2])

    def test_unsupported_modes_fail_or_fall_back(self):
        from investing_algorithm_framework.infrastructure.services \
            .backtesting.vector_native import NativeExecutionUnsupported

        variants = ('hedge',) if sys.version_info >= (3, 12) else (
            'hedge', 'dynamic',
        )
        for variant in variants:
            service, arguments = workload(32, 1)
            if variant == 'dynamic':
                arguments['dynamic_position_sizing'] = True
            if variant in ('hedge', 'fees'):
                arguments['portfolio_configuration'] = PortfolioConfiguration(
                    market='BITVAVO', trading_symbol='EUR',
                    initial_balance=10000,
                    position_mode=(PositionMode.HEDGE if variant == 'hedge'
                                   else PositionMode.NETTING),
                    fee_percentage=.1 if variant == 'fees' else 0,
                )
            start = arguments['backtest_date_range'].start_date
            deposits = [(start, 250.)] if variant == 'deposits' else []
            with self.subTest(variant=variant), patch.object(
                service, '_resolve_deposit_schedule', return_value=deposits,
            ):
                with self.assertRaises(NativeExecutionUnsupported):
                    service.run(**arguments, execution_backend='rust')
                self.assertEqual(
                    result_digest(service.run(**arguments)),
                    result_digest(service.run(
                        **arguments, execution_backend='auto'
                    )),
                )

    def test_costs_sizing_and_deposits_match_python(self):
        for dynamic in self.dynamic_modes:
            for fixed in (False, True):
                for fixed_fee in (0., 1.75, 20000.):
                    results = []
                    for backend in ('python', 'rust'):
                        service, arguments = workload(96, 3)
                        strategy = arguments['strategy']
                        strategy.position_sizes = [PositionSize(
                            symbol=symbol,
                            fixed_amount=1700. if fixed else None,
                            percentage_of_portfolio=None if fixed else 35.,
                        ) for symbol in strategy.symbols]
                        arguments['portfolio_configuration'] = (
                            PortfolioConfiguration(
                                market='BITVAVO', trading_symbol='EUR',
                                initial_balance=10000.,
                                trading_costs=[TradingCost(
                                    symbol=symbol, fee_percentage=.13,
                                    fee_fixed=fixed_fee,
                                    slippage_percentage=.27,
                                ) for symbol in strategy.symbols],
                            )
                        )
                        arguments['dynamic_position_sizing'] = dynamic
                        start = arguments['backtest_date_range'].start_date
                        deposits = [
                            (start - timedelta(hours=1), 100.),
                            (start + timedelta(hours=15, minutes=30), 250.),
                            (start + timedelta(hours=15, minutes=45), 10.),
                            (start + timedelta(hours=120), 999.),
                        ]
                        with patch.object(
                            service, '_resolve_deposit_schedule',
                            return_value=deposits,
                        ):
                            results.append(service.run(
                                **arguments, execution_backend=backend
                            ))
                    with self.subTest(dynamic=dynamic, fixed=fixed,
                                      fixed_fee=fixed_fee):
                        expected, actual = results
                        self.assertEqual(
                            [(order.price, order.amount, order.order_fee)
                             for order in expected.orders],
                            [(order.price, order.amount, order.order_fee)
                             for order in actual.orders],
                        )
                        self.assertEqual(
                            [(trade.cost, trade.net_gain, trade.total_fees)
                             for trade in expected.trades],
                            [(trade.cost, trade.net_gain, trade.total_fees)
                             for trade in actual.trades],
                        )
                        self.assertEqual(360., sum(
                            snapshot.cash_flow or 0
                            for snapshot in actual.portfolio_snapshots
                        ))
                        self.assertEqual(result_digest(expected),
                                         result_digest(actual))

    def test_opposite_signal_flips_match_python(self):
        for dynamic in self.dynamic_modes:
            results = []
            for backend in ('python', 'rust'):
                service, arguments = workload(96, 3)
                strategy = arguments['strategy']
                strategy.flip_on_opposite_signal = True

                def signals(data):
                    for symbol in strategy.symbols:
                        index = data[f'{symbol}/EUR'].index
                        for side, offset in (
                            (SignalSide.OPEN_LONG, 0),
                            (SignalSide.OPEN_SHORT, 2),
                            (SignalSide.CLOSE_LONG, -1),
                            (SignalSide.CLOSE_SHORT, -1),
                        ):
                            yield SignalSeries(
                                symbol=symbol, side=side,
                                series=pd.Series(
                                    np.arange(len(index)) % 4 == offset,
                                    index=index,
                                ),
                            )

                strategy.generate_signal_series = signals
                arguments['dynamic_position_sizing'] = dynamic
                results.append(service.run(
                    **arguments, execution_backend=backend
                ))
            with self.subTest(dynamic=dynamic):
                self.assertTrue(any(
                    event['reason'] == 'flip_on_opposite_signal'
                    for event in results[1].signal_events
                ))
                self.assertEqual(result_digest(results[0]),
                                 result_digest(results[1]))

    def test_cooldown_scope_and_sides_match_python(self):
        from investing_algorithm_framework.domain import CooldownRule

        for scope in (None, 'ASSET0'):
            for trigger in ('buy', 'sell', 'any'):
                for blocks in ('buy', 'sell', 'any'):
                    results = []
                    for backend in ('python', 'rust'):
                        service, arguments = workload(48, 3)
                        arguments['strategy'].cooldowns = [CooldownRule(
                            symbol=scope, trigger=trigger, blocks=blocks,
                            bars=5,
                        )]
                        results.append(service.run(
                            **arguments, execution_backend=backend
                        ))
                    with self.subTest(scope=scope, trigger=trigger,
                                      blocks=blocks):
                        self.assertTrue(any(
                            event['reason'] == 'in_cooldown_rule'
                            for event in results[1].signal_events
                        ))
                        self.assertEqual(result_digest(results[0]),
                                         result_digest(results[1]))

    def test_fixed_risk_exits_match_python(self):
        from investing_algorithm_framework.domain import (
            CooldownRule, TakeProfitRule, StopLossRule,
        )

        for threshold in (0., .15):
            for rule_name in ('take_profits', 'stop_losses', 'both'):
                for cooldown in (0, 3):
                    results = []
                    for backend in ('python', 'rust'):
                        service, arguments = workload(64, 3)
                        strategy = arguments['strategy']
                        for name, rule_type in (
                            ('take_profits', TakeProfitRule),
                            ('stop_losses', StopLossRule),
                        ):
                            if rule_name in (name, 'both'):
                                setattr(strategy, name, [rule_type(
                                    symbol=None,
                                    percentage_threshold=threshold,
                                    sell_percentage=25., side='short',
                                )])
                        strategy.cooldowns = [CooldownRule(
                            trigger='any', blocks='any', bars=cooldown,
                        )]
                        arguments['dynamic_position_sizing'] = (
                            sys.version_info >= (3, 12)
                        )
                        results.append(service.run(
                            **arguments, execution_backend=backend
                        ))
                    with self.subTest(threshold=threshold, rules=rule_name,
                                      cooldown=cooldown):
                        self.assertTrue(any(
                            event['signal'] in ('take_profit', 'stop_loss')
                            for event in results[1].signal_events
                        ))
                        self.assertEqual(result_digest(results[0]),
                                         result_digest(results[1]))

    def test_combined_controls_match_python(self):
        from investing_algorithm_framework.domain import (
            CooldownRule, TakeProfitRule, StopLossRule,
        )

        for seed in range(4):
            for dynamic in self.dynamic_modes:
                results = []
                for backend in ('python', 'rust', 'auto'):
                    service, arguments = workload(128, 3)
                    strategy = arguments['strategy']
                    strategy.flip_on_opposite_signal = True
                    strategy.cooldowns = [
                        CooldownRule(trigger='sell', blocks='buy', bars=seed),
                        CooldownRule(symbol='ASSET0', trigger='buy',
                                     blocks='sell', bars=3),
                    ]
                    strategy.take_profits = [TakeProfitRule(
                        symbol='ASSET1', percentage_threshold=.2,
                        sell_percentage=100.,
                    )]
                    strategy.stop_losses = [StopLossRule(
                        symbol=None, percentage_threshold=.15,
                        sell_percentage=100.,
                    )]

                    def signals(data):
                        random = np.random.default_rng(seed)
                        for symbol in strategy.symbols:
                            index = data[f'{symbol}/EUR'].index
                            entries = random.integers(0, 3, len(index))
                            for side, values in (
                                (SignalSide.OPEN_LONG, entries == 1),
                                (SignalSide.CLOSE_LONG,
                                 random.random(len(index)) < .4),
                                (SignalSide.OPEN_SHORT, entries == 2),
                                (SignalSide.CLOSE_SHORT,
                                 random.random(len(index)) < .4),
                            ):
                                yield SignalSeries(
                                    symbol=symbol, side=side,
                                    series=pd.Series(values, index=index),
                                )

                    strategy.generate_signal_series = signals
                    arguments['dynamic_position_sizing'] = dynamic
                    arguments['portfolio_configuration'] = (
                        PortfolioConfiguration(
                            market='BITVAVO', trading_symbol='EUR',
                            initial_balance=10000., trading_costs=[TradingCost(
                                fee_percentage=.13, fee_fixed=1.75,
                                slippage_percentage=.27,
                            )],
                        )
                    )
                    start = arguments['backtest_date_range'].start_date
                    with patch.object(service, '_resolve_deposit_schedule',
                                      return_value=[
                                          (start + timedelta(hours=7.5), 250.),
                                      ]):
                        results.append(service.run(
                            **arguments, execution_backend=backend
                        ))
                with self.subTest(seed=seed, dynamic=dynamic):
                    self.assertGreater(len(results[1].trades), 0)
                    self.assertEqual(result_digest(results[0]),
                                     result_digest(results[1]))
                    self.assertEqual(result_digest(results[0]),
                                     result_digest(results[2]))

    def test_accounting_boundary_rules_and_empty_batches(self):
        from iaf_confluence_native import run_netting

        empty = run_netting([], [], [], (3, 100., False, False),
                            [(1, 20.)], ([], []))
        self.assertEqual([], empty.events)
        np.testing.assert_array_equal(
            np.frombuffer(empty.snapshot_bytes(), dtype='<f8').reshape(3, 4),
            [[100., 100., 0., 0.], [120., 120., 0., 20.],
             [120., 120., 0., 0.]],
        )
        self.assertEqual(b'', empty.position_bytes())
        specs = [(50., 50., None, 0., 0., 0.)]
        prices = [np.array([10., 10., 10., 10.], dtype='<f8').tobytes()]
        cooldown = run_netting(
            prices, [bytes([1, 2, 1, 1])], specs,
            (4, 100., False, False), [], ([(None, 1, 0, 2)], [[]]),
        )
        self.assertEqual([0, 0, 7, 0],
                         [event.reason for event in cooldown.events])
        for entry, exit_side in ((1, 1), (4, 3)):
            tie = run_netting(
                prices, [bytes([entry, 0, 0, 0])], specs,
                (4, 100., False, False), [],
                ([], [[(True, 0.), (False, 0.)]]),
            )
            self.assertEqual((1, exit_side, 8), (
                tie.events[1].row, tie.events[1].side, tie.events[1].reason,
            ))
        for controls in (
            ([], []), ([(1, 0, 0, 1)], [[]]),
            ([(None, 3, 0, 1)], [[]]), ([], [[(True, float('nan'))]]),
        ):
            with self.assertRaises(ValueError):
                run_netting(prices, [bytes([1, 0, 0, 0])], specs,
                            (4, 100., False, False), [], controls)

    def test_native_input_validation_and_empty_batches(self):
        from iaf_confluence_native import run_static_netting

        self.assertEqual([], run_static_netting([], [], [], 100., 0))
        self.assertEqual([], run_static_netting([b''], [b''], [50.], 100., 0))
        price = np.array([10.], dtype='<f8').tobytes()
        for prices, signals, capital in (
            ([price], [b'\x05'], [50.]),
            ([price], [b'\xff'], [50.]),
            ([b'bad'], [b'\x01'], [50.]),
            ([price], [], [50.]),
            ([price], [b'\x01'], [float('nan')]),
            ([np.array([0.], dtype='<f8').tobytes()], [b'\x01'], [50.]),
        ):
            with self.assertRaises(ValueError):
                run_static_netting(prices, signals, capital, 100., 1)
