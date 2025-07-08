import time
import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, BacktestDateRange, \
    Algorithm, RESOURCE_DIRECTORY, SnapshotInterval
from tests.resources.strategies_for_testing.strategy_v1 import \
    CrossOverStrategyV1


class Test(TestCase):

    def test_run(self):
        """
        """
        start_time = time.time()
        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        resource_directory = os.path.join(os.path.dirname(__file__), 'resources')
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(market="BINANCE", trading_symbol="EUR", initial_balance=400)
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=100)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        algorithm = Algorithm()
        algorithm.add_strategy(CrossOverStrategyV1)
        backtest_report = app.run_backtest(
            backtest_date_range=date_range,
            algorithm=algorithm,
            snapshot_interval=SnapshotInterval.STRATEGY_ITERATION
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Test completed in {elapsed_time:.2f} seconds")

        self.assertAlmostEqual(
            backtest_report.backtest_results.growth, 3, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.backtest_results.growth_percentage, 0.8, delta=0.1
        )
        self.assertEqual(
            backtest_report.backtest_results.initial_unallocated, 400
        )
        self.assertEqual(
            backtest_report.backtest_results.trading_symbol, "EUR"
        )
        self.assertAlmostEqual(
            backtest_report.backtest_results.total_net_gain, 3, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.backtest_results.total_net_gain_percentage, 0.8, delta=0.1
        )
        snapshots = backtest_report.backtest_results.get_portfolio_snapshots()
        # Check that the first two snapshots created at are the same
        # as the start date of the backtest
        self.assertEqual(
            snapshots[0].created_at.replace(tzinfo=timezone.utc),
            start_date.replace(tzinfo=timezone.utc)
        )

        for snapshot in snapshots:
            self.assertTrue(
                end_date >= snapshot.created_at >= start_date
            )
