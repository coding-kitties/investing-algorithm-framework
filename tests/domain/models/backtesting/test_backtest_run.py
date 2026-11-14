from unittest import TestCase
from datetime import datetime, date, timezone
import tempfile
from pathlib import Path

from investing_algorithm_framework.domain import BacktestMetrics, Trade, \
    BacktestRun, BacktestWindow, BacktestDateRange, PortfolioSnapshot, Order, \
    Position


def _backtest_window(start_date, end_date):
    return BacktestWindow(train_range=BacktestDateRange(
        start_date=start_date,
        end_date=end_date,
    ))


class TestBacktestRunRejectionSummary(TestCase):

    def test_history_shutdown_closes_live_and_cyclic_storage(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, '-W', 'always::ResourceWarning', '-c',
             'import pickle\n'
             'from investing_algorithm_framework import BacktestHistory\n'
             'history = BacktestHistory(range(10))\n'
             'view = history[1:]\n'
             'restored = pickle.loads(pickle.dumps(history))\n'
             'history.cycle = history\n'
             'del history\n'
             'assert list(view) == list(range(1, 10))\n'],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn('ResourceWarning', result.stderr)

    def test_history_closes_files_when_construction_fails(self):
        from unittest.mock import patch
        from investing_algorithm_framework import BacktestHistory

        data = tempfile.TemporaryFile()
        with patch('investing_algorithm_framework.domain.backtesting.'
                   'history.TemporaryFile',
                   side_effect=[data, OSError('Cannot create index')]):
            with self.assertRaisesRegex(OSError, 'Cannot create index'):
                BacktestHistory([1])
        self.assertTrue(data.closed)

        data, index = tempfile.TemporaryFile(), tempfile.TemporaryFile()

        def broken_records():
            yield 1
            raise ValueError('Cannot read next record')

        with patch('investing_algorithm_framework.domain.backtesting.'
                   'history.TemporaryFile', side_effect=[data, index]):
            with self.assertRaisesRegex(ValueError, 'Cannot read next record'):
                BacktestHistory(broken_records())
        self.assertTrue(data.closed)
        self.assertTrue(index.closed)

    def test_history_closes_files_after_last_shared_view(self):
        from copy import deepcopy
        import gc
        import pickle
        from investing_algorithm_framework import BacktestHistory

        for restored in (False, True):
            with self.subTest(restored=restored):
                history = BacktestHistory(range(10))
                if restored:
                    history = pickle.loads(pickle.dumps(history))
                data, index = history._data, history._index
                view = deepcopy(history)[2:5]
                del history
                gc.collect()
                self.assertFalse(data.closed)
                self.assertFalse(index.closed)
                self.assertEqual([2, 3, 4], list(view))
                del view
                gc.collect()
                self.assertTrue(data.closed)
                self.assertTrue(index.closed)

    def test_history_retained_allocation_does_not_scale_with_row_count(self):
        import tracemalloc
        from investing_algorithm_framework import BacktestHistory

        tracemalloc.start()
        try:
            history = BacktestHistory((PortfolioSnapshot(
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                total_value=float(index),
            ) for index in range(100000)), model=PortfolioSnapshot)
            self.assertEqual(len(history), 100000)
            self.assertEqual(sum(snapshot.total_value for snapshot in history),
                             4999950000.0)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 1024 * 1024)

    def test_history_storage_lifetime_and_portable_reads(self):
        import gc
        import weakref
        from unittest.mock import patch
        from investing_algorithm_framework import BacktestHistory

        history = BacktestHistory(range(100))
        data = weakref.ref(history._data)
        index = weakref.ref(history._index)
        view = history[10:20]
        del history
        gc.collect()
        self.assertIsNotNone(data())
        with patch('investing_algorithm_framework.domain.backtesting.'
                   'history.os', spec=[]):
            self.assertEqual(list(view), list(range(10, 20)))
            self.assertEqual(view[-1], 19)
        del view
        gc.collect()
        self.assertIsNone(data())
        self.assertIsNone(index())
        self.assertIsNone(BacktestHistory()._data)

    def test_assigning_raw_history_normalizes_domain_records(self):
        from investing_algorithm_framework import BacktestHistory

        snapshot = PortfolioSnapshot(
            created_at=datetime(2024, 1, 1), total_value=100,
        )
        run = BacktestRun(
            backtest_window=_backtest_window(
                datetime(2024, 1, 1), datetime(2024, 1, 31)),
            portfolio_snapshots=BacktestHistory([snapshot]),
        )
        self.assertEqual(run.to_dict()['portfolio_snapshots'],
                         [snapshot.to_dict()])
        self.assertIs(run.portfolio_snapshots._model, PortfolioSnapshot)

    def test_histories_are_detached_read_only_and_slice_without_copying(self):
        from copy import deepcopy
        import gc
        import pickle
        import weakref
        from investing_algorithm_framework.domain.backtesting.history import \
            BacktestHistory

        snapshots = [PortfolioSnapshot(
            portfolio_id='test', trading_symbol='EUR', total_value=number,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ) for number in range(100)]
        references = [weakref.ref(snapshot) for snapshot in snapshots]
        run = BacktestRun(
            backtest_window=_backtest_window(
                datetime(2024, 1, 1), datetime(2024, 1, 31)),
            portfolio_snapshots=iter(snapshots),
        )
        del snapshots
        gc.collect()
        self.assertTrue(all(reference() is None for reference in references))
        history = run.portfolio_snapshots
        self.assertIsInstance(history, BacktestHistory)
        self.assertEqual(len(history), 100)
        history[0].total_value = 500
        self.assertEqual(history[0].total_value, 0)
        self.assertEqual(history[-1].total_value, 99)
        with self.assertRaises(IndexError):
            history[100]
        with self.assertRaises(TypeError):
            history.append(history[0])
        with self.assertRaises(TypeError):
            history[0] = history[1]
        view = history[1::2]
        self.assertIs(view._data, history._data)
        self.assertEqual([item.total_value for item in view],
                         list(range(1, 100, 2)))
        readers = [iter(history), iter(history)]
        for number in range(100):
            for reader in readers:
                self.assertEqual(next(reader).total_value, number)
        copied = deepcopy(run)
        self.assertIs(copied.portfolio_snapshots._data, history._data)
        restored = pickle.loads(pickle.dumps(run))
        self.assertEqual(restored.to_dict(), run.to_dict())
        with self.assertRaises(TypeError):
            restored.portfolio_snapshots.append(history[0])
        materialized = history.materialize()
        materialized[0].total_value = 500
        run.portfolio_snapshots = materialized
        self.assertEqual(run.portfolio_snapshots[0].total_value, 500)
        self.assertEqual(history[0].total_value, 0)

    def test_history_stream_does_not_retain_decoded_records(self):
        import weakref
        from investing_algorithm_framework.domain.backtesting.history import \
            BacktestHistory

        history = BacktestHistory((PortfolioSnapshot(
            portfolio_id='test', trading_symbol='EUR', total_value=number,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ) for number in range(10000)), model=PortfolioSnapshot)
        references = []
        for snapshot in history:
            if references:
                self.assertIsNone(references[-1]())
            references.append(weakref.ref(snapshot))
        del snapshot
        self.assertTrue(all(reference() is None for reference in references))

    def test_empty(self):
        run = BacktestRun(
            backtest_window=_backtest_window(
                datetime(2024, 1, 1), datetime(2024, 1, 31)
            ),
            signal_events=[],
        )

        self.assertEqual(run.get_rejection_summary(), {})

    def test_single_reason(self):
        run = BacktestRun(
            backtest_window=_backtest_window(
                datetime(2024, 1, 1), datetime(2024, 1, 31)
            ),
            signal_events=[
            {
                "date": datetime(2024, 1, 1),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "insufficient_capital",
            },
            {
                "date": datetime(2024, 1, 2),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "insufficient_capital",
            },
            ],
        )

        self.assertEqual(
            run.get_rejection_summary(),
            {"insufficient_capital": 2},
        )

    def test_multiple_reasons_excludes_executed_events(self):
        run = BacktestRun(
            backtest_window=_backtest_window(
                datetime(2024, 1, 1), datetime(2024, 1, 31)
            ),
            signal_events=[
            {
                "date": datetime(2024, 1, 1),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "cooldown",
            },
            {
                "date": datetime(2024, 1, 2),
                "symbol": "ETH",
                "signal": "sell",
                "executed": False,
                "reason": "already_in_position",
            },
            {
                "date": datetime(2024, 1, 3),
                "symbol": "BTC",
                "signal": "buy",
                "executed": False,
                "reason": "cooldown",
            },
            {
                "date": datetime(2024, 1, 4),
                "symbol": "BTC",
                "signal": "buy",
                "executed": True,
                "reason": "executed",
            },
            ],
        )

        self.assertEqual(
            run.get_rejection_summary(),
            {"cooldown": 2, "already_in_position": 1},
        )


