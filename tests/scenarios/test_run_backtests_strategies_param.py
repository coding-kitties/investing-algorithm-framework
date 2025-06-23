import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, BacktestDateRange, \
    RESOURCE_DIRECTORY, pretty_print_backtest
from tests.resources.strategies_for_testing.strategy_v1 import \
    CrossOverStrategyV1
from tests.resources.strategies_for_testing.strategy_v3 import \
    CrossOverStrategyV3


class Test(TestCase):

    def test_run(self):
        """
        """
        resource_directory = os.path.join(os.path.dirname(__file__), '..', 'resources')
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="GoldenCrossStrategy", config=config)
        app.add_market(market="BINANCE", trading_symbol="EUR", initial_balance=400)
        end_date = datetime(2023, 12, 2)
        start_date = end_date - timedelta(days=100)
        date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        backtest_reports = app.run_backtests(
            backtest_date_ranges=[date_range],
            strategies=[
                CrossOverStrategyV1,
                CrossOverStrategyV3,
            ],
            save_strategy=True,
        )
        backtest_report = backtest_reports[0]
        self.assertAlmostEqual(
            backtest_report.results.growth, 3, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.results.growth_percentage, 0.8, delta=0.1
        )
        self.assertEqual(
            backtest_report.results.initial_unallocated, 400
        )
        self.assertEqual(
            backtest_report.results.trading_symbol, "EUR"
        )
        self.assertAlmostEqual(
            backtest_report.results.total_net_gain, 3, delta=0.5
        )
        self.assertAlmostEqual(
            backtest_report.results.total_net_gain_percentage, 0.8, delta=0.1
        )
        backtest_report_two = backtest_reports[1]
        self.assertAlmostEqual(
            backtest_report_two.results.growth, 18.16, delta=0.6
        )
        self.assertAlmostEqual(
            backtest_report_two.results.growth_percentage, 4.5, delta=0.2
        )
        self.assertEqual(
            backtest_report_two.results.initial_unallocated, 400
        )
        self.assertEqual(
            backtest_report_two.results.trading_symbol, "EUR"
        )
        self.assertAlmostEqual(
            backtest_report_two.results.total_net_gain, 18.16, delta=0.6
        )
        self.assertAlmostEqual(
            backtest_report_two.results.total_net_gain_percentage, 4.5, delta=0.2
        )
