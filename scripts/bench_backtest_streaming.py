"""Offline real-strategy/process-boundary and bounded-writer measurements.

Run from the repository root with python -m scripts.bench_backtest_streaming.
JSON goes to stdout; --output stores raw measurements. No fixture writes.
"""
import argparse
from collections import Counter, deque
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from copy import copy
import cProfile
import gc
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import multiprocessing
from pathlib import Path
import pickle
import platform
import pstats
import tempfile
import threading
from time import perf_counter
import traceback
import tracemalloc
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import psutil
import pyarrow as arrow

from investing_algorithm_framework import (
    Backtest, BacktestDateRange, BacktestEngine, BacktestRunConfiguration,
    BacktestWindow, CSVOHLCVDataProvider, PortfolioConfiguration, PositionSize,
    RESOURCE_DIRECTORY, Schedule, SnapshotInterval, Study, TimeUnit, Universe,
    create_app,
)
from investing_algorithm_framework.domain import (
    CooldownRule, StopLossRule, TakeProfitRule,
)
from investing_algorithm_framework.domain.backtesting.bundle import save_bundle
from investing_algorithm_framework.infrastructure.services.backtesting import (
    vector_backtest_service as vector_module,
)
from investing_algorithm_framework.services.backtest_store import (
    LocalTieredStore,
)
from investing_algorithm_framework.services.metrics.generate import (
    create_backtest_metrics,
)
from scripts.bench_vector_snapshot_events import result_digest
from tests.resources.strategies_for_testing.strategy_v1 import (
    CrossOverStrategyV1,
)
from tests.scenarios.vectorized_backtests.test_run_vector_backtest import (
    RSIEMACrossoverStrategy,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/resources/test_data/ohlcv'
FILES = {
    'BTC': FIXTURE / (
        'OHLCV_BTC-EUR_BITVAVO_2h_2021-09-26-08-00_2023-12-02-00-00.csv'
    ),
    'DOT': FIXTURE / (
        'OHLCV_DOT-EUR_BITVAVO_2h_2021-12-15-08-00_2023-12-31-00-00.csv'
    ),
}


@contextmanager
def python_data_path(mode):
    if mode == 'optimized':
        yield
        return
    if mode != 'baseline':
        raise ValueError('Unknown Python data path')
    from sqlalchemy import inspect
    from investing_algorithm_framework.infrastructure.repositories \
        .event_memory import EventMemoryState
    from investing_algorithm_framework.infrastructure.repositories \
        .event_snapshot_archive import EventAccountingArchive

    def select(archive, params, *, order=False, ascending=False):
        archive.flush()
        clauses = ['size > 0']
        parameters = []
        columns = inspect(archive.model).columns
        for key, value in params.items():
            if key not in columns or (
                    key not in archive._query_fields and key != 'id'):
                continue
            if value is None:
                continue
            field = 'identity' if key == 'id' else key
            clauses.append(f'{field} = ?')
            parameters.append(str(value) if key == 'id'
                              else archive._query_value(value))
        ordering = 'sequence'
        if order:
            direction = 'ASC' if ascending else 'DESC'
            ordering = (
                f'created_at {direction}, target_symbol, trading_symbol, '
                'strategy_id, order_side, order_type, price, amount, '
                'length(identity), identity'
            )
        cursor = archive.locations.execute(
            'SELECT identity FROM locations WHERE '
            + ' AND '.join(clauses) + f' ORDER BY {ordering}', parameters,
        )
        try:
            for row in cursor:
                yield archive[int(row[0])]
        finally:
            cursor.close()

    def convert(data, remove_duplicates=True, add_index=True,
                add_datetime_column=True, datetime_column_name='Datetime'):
        frame = data.to_pandas().copy()
        if add_datetime_column and datetime_column_name not in frame:
            frame[datetime_column_name] = pd.to_datetime(frame.index)
        frame[datetime_column_name] = pd.to_datetime(
            frame[datetime_column_name])
        if remove_duplicates:
            frame = frame.drop_duplicates(datetime_column_name, keep='first')
        if add_index:
            frame.set_index(datetime_column_name, inplace=True)
        return frame

    with ExitStack() as stack:
        stack.enter_context(patch.object(EventAccountingArchive, 'select',
                                         new=select))
        stack.enter_context(patch.object(
            EventMemoryState, '_read_result',
            new=lambda state, value: state._clone(value, eager_only=True),
        ))
        for name in ('csv', 'ccxt', 'pandas', 'ohlcv_base'):
            module = importlib.import_module(
                'investing_algorithm_framework.infrastructure.data_providers.'
                + name)
            stack.enter_context(patch.object(
                module, 'convert_polars_to_pandas', new=convert))
        yield


@contextmanager
def preparation_path(mode):
    from investing_algorithm_framework.domain.utils.polars import \
        convert_polars_to_pandas
    from investing_algorithm_framework.services.order_service.order_service \
        import OrderService

    counts = Counter()
    get_all = OrderService.get_all

    def orders(service, query_params=None):
        if query_params and 'created_at_gt' in query_params:
            counts['cooldown_queries'] += 1
            if mode == 'baseline':
                query_params = {key: value for key, value in query_params.items()
                                if key != 'created_at_gt'}
        return get_all(service, query_params)

    def convert(data, remove_duplicates=True, add_index=True,
                add_datetime_column=True, datetime_column_name='Datetime'):
        counts['conversions'] += 1
        if mode == 'optimized':
            return convert_polars_to_pandas(
                data, remove_duplicates, add_index, add_datetime_column,
                datetime_column_name)
        frame = data.to_pandas()
        if add_datetime_column and datetime_column_name not in frame:
            frame[datetime_column_name] = pd.to_datetime(frame.index)
        if not pd.api.types.is_datetime64_any_dtype(
                frame[datetime_column_name].dtype):
            frame[datetime_column_name] = pd.to_datetime(
                frame[datetime_column_name])
        if remove_duplicates:
            frame = frame.drop_duplicates(datetime_column_name, keep='first')
        if add_index:
            frame.set_index(datetime_column_name, inplace=True)
        return frame

    with ExitStack() as stack:
        stack.enter_context(patch.object(OrderService, 'get_all', new=orders))
        stack.enter_context(patch(
            'investing_algorithm_framework.services.data_providers.'
            'data_provider_service.convert_polars_to_pandas', new=convert))
        for name in ('csv', 'ccxt', 'pandas', 'ohlcv_base'):
            module = importlib.import_module(
                'investing_algorithm_framework.infrastructure.data_providers.'
                + name)
            stack.enter_context(patch.object(
                module, 'convert_polars_to_pandas', new=convert))
        yield counts


@contextmanager
def archive_decoder(mode):
    if mode == 'optimized':
        yield
        return
    from sqlalchemy import inspect
    from sqlalchemy.orm.attributes import set_committed_value
    from investing_algorithm_framework.infrastructure.repositories \
        .event_snapshot_archive import EventSnapshotArchive

    def read(archive, offset, size):
        archive.records.seek(offset)
        payload = archive.records.read(size)
        if len(payload) != size:
            raise OSError('Truncated event snapshot archive')
        fields, relations = pickle.loads(payload)
        mapper = inspect(archive.model)
        value = mapper.class_manager.new_instance()
        for key, item in fields.items():
            if key in mapper.attrs:
                set_committed_value(value, key, item)
            else:
                value.__dict__[key] = item
        for key, identities in relations.items():
            relation = mapper.relationships[key]
            table = archive.state._table(relation.mapper.class_)
            related = [table[item] for item in identities if item in table]
            set_committed_value(value, key, related)
        return value

    with patch.object(EventSnapshotArchive, '_read', new=read):
        yield


class MemorySampler:
    """Sample summed RSS; shared pages count twice, unlike physical memory."""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.phase = 'startup'
        self.peaks = {}
        self.samples = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        process = psutil.Process()
        while not self.stop.is_set():
            total = 0
            try:
                processes = [process] + process.children(recursive=True)
            except psutil.Error:
                processes = [process]
            for member in processes:
                try:
                    total += member.memory_info().rss
                except psutil.Error:
                    pass
            phase = self.phase
            self.peaks[phase] = max(total, self.peaks.get(phase, 0))
            self.samples += 1
            self.stop.wait(.01)

    def __enter__(self):
        if self.enabled:
            self.thread.start()
        return self

    def __exit__(self, *args):
        if self.enabled:
            self.stop.set()
            self.thread.join()


class ProfiledCrossOver(CrossOverStrategyV1):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.risk_counts = Counter()

    def on_trade_stop_loss_triggered(self, context, trade):
        self.risk_counts['stop_loss'] += 1

    def on_trade_take_profit_triggered(self, context, trade):
        self.risk_counts['take_profit'] += 1


def strategy_for(name, symbols, event=False):
    if name == 'ema':
        strategy_type = ProfiledCrossOver if event else CrossOverStrategyV1
        strategy = strategy_type(symbols=symbols)
    else:
        strategy = RSIEMACrossoverStrategy(
            algorithm_id='rsi-ema-profile', symbols=symbols,
            position_sizes=[], schedule=Schedule.every(2, TimeUnit.HOUR),
            market='BITVAVO', rsi_time_frame='2h', rsi_period=14,
            rsi_overbought_threshold=65, rsi_oversold_threshold=45,
            ema_time_frame='2h', ema_short_period=50, ema_long_period=100,
            ema_cross_lookback_window=4,
        )
    strategy.position_sizes = [PositionSize(
        symbol=symbol, percentage_of_portfolio=40 / len(symbols),
    ) for symbol in symbols]
    strategy.position_sizes_lookup = {}
    strategy.data_sources = [replace(source, warmup_window=600)
                             for source in strategy.data_sources]
    strategy.take_profits = [TakeProfitRule(
        symbol=symbol, percentage_threshold=3., sell_percentage=100.,
    ) for symbol in symbols]
    strategy.stop_losses = [StopLossRule(
        symbol=symbol, percentage_threshold=2., sell_percentage=100.,
    ) for symbol in symbols]
    strategy.cooldowns = [CooldownRule(trigger='sell', blocks='buy', bars=3)]
    return strategy


def vector_case(strategy, date_range, backend):
    frames = {}
    for symbol in strategy.symbols:
        frame = pd.read_csv(FILES[symbol])
        frame['Datetime'] = pd.to_datetime(frame['Datetime'], utc=True)
        frame = frame.set_index('Datetime').sort_index()
        frames[f'{symbol}/EUR'] = frame.loc[
            date_range.start_date - timedelta(hours=1200):date_range.end_date
        ]
    inputs = {source.identifier: frames[source.symbol]
              for source in strategy.data_sources}
    provider = SimpleNamespace(
        get_vectorized_backtest_data=lambda **kwargs: inputs,
        get_ohlcv_data=lambda symbol, **kwargs: frames[symbol].loc[
            date_range.start_date:date_range.end_date
        ],
    )
    service = vector_module.VectorBacktestService(provider)
    return lambda: service.run(
        strategy=strategy, backtest_date_range=date_range,
        portfolio_configuration=PortfolioConfiguration(
            market='BITVAVO', trading_symbol='EUR', initial_balance=10000,
        ), dynamic_position_sizing=True, execution_backend=backend,
    )


def event_case(strategy, date_range, directory, event_fill_backend='python',
               event_schedule_backend='python', event_state_backend='sql',
               vector_backend=None):
    app = create_app(config={RESOURCE_DIRECTORY: directory})
    app.add_market(
        market='BITVAVO',
        trading_symbol='EUR',
        initial_balance=10000)
    for symbol in strategy.symbols:
        app.add_data_provider(CSVOHLCVDataProvider(
            symbol=f'{symbol}/EUR', market='BITVAVO', time_frame='2h',
            storage_path=str(FILES[symbol]), warmup_window=600,
        ))

    def execute():
        results = app.run_backtest(
            strategy=strategy,
            study=Study(
                universe=Universe(market='BITVAVO', trading_symbol='EUR'),
                backtest_windows=[BacktestWindow(train_range=date_range)],
                engines=[BacktestEngine.VECTOR if vector_backend
                         else BacktestEngine.EVENT_DRIVEN],
            ),
            run_configuration=BacktestRunConfiguration(
                snapshot_interval=SnapshotInterval.DAILY, show_progress=False,
                event_fill_backend=event_fill_backend, continue_on_error=False,
                event_schedule_backend=event_schedule_backend,
                event_state_backend=event_state_backend,
                execution_backend=vector_backend or 'python',
            ),
        )
        backtest = next(results.iter_backtests())
        return (backtest.vector_runs if vector_backend
                else backtest.event_runs)[0]
    return execute


def acceptance_sweep(directory, count, days, backend, workers,
                     hard_memory_limit_mb=None, event_state_backend='sql'):
    import sys
    from investing_algorithm_framework.domain.backtesting.backtest_run \
        import _deserialise_signal_events
    from investing_algorithm_framework.services.backtest_store.recording \
        import iter_signal_reports

    directory.mkdir(parents=True, exist_ok=False)
    app = create_app(config={RESOURCE_DIRECTORY: str(directory / 'resources')})
    for symbol in ('BTC', 'DOT'):
        app.add_data_provider(CSVOHLCVDataProvider(
            symbol=f'{symbol}/EUR', market='BITVAVO', time_frame='2h',
            storage_path=str(FILES[symbol]), warmup_window=600,
        ))
    end = datetime(2023, 12, 2, tzinfo=timezone.utc)
    study = Study(
        name='streaming-acceptance', initial_capital=10000,
        universe=Universe(market='BITVAVO', trading_symbol='EUR',
                          symbols=['BTC', 'DOT']),
        backtest_windows=[BacktestWindow(train_range=BacktestDateRange(
            start_date=end - timedelta(days=days), end_date=end,
        ))],
        engines=[BacktestEngine.EVENT_DRIVEN if backend == 'event'
                 else BacktestEngine.VECTOR],
    )

    def strategies():
        result = []
        for number in range(count):
            strategy = strategy_for('ema', ['BTC', 'DOT'],
                                    event=backend == 'event')
            strategy.algorithm_id = f'acceptance-{number:03d}'
            strategy.strategy_id = strategy.algorithm_id
            strategy.position_sizes = [PositionSize(
                symbol=symbol, percentage_of_portfolio=10 + number / 10,
            ) for symbol in strategy.symbols]
            result.append(strategy)
        return result

    cases = []
    expected = {}
    for recorded in (False, True):
        label = 'recorded' if recorded else 'baseline'
        print(
            f'Sweep {backend}: {count} algorithms, {days} days, '
            f'{workers} workers; starting {label}',
            file=sys.stderr, flush=True,
        )
        root = directory / label
        configuration = BacktestRunConfiguration(
            backtest_storage_directory=root / 'bundles',
            signal_storage_directory=root / 'signals' if recorded else None,
            execution_backend=backend if backend != 'event' else 'python',
            n_workers=workers, max_tasks_per_child=8,
            snapshot_interval=SnapshotInterval.DAILY,
            show_progress=False, continue_on_error=False,
            dynamic_position_sizing=True,
            hard_memory_limit_mb=hard_memory_limit_mb,
            event_state_backend=event_state_backend,
        )
        with MemorySampler() as memory:
            memory.phase = 'execute_transfer_save'
            started = perf_counter()
            index = app.run_backtest(strategies=strategies(), study=study,
                                     run_configuration=configuration)
            elapsed = perf_counter() - started
            print(
                f'Sweep {backend}/{label}: execution and saving finished '
                f'in {elapsed:.1f}s; validating saved results',
                file=sys.stderr, flush=True,
            )
            memory.phase = 'lazy_validation'
            actual = {}
            signals = trades = snapshots = 0
            for backtest in index.iter_backtests():
                runs = (backtest.event_runs if backend == 'event'
                        else backtest.vector_runs)
                if len(runs) != 1:
                    raise AssertionError('Expected one completed window')
                backtest_run = runs[0]
                if recorded:
                    reference = backtest_run.metadata['signal_history']
                    reports = iter_signal_reports(root / 'signals', reference)
                    if backend != 'event':
                        backtest_run.signal_events = (
                            _deserialise_signal_events(list(reports)))
                    else:
                        report_count = sum(1 for _ in reports)
                        if report_count != 12 * days + 1:
                            raise AssertionError('Missing event signal reports')
                    signals += reference['count']
                actual[backtest.algorithm_id] = result_digest(backtest_run)
                trades += len(backtest_run.trades)
                snapshots += len(backtest_run.portfolio_snapshots)
            if len(actual) != count or trades == 0:
                raise AssertionError('Incomplete or inactive acceptance sweep')
            if recorded and expected != actual:
                raise AssertionError('Recorded results differ from baseline')
            if not recorded:
                expected = actual
            memory.phase = 'resume'
            print(
                f'Sweep {backend}/{label}: {len(actual)} results validated; '
                'checking checkpoint resume', file=sys.stderr, flush=True,
            )
            before = set(root.glob('signals/streams/*/*/manifest.json'))
            started = perf_counter()
            resumed = app.run_backtest(strategies=strategies(), study=study,
                                       run_configuration=configuration)
            resume_s = perf_counter() - started
            pd.testing.assert_frame_equal(index.df, resumed.df)
            after = set(root.glob('signals/streams/*/*/manifest.json'))
            if before != after or (recorded and len(after) != count):
                raise AssertionError('Resume reran completed recordings')
        cases.append({
            'recorded': recorded, 'algorithms': len(actual), 'days': days,
            'backend': backend, 'workers': workers, 'wall_s': elapsed,
            'event_state_backend': event_state_backend,
            'resume_s': resume_s, 'trades': trades, 'snapshots': snapshots,
            'signal_reports': signals, 'tree_peak_rss_bytes': memory.peaks,
            'memory_samples': memory.samples,
            'storage_bytes': sum(path.stat().st_size for path in root.rglob('*')
                                 if path.is_file()),
            'hard_memory_limit_mb': hard_memory_limit_mb,
            'exact_saved_result_parity': True,
        })
        print(
            f'Sweep {backend}/{label}: complete; resume {resume_s:.1f}s',
            file=sys.stderr, flush=True,
        )
    return cases, expected


def worker(connection, case):
    try:
        with tempfile.TemporaryDirectory(prefix='iaf-prof-') as directory:
            sample_rss = not case['profile'] and case.get('sample_rss', True)
            with MemorySampler(enabled=sample_rss) as memory:
                started = perf_counter()
                date_range = BacktestDateRange(
                    start_date=datetime(2023, 12, 2, tzinfo=timezone.utc)
                    - timedelta(days=case['days']),
                    end_date=datetime(2023, 12, 2, tzinfo=timezone.utc),
                )
                strategy = strategy_for(case['strategy'], case['symbols'],
                                        event=case['backend'] == 'event')
                execute = (event_case(
                    strategy, date_range, directory,
                    case.get('event_fill_backend', 'python'),
                    case.get('event_schedule_backend', 'python'),
                    case.get('event_state_backend', 'sql'),
                    vector_backend=(case['backend']
                                    if case['backend'] != 'event' else None))
                           if (case['backend'] == 'event'
                               or case.get('real_vector_data')) else vector_case(
                               strategy, date_range, case['backend']))
                preparation = perf_counter() - started
                profiler = cProfile.Profile() if case['profile'] else None
                metrics_seconds = 0.0
                metrics_calls = 0
                native_fill_calls = 0
                native_schedule_calls = 0
                event_tick_sql_statements = 0
                event_ticks = 0
                inside_event_tick = False

                from sqlalchemy import event
                from sqlalchemy.engine import Engine
                from investing_algorithm_framework.app.eventloop import \
                    EventLoopService

                run_iteration = EventLoopService._run_iteration

                def count_statement(*args):
                    nonlocal event_tick_sql_statements
                    if inside_event_tick:
                        event_tick_sql_statements += 1

                def measured_iteration(loop, *args, **kwargs):
                    nonlocal inside_event_tick, event_ticks
                    event_ticks += 1
                    inside_event_tick = True
                    try:
                        return run_iteration(loop, *args, **kwargs)
                    finally:
                        inside_event_tick = False

                from investing_algorithm_framework.app.native_schedule import \
                    load_native_schedule

                def load_schedule():
                    runner = load_native_schedule()

                    def run_schedule(*args):
                        nonlocal native_schedule_calls
                        native_schedule_calls += 1
                        return runner(*args)

                    return run_schedule

                from investing_algorithm_framework.services \
                    .trade_order_evaluator.native import select_native_fill

                def select_fill(*args, **kwargs):
                    nonlocal native_fill_calls
                    native_fill_calls += 1
                    return select_native_fill(*args, **kwargs)

                def calculate_metrics(*args, **kwargs):
                    nonlocal metrics_seconds, metrics_calls
                    kwargs['metrics_backend'] = case.get(
                        'metrics_backend', 'python')
                    metric_start = perf_counter()
                    previous_phase = memory.phase
                    memory.phase = 'metrics'
                    value = create_backtest_metrics(*args, **kwargs)
                    memory.peaks['metrics'] = max(
                        memory.peaks.get('metrics', 0),
                        psutil.Process().memory_info().rss,
                    )
                    memory.phase = previous_phase
                    metrics_seconds += perf_counter() - metric_start
                    metrics_calls += 1
                    return value

                memory.phase = 'execution'
                if profiler:
                    profiler.enable()
                with ExitStack() as stack:
                    preparation_counts = stack.enter_context(preparation_path(
                        case.get('preparation_path', 'optimized')))
                    stack.enter_context(archive_decoder(
                        case.get('archive_decoder', 'optimized')))
                    stack.enter_context(python_data_path(
                        case.get('python_data_path', 'optimized')))
                    input_mode = case.get('metric_inputs', 'compact')
                    if input_mode != 'compact':
                        def prepare_inputs(run):
                            if input_mode == 'legacy':
                                return run
                            working = copy(run)
                            for field in ('trades', 'portfolio_snapshots'):
                                object.__setattr__(working, field,
                                                   list(getattr(run, field)))
                            return working
                        stack.enter_context(patch(
                            'investing_algorithm_framework.services.metrics.'
                            'generate.prepare_metric_inputs',
                            new=prepare_inputs,
                        ))
                    if case['backend'] == 'event':
                        event.listen(Engine, 'before_cursor_execute',
                                     count_statement)
                        stack.callback(
                            event.remove, Engine, 'before_cursor_execute',
                            count_statement,
                        )
                        stack.enter_context(patch.object(
                            EventLoopService, '_run_iteration',
                            new=measured_iteration,
                        ))
                    if (case.get('event_schedule_backend') == 'rust'
                            or case.get('event_state_backend') == 'rust'):
                        stack.enter_context(patch(
                            'investing_algorithm_framework.app.'
                            'native_schedule.load_native_schedule',
                            new=load_schedule,
                        ))
                    if (case.get('event_fill_backend') == 'rust'
                            or case.get('event_state_backend') == 'rust'):
                        stack.enter_context(patch(
                            'investing_algorithm_framework.services.'
                            'trade_order_evaluator.native.select_native_fill',
                            new=select_fill,
                        ))
                    for module in (
                        'backtest_service', 'event_backtest_service',
                        'vector_backtest_service',
                    ):
                        stack.enter_context(patch(
                            'investing_algorithm_framework.infrastructure.'
                            f'services.backtesting.{module}.'
                            'create_backtest_metrics', new=calculate_metrics,
                        ))
                    started = perf_counter()
                    result = execute()
                    execution = perf_counter() - started
                if metrics_calls == 0:
                    raise AssertionError('Selected metrics backend was unused')
                if (case.get('event_state_backend') == 'memory'
                        and (event_ticks == 0 or event_tick_sql_statements)):
                    raise AssertionError('Memory ticks must run without SQL')
                if (case.get('event_fill_backend') == 'rust'
                        and native_fill_calls == 0):
                    raise AssertionError('Native event fills were unused')
                if (case.get('event_schedule_backend') == 'rust'
                        and native_schedule_calls == 0):
                    raise AssertionError('Native event scheduler was unused')
                if profiler:
                    profiler.disable()
                memory.phase = 'digest'
                digest = result_digest(result)
                signal_counts = Counter(item.get('signal')
                                        for item in result.signal_events)
                memory.phase = 'pickle'
                started = perf_counter()
                payload = pickle.dumps(
                    result, protocol=pickle.HIGHEST_PROTOCOL)
                serialization = perf_counter() - started
                top = []
                if profiler:
                    stats = pstats.Stats(profiler)
                    for key, value in sorted(stats.stats.items(),
                                             key=lambda item: item[1][3],
                                             reverse=True)[:100]:
                        filename = Path(key[0])
                        relative = (str(filename.relative_to(ROOT))
                                    if filename.is_relative_to(ROOT) else key[0])
                        top.append({'file': relative,
                                    'line': key[1], 'function': key[2],
                                    'calls': value[1], 'self_s': value[2],
                                    'cumulative_s': value[3]})
                metadata = dict(
                    preparation_s=preparation, execution_s=execution,
                    preparation_counts=dict(preparation_counts),
                    metrics_s=metrics_seconds, metrics_calls=metrics_calls,
                    native_fill_calls=native_fill_calls,
                    native_schedule_calls=native_schedule_calls,
                    event_ticks=event_ticks,
                    event_tick_sql_statements=event_tick_sql_statements,
                    serialize_s=serialization, pickle_bytes=len(payload),
                    digest=digest, trades=len(result.trades),
                    snapshots=len(result.portfolio_snapshots),
                    signals=dict(signal_counts), top_functions=top,
                    risk_hook_counts=dict(
                        getattr(strategy, 'risk_counts', {})),
                    order_reasons=dict(Counter(
                        str(order.to_dict().get('reason'))
                        for order in result.orders
                    )),
                    worker_peak_rss_bytes=memory.peaks,
                )
                connection.send(metadata)
                connection.send_bytes(payload)
    except BaseException:
        connection.send({'error': traceback.format_exc()})
    finally:
        connection.close()


def profile_case(case):
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(sender, case))
    with MemorySampler(enabled=(not case['profile'] and
                                case.get('sample_rss', True))) as memory, \
            tempfile.TemporaryDirectory() as directory:
        started = perf_counter()
        process.start()
        sender.close()
        try:
            memory.phase = 'worker_startup_execute_serialize'
            metadata = receiver.recv()
            if 'error' in metadata:
                raise RuntimeError(metadata['error'])
            ready = perf_counter() - started
            memory.phase = 'result_transfer'
            transfer_start = perf_counter()
            payload = receiver.recv_bytes()
            metadata['transfer_s'] = perf_counter() - transfer_start
            memory.phase = 'deserialize'
            deserialize_start = perf_counter()
            result = pickle.loads(payload)
            metadata['deserialize_s'] = perf_counter() - deserialize_start
            del payload
            process.join()
            if process.exitcode != 0:
                raise RuntimeError(f'Worker exited with {process.exitcode}')
            if result_digest(result) != metadata['digest']:
                raise AssertionError('Result changed across process boundary')
            metadata['ready_s'] = ready
            slot = 'vector_runs'
            if case['backend'] == 'event':
                slot = 'event_runs'
            backtest = Backtest(algorithm_id='profile', **{slot: [result]})
            memory.phase = 'save'
            save_start = perf_counter()
            target = save_bundle(backtest, Path(directory) / 'result.obtf')
            metadata['save_s'] = perf_counter() - save_start
            metadata['bundle_bytes'] = target.stat().st_size
            memory.phase = 'merge'
            merge_start = perf_counter()
            save_bundle(backtest, target)
            metadata['merge_s'] = perf_counter() - merge_start
            memory.phase = 'read'
            read_start = perf_counter()
            loaded = Backtest.open(str(target))
            metadata['read_s'] = perf_counter() - read_start
            restored = getattr(loaded, slot)[0]
            metadata['bundle_digest_equal'] = result_digest(
                restored) == metadata['digest']
            metadata['bundle_metric_changed_keys'] = [
                key for key, value in result.backtest_metrics.to_dict().items()
                if json.dumps(value, default=str) != json.dumps(
                    restored.backtest_metrics.to_dict().get(key), default=str
                )
            ]
            metadata['restored_signal_count'] = len(restored.signal_events)
            if (len(restored.trades), len(restored.portfolio_snapshots)) != (
                len(result.trades), len(result.portfolio_snapshots)
            ):
                raise AssertionError('Bundle record counts changed')
            metadata['end_to_end_s'] = perf_counter() - started
        finally:
            receiver.close()
            if process.is_alive():
                process.terminate()
                process.join()
        metadata['tree_peak_rss_bytes'] = memory.peaks
        metadata['rss_samples'] = memory.samples
        metadata['case'] = case
    return metadata


