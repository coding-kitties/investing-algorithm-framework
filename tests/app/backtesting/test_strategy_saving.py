import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit, Algorithm, \
    BacktestDateRange
from investing_algorithm_framework.services import BacktestService
from tests.resources.strategies_for_testing.strategy_v1 import \
    CrossOverStrategyV1


class TestStrategy(TradingStrategy):
    strategy_id = "test_strategy"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def run_strategy(self, context, market_data):
        pass


class Test(TestCase):
    """
    Collection of tests for backtest report operations where
    the tests resolve around the saving of strategies.
    """
    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def tearDown(self) -> None:
        database_dir = os.path.join(
            self.resource_dir, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    def test_in_memory(self):
        """
        Test if the report is generated without saving the strategy to a file.
        when the strategy is specified in memory.
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        algorithm = Algorithm()
        algorithm.add_strategy(TestStrategy())
        app.add_algorithm(algorithm)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        start_date = datetime(2025, 5, 24, 11, 22, 44)
        end_date = datetime(2025, 5, 25, 11, 22, 44)
        backtest_date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date
        )
        report = app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
        )
        report_directory = BacktestService.create_report_directory_name(report)
        report_name = "results.json"
        backtest_report_root_dir = os.path.join(
            self.resource_dir, "backtest_reports"
        )
        backtest_report_dir = os.path.join(
            backtest_report_root_dir, report_directory
        )

        # Check if the backtest report root directory exists
        self.assertTrue(os.path.isdir(backtest_report_root_dir))

        # Check if the backtest report directory exists
        self.assertTrue(os.path.isdir(backtest_report_dir))

        report_file_path = os.path.join(
            backtest_report_dir, report_name
        )

        # check if the report json file exists
        self.assertTrue(os.path.isfile(report_file_path))


    def test_with_directory(self):
        """
        Test if the strategy is saved when the strategy is specified through
        a directory attribute.
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        algorithm = Algorithm()
        algorithm.add_strategy(CrossOverStrategyV1())
        app.add_algorithm(algorithm)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        start_date = datetime(2025, 5, 24, 11, 22, 44)
        end_date = datetime(2025, 5, 25, 11, 22, 44)
        backtest_date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date
        )
        report = app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            risk_free_rate=2.4
        )
        report_directory = BacktestService.create_report_directory_name(report)
        backtest_report_root_dir = os.path.join(
            self.resource_dir, "backtest_reports"
        )
        backtest_report_dir = os.path.join(
            backtest_report_root_dir, report_directory
        )

        # Check if the backtest report root directory exists
        self.assertTrue(os.path.isdir(backtest_report_root_dir))

        # Check if the backtest report directory exists
        self.assertTrue(os.path.isdir(backtest_report_dir))
        # Check if the strategy file exists
        strategy_one_directory = os.path.join(
            backtest_report_dir, "strategies"
        )
        strategy_one_file_path = os.path.join(
            strategy_one_directory, "strategy_v1.py"
        )
        data_sources_path = os.path.join(
            strategy_one_directory, "data_sources.py"
        )
        self.assertTrue(os.path.isdir(strategy_one_directory))
        self.assertTrue(os.path.isfile(strategy_one_file_path))
        self.assertTrue(os.path.isfile(data_sources_path))