class TestBacktestMetrics(TestCase):

    def test_metric_histories_are_read_only_and_serialize_lazily(self):
        from investing_algorithm_framework import BacktestHistory
        from investing_algorithm_framework.domain.backtesting.history import (
            SerializedHistory,
        )

        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        metrics = BacktestMetrics(
            backtest_window=_backtest_window(timestamp, datetime(2024, 2, 1)),
            equity_curve=((float(index), timestamp) for index in range(10)),
        )
        self.assertIsInstance(metrics.equity_curve, BacktestHistory)
        with self.assertRaises(TypeError):
            metrics.equity_curve.append((100.0, timestamp))
        eager = metrics.to_dict()['equity_curve']
        lazy = metrics.to_dict(materialize_history=False)['equity_curve']
        self.assertIsInstance(eager, list)
        self.assertIsInstance(lazy, SerializedHistory)
        self.assertEqual(list(lazy), eager)
        self.assertEqual(list(lazy[2:5]), eager[2:5])
        metrics.equity_curve = [(99.0, timestamp)]
        self.assertEqual(metrics.equity_curve[0], (99.0, timestamp))
        self.assertEqual(len(lazy), 10)

    def setUp(self):
        # Create a temporary directory for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save(self):
        backtest_metrics = BacktestMetrics(
            backtest_window=_backtest_window(datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2020, 12, 31, tzinfo=timezone.utc)),
            equity_curve = [
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth = 0.0,
            total_growth_percentage = 0.0,
            total_net_gain = 0.0,
            total_net_gain_percentage = 0.0,
            final_value = 0.0,
            cagr = 0.0,
            sharpe_ratio = 0.0,
            rolling_sharpe_ratio = [
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio = 0.0,
            calmar_ratio = 0.0,
            profit_factor = 0.0,
            gross_profit = 0.0,
            gross_loss = 0.0,
            annual_volatility = 0.0,
            monthly_returns = [
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)), (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)), (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)), (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)), (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns = [
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series = [
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)), (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)), (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)), (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)), (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown = 0.0,
            max_drawdown_absolute = 0.0,
            max_daily_drawdown = 0.0,
            max_drawdown_duration = 0,
            trades_per_year = 0.0,
            trade_per_day = 0.0,
            exposure_ratio = 0.0,
            average_trade_gain = 0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss = 0.0,
            average_trade_loss_percentage=0.0,
            best_trade = Trade(
                id=10,
                open_price=0.0,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 12, 31),
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=10.0,
                cost=1.0,
                available_amount=1.0,
                remaining=9.0,
                filled_amount=1,
                status="closed"
            ),
            worst_trade = Trade(
                id=10,
                open_price=0.0,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 12, 31),
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=10.0,
                cost=1.0,
                available_amount=1.0,
                remaining=9.0,
                filled_amount=1,
                status="closed"
            ),
            average_trade_duration = 0.0,
            number_of_trades = 0,
            win_rate = 0.0,
            win_loss_ratio = 0.0,
            percentage_winning_months = 0.0,
            percentage_winning_years = 0.0,
            average_monthly_return = 0.0,
            average_monthly_return_losing_months = 0.0,
            average_monthly_return_winning_months = 0.0,
            best_month = (0.0, datetime(2020, 1, 1)),
            best_year = (0.0, date(2020, 1, 1)),
            worst_month = (0.0, datetime(2020, 1, 1)),
            worst_year = (0.0, date(2020, 1, 1))
        )

        backtest_run = BacktestRun(
            backtest_window=BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                    end_date=datetime(2020, 12, 31, tzinfo=timezone.utc),
                )
            ),
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
                    id=10,
                    open_price=0.0,
                    opened_at=datetime(2020, 1, 1),
                    closed_at=datetime(2020, 12, 31),
                    orders=[],
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    amount=10.0,
                    cost=1.0,
                    available_amount=1.0,
                    remaining=9.0,
                    filled_amount=1,
                    status="closed"
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics
        )
        file_path = self.dir_path
        backtest_run.save(file_path)

    def test_open(self):
        backtest_metrics = BacktestMetrics(
            backtest_window=_backtest_window(datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2020, 12, 31, tzinfo=timezone.utc)),
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=0.0,
            total_growth_percentage=0.0,
            total_net_gain=0.0,
            total_net_gain_percentage=0.0,
            final_value=0.0,
            cagr=0.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
                id=10,
                open_price=0.0,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 12, 31),
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=10.0,
                cost=1.0,
                available_amount=1.0,
                remaining=9.0,
                filled_amount=1,
                status="closed"
            ),
            worst_trade=Trade(
                id=10,
                open_price=0.0,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 12, 31),
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=10.0,
                cost=1.0,
                available_amount=1.0,
                remaining=9.0,
                filled_amount=1,
                status="closed"
            ),
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        backtest_run = BacktestRun(
            backtest_window=BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                    end_date=datetime(2020, 12, 31, tzinfo=timezone.utc),
                )
            ),
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
                    id=10,
                    open_price=0.0,
                    opened_at=datetime(2020, 1, 1),
                    closed_at=datetime(2020, 12, 31),
                    orders=[],
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    amount=10.0,
                    cost=1.0,
                    available_amount=1.0,
                    remaining=9.0,
                    filled_amount=1,
                    status="closed"
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics
        )
        file_path = self.dir_path
        backtest_run.save(file_path)
        opened_backtest_run = BacktestRun.open(file_path)
        self.assertEqual(backtest_run.to_dict(), opened_backtest_run.to_dict())