def writer_case(rows, batch_rows, level, asynchronous, diagnostic):
    schema = arrow.schema([
        ('timestamp_us', arrow.int64()), ('value', arrow.float64()),
        ('symbol', arrow.string()), ('payload', arrow.binary()),
    ], metadata={b'benchmark_schema_version': b'1'})
    random = np.random.default_rng(123)
    with tempfile.TemporaryDirectory() as directory, MemorySampler() as memory:
        store = LocalTieredStore(directory)
        baseline = psutil.Process().memory_info().rss
        memory.phase = 'stream'
        started = perf_counter()
        with store.begin_run(
            'writer', 'attempt', {'history': schema},
            max_batch_rows=batch_rows, compression_level=level,
            retention='full' if diagnostic else 'compact',
        ) as writer:
            executor = ThreadPoolExecutor(
                max_workers=1) if asynchronous else None
            pending = deque()
            try:
                for offset in range(0, rows, batch_rows):
                    if len(pending) == 2:
                        pending.popleft().result()
                    count = min(batch_rows, rows - offset)
                    batch = arrow.RecordBatch.from_arrays([
                        arrow.array(
                            np.arange(
                                offset,
                                offset + count,
                                dtype=np.int64)),
                        arrow.array(random.normal(size=count)),
                        arrow.array(['BTC'] * count),
                        arrow.array([random.bytes(256) if diagnostic else b''
                                     for _ in range(count)]),
                    ], schema=schema)
                    if executor:
                        pending.append(
                            executor.submit(
                                writer.append_batch,
                                'history',
                                batch))
                    else:
                        writer.append_batch('history', batch)
                for future in pending:
                    future.result()
            finally:
                if executor:
                    executor.shutdown(wait=True)
            handle = writer.commit()
        elapsed = perf_counter() - started
        total_bytes = sum(path.stat().st_size for path in store.root.rglob('*')
                          if path.is_file())
        memory.phase = 'stream_read'
        started = perf_counter()
        read_rows = sum(
            batch.num_rows for batch in store.iter_run_batches(handle))
        if read_rows != rows:
            raise AssertionError('Writer lost records')
        return dict(rows=rows, batch_rows=batch_rows, level=level,
                    asynchronous=asynchronous, diagnostic=diagnostic,
                    write_s=elapsed, read_s=perf_counter() - started,
                    file_bytes=total_bytes, chunks=writer.chunk_count,
                    peak_batch_bytes=writer.peak_batch_bytes,
                    baseline_rss_bytes=baseline, peak_rss_bytes=memory.peaks)


