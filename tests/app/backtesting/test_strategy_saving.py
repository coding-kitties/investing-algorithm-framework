import os
from datetime import datetime, timedelta
from unittest import TestCase

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit, Algorithm, \
    BacktestDateRange
from investing_algorithm_framework.services import BacktestService


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
        Test if the backtest report contains the in-memory strategy.
        The strategy should be saved as a python file called
        <strategy_id>.py.
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
        backtest_date_range = BacktestDateRange(
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow()
        )
        report = app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            save_strategy=True,
            save_in_memory_strategies=True
        )
        report_directory = BacktestService.create_report_directory_name(report)
        report_name = "report.json"
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
        strategy_file_path = os.path.join(
            backtest_report_dir, "TestStrategy.py"
        )
        self.assertTrue(os.path.isfile(strategy_file_path))

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
        algorithm.add_strategy(TestStrategy())
        app.add_algorithm(algorithm)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow()
        )
        strategy_directory = os.path.join(
            self.resource_dir, "strategies_for_testing"
        )
        report = app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            save_strategy=True,
            strategy_directory=strategy_directory,
        )
        report_directory = BacktestService.create_report_directory_name(report)
        report_name = "report.json"
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
        strategy_one_file_path = os.path.join(
            backtest_report_dir, "strategies_for_testing", "strategy_one.py"
        )
        self.assertTrue(os.path.isfile(strategy_one_file_path))

        strategy_two_file_path = os.path.join(
            backtest_report_dir, "strategies_for_testing", "strategy_two.py"
        )
        self.assertTrue(os.path.isfile(strategy_two_file_path))

    def test_save_strategy_with_run_backtests(self):
        """
        Test if the in-memory strategy is saved when the run_backtests method is called with save_strategy=True.
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        algorithm_one = Algorithm()
        algorithm_one.add_strategy(TestStrategy())

        algorithm_two = Algorithm()
        algorithm_two.add_strategy(TestStrategy())

        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        backtest_date_range = BacktestDateRange(
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow()
        )
        strategy_directory = os.path.join(
            self.resource_dir, "strategies_for_testing"
        )
        reports = app.run_backtests(
            algorithms=[algorithm_one, algorithm_two],
            backtest_date_ranges=[backtest_date_range],
            save_strategy=True,
        )

        backtest_report_root_dir = os.path.join(
            self.resource_dir, "backtest_reports"
        )

        # Check if the backtest report root directory exists
        self.assertTrue(os.path.isdir(backtest_report_root_dir))

        for report in reports:
            report_directory = BacktestService\
                .create_report_directory_name(report)
            report_name = "report.json"

            report_directory = os.path.join(
                backtest_report_root_dir, report_directory
            )

            # Check if the backtest report directory exists
            self.assertTrue(os.path.isdir(report_directory))

            # Check if the strategy file exists
            strategy_file_path = os.path.join(
                report_directory, "TestStrategy.py"
            )
            self.assertTrue(os.path.isfile(strategy_file_path))

            report_file_path = os.path.join(
                report_directory, report_name
            )
            # check if the report json file exists
            self.assertTrue(os.path.isfile(report_file_path))
