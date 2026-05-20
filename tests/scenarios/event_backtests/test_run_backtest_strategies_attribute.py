"""
Event backtest scenario: strategy registered via ``app.add_strategy``.

Verifies that strategies added on the app via ``app.add_strategy`` are
picked up automatically when ``app.run_backtest`` is called without a
``strategy`` or ``strategies`` parameter.

Uses a short (30-day) date range so this test runs well under 30s on CI,
with all data sourced from ``tests/resources/test_data/``.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import (
    create_app,
    BacktestDateRange,
    RESOURCE_DIRECTORY,
    DATA_DIRECTORY,
    SnapshotInterval,
)
from tests.resources.strategies_for_testing.strategy_v1 import (
    CrossOverStrategyV1,
)


class Test(TestCase):

    def test_run(self):
        start_time = time.time()
        resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        config = {
            RESOURCE_DIRECTORY: resource_directory,
            DATA_DIRECTORY: "test_data/ohlcv",
        }
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )
        app.add_strategy(CrossOverStrategyV1)
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        backtest = app.run_backtest(
            backtest_date_range=date_range,
            snapshot_interval=SnapshotInterval.DAILY,
        )
        elapsed_time = time.time() - start_time
        self.assertLess(
            elapsed_time, 30,
            f"Event backtest took {elapsed_time:.2f}s (expected <30s)"
        )

        metrics = backtest.get_backtest_metrics(date_range)
        run = backtest.get_backtest_run(date_range)
        self.assertEqual(run.initial_unallocated, 400)
        self.assertEqual(run.trading_symbol, "EUR")
        self.assertIsNotNone(metrics.total_growth)
        self.assertAlmostEqual(
            metrics.total_growth, metrics.total_net_gain, delta=0.01
        )
        snapshots = run.get_portfolio_snapshots()
        self.assertGreater(len(snapshots), 0)
        self.assertEqual(
            snapshots[0].created_at.replace(tzinfo=timezone.utc),
            start_date.replace(tzinfo=timezone.utc),
        )
