import os
from datetime import datetime, timedelta
from unittest import TestCase

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit, Algorithm
from investing_algorithm_framework.domain import DATETIME_FORMAT_BACKTESTING


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

    def test_run_backtests(self):
        """
        Test if all backtests are run when multiple algorithms are provided
        """
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
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
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow()
        app._initialize_app_for_backtest(
            backtest_start_date=start_date,
            backtest_end_date=end_date,
            pending_order_check_interval='2h',
            market_data_sources=[]
        )
        reports = app.run_backtests(
            algorithms=[algorithm_one, algorithm_two, algorithm_three],
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        for report in reports:
            csv_file_path = os.path.join(
                self.resource_dir,
                os.path.join(
                    "backtest_reports",
                    f"report_{report.name}_backtest_start_date_"
                    f"{report.backtest_start_date.strftime(DATETIME_FORMAT_BACKTESTING)}_backtest_end_date_"
                    f"{report.backtest_end_date.strftime(DATETIME_FORMAT_BACKTESTING)}_created_at_{report.created_at.strftime(DATETIME_FORMAT_BACKTESTING)}.csv"
                )
            )

            # Check if the backtest report exists
            self.assertTrue(os.path.isfile(csv_file_path))