def copy_read_cases(repeats):
    from investing_algorithm_framework.domain import OrderSide, OrderType
    from investing_algorithm_framework.infrastructure.database import SQLBaseModel
    from investing_algorithm_framework.infrastructure.models import \
        SQLOrder, SQLTradeAllocation
    from investing_algorithm_framework.infrastructure.repositories.event_memory \
        import event_memory_scope
    from investing_algorithm_framework.infrastructure.repositories \
        .order_repository import SQLOrderRepository

    results = []
    for count in (100, 10000):
        with event_memory_scope() as state:
            order = SQLOrderRepository().create({
                'target_symbol': 'BTC', 'trading_symbol': 'EUR',
                'amount': float(count), 'price': 10.,
                'order_type': OrderType.LIMIT, 'order_side': OrderSide.BUY,
            })
            for number in range(count):
                state._adopt(SQLTradeAllocation(
                    order_id=order.id, trade_id=number + 1,
                    amount=1., amount_pending=0.,
                ))
            canonical = state.rows[SQLOrder][order.id]
            for repeat in range(repeats):
                modes = (False, True) if repeat % 2 == 0 else (True, False)
                for eager_only in modes:
                    gc.collect()
                    memo = {}
                    tracemalloc.start()
                    try:
                        started = perf_counter()
                        copied = state._clone(canonical, memo,
                                              eager_only=eager_only)
                        elapsed = perf_counter() - started
                        _, peak = tracemalloc.get_traced_memory()
                    finally:
                        tracemalloc.stop()
                    models = sum(isinstance(value, SQLBaseModel)
                                 for value in memo.values())
                    if models != (1 if eager_only else count + 1):
                        raise AssertionError('Unexpected read-copy graph')
                    results.append(dict(
                        allocations=count, eager_only=eager_only,
                        copied_models=models, copy_s=elapsed,
                        peak_traced_bytes=peak,
                    ))
                    del copied, memo
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', nargs='+', type=int, default=[30, 365, 650])
    parser.add_argument(
        '--strategies',
        nargs='+',
        choices=[
            'ema',
            'rsi'],
        default=[
            'ema',
            'rsi'])
    parser.add_argument(
        '--backends',
        nargs='+',
        choices=[
            'python',
            'rust',
            'event'],
        default=[
            'python',
            'rust'])
    parser.add_argument(
        '--symbols',
        nargs='+',
        choices=list(FILES),
        default=[
            'BTC',
            'DOT'])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--metrics-backends', nargs='+',
                        choices=['python', 'rust'], default=['python'])
    parser.add_argument('--metric-input-modes', nargs='+',
                        choices=['legacy', 'compact', 'materialized'],
                        default=['compact'])
    parser.add_argument('--event-fill-backends', nargs='+',
                        choices=['python', 'rust'], default=['python'])
    parser.add_argument('--event-schedule-backends', nargs='+',
                        choices=['python', 'rust'], default=['python'])
    parser.add_argument('--event-state-backends', nargs='+',
                        choices=['sql', 'memory', 'rust'], default=['sql'])
    parser.add_argument('--python-data-paths', nargs='+',
                        choices=['baseline', 'optimized'],
                        default=['optimized'])
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--no-rss', action='store_true')
    parser.add_argument('--real-vector-data', action='store_true')
    parser.add_argument('--archive-decoders', nargs='+',
                        choices=['baseline', 'optimized'],
                        default=['optimized'])
    parser.add_argument('--preparation-paths', nargs='+',
                        choices=['baseline', 'optimized'],
                        default=['optimized'])
    parser.add_argument('--writer', action='store_true')
    parser.add_argument('--copy-reads', action='store_true')
    parser.add_argument('--rows', type=int, default=131072)
    parser.add_argument('--writer-batch-rows', nargs='+', type=int,
                        default=[1024, 8192])
    parser.add_argument('--writer-levels', nargs='+', type=int,
                        choices=range(1, 20), default=[3, 9, 19])
    parser.add_argument('--writer-modes', nargs='+', choices=['sync', 'async'],
                        default=['sync', 'async'])
    parser.add_argument('--writer-retention', nargs='+',
                        choices=['compact', 'diagnostic'],
                        default=['compact', 'diagnostic'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--sweep', action='store_true')
    parser.add_argument('--algorithms', type=int, default=50)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--sweep-directory', type=Path)
    parser.add_argument('--hard-memory-limit-mb', type=int)
    args = parser.parse_args()
    if sum((args.sweep, args.writer, args.copy_reads)) > 1:
        parser.error('Select only one of --sweep, --writer or --copy-reads')
    if args.python_data_paths != ['optimized'] and (
            args.sweep or args.writer or args.copy_reads):
        parser.error('--python-data-paths applies only to representative runs')
    if (args.sweep or args.writer) and args.metrics_backends != ['python']:
        parser.error('--metrics-backends applies only to representative runs')
    if args.event_fill_backends != ['python'] and (
            args.sweep or args.writer or 'event' not in args.backends):
        parser.error('--event-fill-backends requires representative event runs')
    if args.event_schedule_backends != ['python'] and (
            args.sweep or args.writer or 'event' not in args.backends):
        parser.error(
            '--event-schedule-backends requires representative event runs')
    if args.repeats < 1 or args.rows < 1 or any(
            not 1 <= days <= 650 for days in args.days):
        parser.error('Require positive counts and windows of 1..650 days')
    if args.event_state_backends != ['sql'] and (
            args.writer or 'event' not in args.backends):
        parser.error(
            '--event-state-backends requires event runs')
    report = {
        'environment': {
            'python': platform.python_version(), 'platform': platform.platform(),
            'numpy': np.__version__, 'pandas': pd.__version__,
            'arrow': arrow.__version__, 'rss_interval_s': .01,
        },
        'fixture_sha256': {
            symbol: hashlib.sha256(FILES[symbol].read_bytes()).hexdigest()
            for symbol in args.symbols
        },
        'results': [],
    }
    if args.sweep:
        if args.sweep_directory is None or args.algorithms < 1:
            parser.error('--sweep requires --sweep-directory and positive count')
        vector_expected = {}
        event_expected = {}
        for days in args.days:
            for backend in args.backends:
                states = (args.event_state_backends
                          if backend == 'event' else ['sql'])
                for state_backend in states:
                    suffix = f'-{state_backend}' if backend == 'event' else ''
                    cases, digests = acceptance_sweep(
                        args.sweep_directory / f'{backend}-{days}{suffix}',
                        args.algorithms, days, backend, args.workers,
                        args.hard_memory_limit_mb, state_backend,
                    )
                    reference = (event_expected if backend == 'event'
                                 else vector_expected)
                    expected = reference.setdefault(days, digests)
                    if expected != digests:
                        raise AssertionError('Backend saved results differ')
                    report['results'].extend(cases)
                    if args.output:
                        args.output.write_text(
                            json.dumps(report, indent=2) + '\n')
    elif args.copy_reads:
        report['results'] = copy_read_cases(args.repeats)
    elif args.writer:
        for retention in args.writer_retention:
            for batch_rows in args.writer_batch_rows:
                for level in args.writer_levels:
                    for mode in args.writer_modes:
                        for _ in range(args.repeats):
                            report['results'].append(writer_case(
                                args.rows, batch_rows, level, mode == 'async',
                                retention == 'diagnostic',
                            ))
    else:
        digests = {}
        for repeat in range(args.repeats):
            for days in args.days:
                for strategy in args.strategies:
                    backends = (args.backends if repeat % 2 == 0
                                else args.backends[::-1])
                    for backend in backends:
                        if backend == 'event' and strategy != 'ema':
                            continue
                        metric_backends = (args.metrics_backends
                                           if repeat % 2 == 0
                                           else args.metrics_backends[::-1])
                        fill_backends = (args.event_fill_backends
                                         if backend == 'event' else ['python'])
                        if repeat % 2:
                            fill_backends = fill_backends[::-1]
                        schedule_backends = (
                            args.event_schedule_backends
                            if backend == 'event' else ['python'])
                        if repeat % 2:
                            schedule_backends = schedule_backends[::-1]
                        state_backends = (args.event_state_backends
                                          if backend == 'event' else ['sql'])
                        if repeat % 2:
                            state_backends = state_backends[::-1]
                        combinations = (
                            (metrics, fills, schedule, state, inputs, data_path,
                             decoder, preparation)
                            for metrics in metric_backends
                            for fills in fill_backends
                            for schedule in schedule_backends
                            for state in state_backends
                            for inputs in (args.metric_input_modes
                                           if repeat % 2 == 0 else
                                           args.metric_input_modes[::-1])
                            for data_path in (
                                args.python_data_paths if repeat % 2 == 0
                                else args.python_data_paths[::-1])
                            for decoder in (
                                args.archive_decoders if repeat % 2 == 0
                                else args.archive_decoders[::-1])
                            for preparation in (
                                args.preparation_paths if repeat % 2 == 0
                                else args.preparation_paths[::-1])
                        )
                        for (metrics_backend, fill_backend, schedule_backend,
                                state_backend, input_mode,
                                data_path, decoder, preparation) in combinations:
                            result = profile_case(dict(
                                days=days, strategy=strategy, backend=backend,
                                metrics_backend=metrics_backend,
                                event_fill_backend=fill_backend,
                                event_schedule_backend=schedule_backend,
                                event_state_backend=state_backend,
                                metric_inputs=input_mode,
                                python_data_path=data_path,
                                archive_decoder=decoder,
                                preparation_path=preparation,
                                real_vector_data=args.real_vector_data,
                                sample_rss=not args.no_rss,
                                symbols=args.symbols, profile=args.profile,
                            ))
                            engine = ('event' if backend == 'event'
                                      else 'vector')
                            key = (days, strategy, engine)
                            expected = digests.setdefault(
                                key, result['digest'])
                            if expected != result['digest']:
                                raise AssertionError(
                                    f'Non-identical execution result: {key}')
                            report['results'].append(result)
                            if args.output:
                                args.output.write_text(
                                    json.dumps(report, indent=2) + '\n')
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
