import os
from unittest import TestCase
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit, Algorithm
from investing_algorithm_framework.domain import DATETIME_FORMAT
from tests.resources import TestBase


class TestStrategy(TradingStrategy):
    strategy_id = "test_strategy"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def run_strategy(self, algorithm, market_data):
        pass


class Test(TestCase):
    """
    Collection of tests for backtest report operations
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

    def test_report_csv_creation(self):
        """
        Test if the backtest report is created as a CSV file
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
        report = app.run_backtest(
            algorithm,
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        # Check if the backtest report exists
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.resource_dir,
                    "backtest_reports",
                    f"report_{report.name}"
                    f"_{report.created_at.strftime(DATETIME_FORMAT)}.csv"
                )
            )
        )

    def test_report_csv_creation_without_strategy_identifier(self):
        """
        Test if the backtest report is created as a CSV file
        when the strategy does not have an identifier
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        strategy = TestStrategy()
        strategy.strategy_id = None
        algorithm = Algorithm()
        algorithm.add_strategy(strategy)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        report = app.run_backtest(
            algorithm=algorithm,
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        # Check if the backtest report exists
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.resource_dir,
                    "backtest_reports",
                    f"report_{report.name}"
                    f"_{report.created_at.strftime(DATETIME_FORMAT)}.csv"
                )
            )
        )

    def test_report_csv_creation_with_multiple_strategies(self):
        """
        Test if the backtest report is created as a CSV file
        when there are multiple strategies
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        strategy = TestStrategy()
        strategy.strategy_id = None
        algorithm = Algorithm()
        algorithm.add_strategy(strategy)

        @algorithm.strategy()
        def run_strategy(algorithm, market_data):
            pass

        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )

        self.assertEqual(2, len(algorithm.strategies))
        report = app.run_backtest(
            algorithm=algorithm,
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        # Check if the backtest report exists
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.resource_dir,
                    "backtest_reports",
                    f"report_{report.name}"
                    f"_{report.created_at.strftime(DATETIME_FORMAT)}.csv"
                )
            )
        )

    def test_report_csv_creation_with_multiple_strategies_with_id(self):
        """
        Test if the backtest report is created as a CSV file
        when there are multiple strategies with identifiers
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        algorithm = Algorithm()

        @algorithm.strategy()
        def run_strategy(algorithm, market_data):
            pass

        algorithm.add_strategy(TestStrategy)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )

        self.assertEqual(2, len(algorithm.strategies))
        report = app.run_backtest(
            algorithm=algorithm,
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        # Check if the backtest report exists
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.resource_dir,
                    "backtest_reports",
                    f"report_{report.name}"
                    f"_{report.created_at.strftime(DATETIME_FORMAT)}.csv"
                )
            )
        )
