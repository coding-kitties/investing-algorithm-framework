"""
Event backtest scenario: algorithm parameter.

Verifies that ``app.run_backtest(algorithm=...)`` produces a valid
``Backtest`` result using offline test data from
``tests/resources/test_data/``.

Uses a short (30-day) date range so this test runs well under 30s on CI.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import (
    create_app,
    BacktestDateRange,
    Algorithm,
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
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        algorithm = Algorithm()
        algorithm.add_strategy(CrossOverStrategyV1)
        backtest = app.run_backtest(
            backtest_date_range=date_range,
            algorithm=algorithm,
            snapshot_interval=SnapshotInterval.DAILY,
        )
        elapsed_time = time.time() - start_time
        # Guard against regressions that would blow up CI runtime.
        self.assertLess(
            elapsed_time, 30,
            f"Event backtest took {elapsed_time:.2f}s (expected <30s)"
        )

        backtest_metrics = backtest.get_backtest_metrics(date_range)
        backtest_run = backtest.get_backtest_run(date_range)
        self.assertEqual(backtest_run.initial_unallocated, 400)
        self.assertEqual(backtest_run.trading_symbol, "EUR")
        self.assertIsNotNone(backtest_metrics.total_growth)
        self.assertIsNotNone(backtest_metrics.total_net_gain)
        self.assertAlmostEqual(
            backtest_metrics.total_growth,
            backtest_metrics.total_net_gain,
            delta=0.01,
        )
        self.assertAlmostEqual(
            backtest_metrics.total_growth_percentage,
            backtest_metrics.total_growth / 400.0,
            delta=1e-6,
        )

        snapshots = backtest_run.get_portfolio_snapshots()
        self.assertGreater(len(snapshots), 0)
        # First snapshot timestamp should match the start of the backtest.
        self.assertEqual(
            snapshots[0].created_at.replace(tzinfo=timezone.utc),
            start_date.replace(tzinfo=timezone.utc),
        )
        for snapshot in snapshots:
            self.assertTrue(end_date >= snapshot.created_at >= start_date)
