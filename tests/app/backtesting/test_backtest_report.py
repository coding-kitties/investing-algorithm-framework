import os
from datetime import datetime, timedelta
from unittest import TestCase

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit, Algorithm, \
    BacktestDateRange


class TestStrategy(TradingStrategy):
    strategy_id = "test_strategy"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def run_strategy(self, context, data):
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

    def test_report_json_creation(self):
        """
        Test if the backtest report is created as a CSV file
        """
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
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
        start_date = datetime(2023, 12, 2, tzinfo=None)
        end_date = start_date + timedelta(days=1)
        backtest_date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date
        )
        backtest = app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            risk_free_rate=0.027
        )
        path = os.path.join(
            self.resource_dir, "backtest_reports_for_testing/test_algorithm_backtest"
        )
        backtest.save(directory_path=path)

        # Check if the backtest report exists
        self.assertTrue(os.path.isdir(path))
