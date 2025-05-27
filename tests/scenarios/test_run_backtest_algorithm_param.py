import time
import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, BacktestDateRange, \
    Algorithm, RESOURCE_DIRECTORY
from tests.resources.strategies_for_testing.strategy_v1 import \
    CrossOverStrategyV1


class Test(TestCase):

    def test_run(self):
        """
        """
        start_time = time.time()
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
        algorithm = Algorithm()
        algorithm.add_strategy(CrossOverStrategyV1)
        backtest_report = app.run_backtest(
            backtest_date_range=date_range,
            save_strategy=True,
            algorithm=algorithm
        )
        self.assertAlmostEqual(
            backtest_report.get_growth(), 3, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.get_growth_percentage(), 0.8, delta=0.05
        )
        self.assertEqual(
            backtest_report.get_initial_unallocated(), 400
        )
        self.assertEqual(
            backtest_report.get_trading_symbol(), "EUR"
        )
        self.assertAlmostEqual(
            backtest_report.get_profit(), 3, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.get_profit_percentage(), 0.8, delta=0.05
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Test completed in {elapsed_time:.2f} seconds")
