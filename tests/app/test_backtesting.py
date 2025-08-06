import os
from unittest import TestCase

from investing_algorithm_framework import TradingStrategy, Algorithm, \
    create_app, RESOURCE_DIRECTORY, PortfolioConfiguration, \
    BacktestDateRange, Context
from investing_algorithm_framework.domain import SQLALCHEMY_DATABASE_URI


class SimpleTradingStrategy(TradingStrategy):
    interval = 2
    time_unit = "hour"

    def apply_strategy(self, context: Context, data):
        pass

class Test(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def test_backtest_with_initial_amount(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="USDT"
            )
        )
        date_range = BacktestDateRange(
            start_date="2021-01-01",
            end_date="2021-02-01"
        )
        algorithm = Algorithm()
        algorithm.add_strategy(SimpleTradingStrategy)
        app.add_algorithm(algorithm)
        report = app.run_backtest(
            backtest_date_range=date_range,
            initial_amount=1000
        )
        self.assertEqual(report.backtest_results.initial_unallocated, 1000)
        self.assertEqual(report.backtest_results.growth, 0)
        self.assertEqual(report.backtest_results.growth_percentage, 0)
        self.assertEqual(report.backtest_metrics.total_return, 0)
        self.assertEqual(report.backtest_metrics.total_return_percentage, 0)
        self.assertAlmostEqual(report.backtest_results.number_of_runs, 373, places=1)
        self.assertEqual(report.backtest_results.trading_symbol, "USDT")
        database_uri = app.config[SQLALCHEMY_DATABASE_URI]
        self.assertIsNotNone(database_uri)
        self.assertTrue(database_uri.endswith("backtest-database.sqlite3"))

    def test_backtest_with_initial_balance(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="USDT",
                initial_balance=500
            )
        )
        date_range = BacktestDateRange(
            start_date="2021-01-01",
            end_date="2021-02-01"
        )
        algorithm = Algorithm()
        algorithm.add_strategy(SimpleTradingStrategy)
        app.add_algorithm(algorithm)
        report = app.run_backtest(
            backtest_date_range=date_range,
        )
        self.assertEqual(report.backtest_results.initial_unallocated, 500)
        self.assertEqual(report.backtest_results.growth, 0)
        self.assertEqual(report.backtest_results.growth_percentage, 0)
        self.assertEqual(report.backtest_metrics.total_return, 0)
        self.assertEqual(report.backtest_metrics.total_return_percentage, 0)
        self.assertAlmostEqual(report.backtest_results.number_of_runs, 373, places=1)
        self.assertEqual(report.backtest_results.trading_symbol, "USDT")
        database_uri = app.config[SQLALCHEMY_DATABASE_URI]
        self.assertIsNotNone(database_uri)
        self.assertTrue(database_uri.endswith("backtest-database.sqlite3"))
