import os
from datetime import datetime, timedelta, timezone
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
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def tearDown(self) -> None:
        database_dir = os.path.join(self.resource_dir, "databases")

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

        if os.path.exists(database_dir):
            os.rmdir(database_dir)

    def test_run_backtests(self):
        """
        Test if all backtests are run when multiple algorithms are provided
        """
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir}
        )

        # Add all algorithms
        algorithm_one = Algorithm()
        algorithm_one.add_strategy(TestStrategy())
        algorithm_two = Algorithm()
        algorithm_two.add_strategy(TestStrategy())
        algorithm_three = Algorithm()
        algorithm_three.add_strategy(TestStrategy())

        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1)
        backtest_date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date
        )
        reports = app.run_backtests(
            algorithms=[algorithm_one, algorithm_two, algorithm_three],
            backtest_date_ranges=[backtest_date_range],
            risk_free_rate=0.027
        )
        self.assertEqual(3, len(reports))
