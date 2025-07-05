import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, BacktestDateRange, \
    RESOURCE_DIRECTORY
from tests.resources.strategies_for_testing.strategy_v1 import \
    CrossOverStrategyV1
from tests.resources.strategies_for_testing.strategy_v2 import \
    CrossOverStrategyV2


class Test(TestCase):

    def test_run(self):
        """
        """
        # RESOURCE_DIRECTORY should always point to the parent directory/resources
        resource_directory = os.path.join(os.path.dirname(__file__), '..', 'resources')
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(market="BINANCE", trading_symbol="EUR", initial_balance=400)
        end_date = datetime(2023, 12, 2)
        start_date = end_date - timedelta(days=100)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        backtest_report = app.run_backtest(
            backtest_date_range=date_range,
            strategies=[CrossOverStrategyV1, CrossOverStrategyV2]
        )
        self.assertAlmostEqual(
            backtest_report.results.growth, 18.1, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.results.growth_percentage, 4.5, delta=0.5
        )
        self.assertEqual(
            backtest_report.results.initial_unallocated, 400
        )
        self.assertEqual(
            backtest_report.results.trading_symbol, "EUR"
        )
        self.assertAlmostEqual(
            backtest_report.results.total_net_gain, 18.1, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.results.total_net_gain_percentage, 4.5, delta=0.5
        )
        snapshots = backtest_report.results.get_portfolio_snapshots()
        # Check that the first two snapshots created at are the same
        # as the start date of the backtest
        self.assertEqual(
            snapshots[0].created_at.replace(tzinfo=timezone.utc),
            start_date.replace(tzinfo=timezone.utc)
        )
