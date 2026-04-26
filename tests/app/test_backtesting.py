"""
Consolidated tests for backtesting operations via the app.

Merged from:
- test_backtesting.py
- backtesting/test_backtest_report.py
- backtesting/test_run_backtest.py
- backtesting/test_run_backtests.py
"""
import os
import shutil
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import TradingStrategy, Algorithm, \
    create_app, RESOURCE_DIRECTORY, PortfolioConfiguration, \
    BacktestDateRange, TimeUnit
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from investing_algorithm_framework.domain import SQLALCHEMY_DATABASE_URI


# ---------------------------------------------------------------------------
# Shared test strategy (previously duplicated across 4 files)
# ---------------------------------------------------------------------------

class BacktestTestStrategy(TradingStrategy):
    strategy_id = "test_strategy"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


class HourlyTestStrategy(TradingStrategy):
    """Strategy with hourly interval (used for initial_amount/balance tests)."""
    interval = 2
    time_unit = "hour"

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


# ---------------------------------------------------------------------------
# Shared base for backtesting tests
# ---------------------------------------------------------------------------

class BacktestTestBase(TestCase):
    """Base with resource dir, database & report cleanup."""

    def setUp(self) -> None:
        super().setUp()
        self.resource_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources"
        )
        self.backtest_databases_dir = os.path.join(
            self.resource_dir, "backtest_databases"
        )
        self.backtest_reports_dir = os.path.join(
            self.resource_dir, "backtest_reports"
        )

    def tearDown(self) -> None:
        super().tearDown()
        teardown_sqlalchemy()
        for path in (
            os.path.join(self.resource_dir, "databases"),
            self.backtest_databases_dir,
            self.backtest_reports_dir,
        ):
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests: run_backtest with initial amount / balance
# ---------------------------------------------------------------------------

class TestBacktestInitialConfig(BacktestTestBase):

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
        algorithm.add_strategy(HourlyTestStrategy)
        app.add_algorithm(algorithm)
        backtest = app.run_backtest(
            backtest_date_range=date_range,
            initial_amount=1000,
            risk_free_rate=0.027
        )
        run = backtest.get_backtest_run(date_range)
        metrics = backtest.get_backtest_metrics(date_range)
        self.assertEqual(run.initial_unallocated, 1000)
        self.assertEqual(metrics.total_growth, 0)
        self.assertEqual(metrics.total_growth_percentage, 0)
        self.assertEqual(metrics.total_net_gain, 0)
        self.assertEqual(metrics.total_net_gain_percentage, 0)
        self.assertAlmostEqual(run.number_of_runs, 373, places=1)
        self.assertEqual(run.trading_symbol, "USDT")
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
        algorithm.add_strategy(HourlyTestStrategy)
        app.add_algorithm(algorithm)
        backtest = app.run_backtest(
            backtest_date_range=date_range,
            risk_free_rate=0.027
        )
        run = backtest.get_backtest_run(date_range)
        metrics = backtest.get_backtest_metrics(date_range)
        self.assertEqual(run.initial_unallocated, 500)
        self.assertEqual(metrics.total_growth, 0)
        self.assertEqual(metrics.total_growth_percentage, 0)
        self.assertEqual(metrics.total_net_gain, 0)
        self.assertEqual(metrics.total_net_gain_percentage, 0)
        self.assertAlmostEqual(run.number_of_runs, 373, places=1)
        self.assertEqual(run.trading_symbol, "USDT")
        database_uri = app.config[SQLALCHEMY_DATABASE_URI]
        self.assertIsNotNone(database_uri)
        self.assertTrue(database_uri.endswith("backtest-database.sqlite3"))


# ---------------------------------------------------------------------------
# Tests: backtest report creation & saving
# ---------------------------------------------------------------------------

class TestBacktestReportCreation(BacktestTestBase):

    def _run_backtest(self, strategy=None, algorithm=None):
        """Helper to run a simple 1-day backtest."""
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir}
        )
        if algorithm is None:
            algorithm = Algorithm()
            algorithm.add_strategy(strategy or BacktestTestStrategy())
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
        return app.run_backtest(
            algorithm=algorithm,
            backtest_date_range=backtest_date_range,
            risk_free_rate=0.027
        )

    def test_report_json_creation(self):
        """Test that the backtest report is saved as JSON."""
        algorithm = Algorithm()
        algorithm.add_strategy(BacktestTestStrategy())
        backtest = self._run_backtest(algorithm=algorithm)
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing",
            "test_algorithm_backtest"
        )
        backtest.save(directory_path=path)
        self.assertTrue(os.path.isdir(path))

    def test_report_creation(self):
        backtest = self._run_backtest()
        save_dir = os.path.join(self.backtest_reports_dir, "test_backtest")
        backtest.save(save_dir)
        self.assertTrue(os.path.isdir(save_dir))

    def test_report_creation_without_strategy_identifier(self):
        strategy = BacktestTestStrategy()
        strategy.strategy_id = None
        algorithm = Algorithm()
        algorithm.add_strategy(strategy)
        backtest = self._run_backtest(algorithm=algorithm)
        save_dir = os.path.join(self.backtest_reports_dir, "test_backtest")
        backtest.save(save_dir)
        self.assertTrue(os.path.isdir(save_dir))


# ---------------------------------------------------------------------------
# Tests: run_backtests (multiple algorithms)
# ---------------------------------------------------------------------------

class TestRunBacktests(BacktestTestBase):

    def test_run_backtests(self):
        """Test that all backtests run when multiple algorithms are provided."""
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir}
        )
        algorithm_one = Algorithm()
        algorithm_one.add_strategy(BacktestTestStrategy())
        algorithm_two = Algorithm()
        algorithm_two.add_strategy(BacktestTestStrategy())
        algorithm_three = Algorithm()
        algorithm_three.add_strategy(BacktestTestStrategy())

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
