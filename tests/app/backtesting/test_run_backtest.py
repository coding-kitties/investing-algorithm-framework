import os
import shutil
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from typing import Dict, Any
import pandas as pd

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit, Algorithm, \
    BacktestDateRange


class TestStrategy(TradingStrategy):
    strategy_id = "test_strategy"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[
        str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[
        str, pd.Series]:
        pass


class Test(TestCase):
    """
    Collection of tests for backtest report operations
    """
    def setUp(self) -> None:
        self.resource_directory = os.path.abspath(
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
        super().tearDown()
        databases_directory = os.path.join(self.resource_directory,
                                           "databases")
        backtest_databases_directory = os.path.join(
            self.resource_directory, "backtest_databases")

        if os.path.exists(databases_directory):
            shutil.rmtree(databases_directory)

        if os.path.exists(backtest_databases_directory):
            shutil.rmtree(backtest_databases_directory)

    def test_report_creation(self):
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_directory}
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
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1)
        backtest_date_range = BacktestDateRange(
            start_date=start_date,
            end_date=end_date
        )
        backtest = app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            risk_free_rate=0.027
        )
        path = os.path.join(self.resource_directory, "backtest_reports/test_backtest")
        backtest.save(path)
        # Check if the backtest report exists
        self.assertTrue(os.path.isdir(path))

    def test_report_creation_without_strategy_identifier(self):
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_directory}
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
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=1)
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
            self.resource_directory, "backtest_reports/test_backtest"
        )
        backtest.save(path)
        # Check if the backtest report exists
        self.assertTrue(os.path.isdir(path))
