"""
Consolidated tests for running strategies and the app.

Merged from:
- test_run.py
- test_start.py
- algorithm/test_run_strategy.py
"""
import os
import shutil
from unittest import TestCase
from typing import Dict, Any
import pandas as pd

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    Algorithm, MarketCredential
from tests.resources import random_string, OrderExecutorTest, \
    PortfolioProviderTest


# ---------------------------------------------------------------------------
# Shared test strategies
# ---------------------------------------------------------------------------

class EmptyStrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


class EmptyStrategyTwo(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


class CountingStrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2
    number_of_runs = 0

    def __init__(self, strategy_id=None, time_unit=None, interval=None,
                 market_data_sources=None, worker_id=None, decorated=None):
        super().__init__(strategy_id, time_unit, interval,
                         market_data_sources, worker_id, decorated)
        CountingStrategyOne.number_of_runs = 0

    def apply_strategy(self, context, data):
        CountingStrategyOne.number_of_runs += 1

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


class CountingStrategyTwo(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2
    number_of_runs = 0

    def __init__(self, strategy_id=None, time_unit=None, interval=None,
                 market_data_sources=None, worker_id=None, decorated=None):
        super().__init__(strategy_id, time_unit, interval,
                         market_data_sources, worker_id, decorated)
        CountingStrategyTwo.number_of_runs = 0

    def apply_strategy(self, context, data):
        CountingStrategyTwo.number_of_runs += 1

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        pass


# ---------------------------------------------------------------------------
# Shared base for run tests (setUp / tearDown with resource_dir + db cleanup)
# ---------------------------------------------------------------------------

class RunTestBase(TestCase):
    """Base class for tests that create apps manually with resource_dir."""

    def setUp(self) -> None:
        super().setUp()
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "resources"
            )
        )

    def tearDown(self) -> None:
        super().tearDown()
        for subdir in ("databases", "backtest_databases"):
            path = os.path.join(self.resource_dir, subdir)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def _create_app_with_strategies(self, strategy_classes, market="BINANCE",
                                     web=False):
        """Helper to create an app with given strategies + standard config."""
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir},
            web=web
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.container.portfolio_configuration_service().clear()
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market=market,
                trading_symbol="EUR",
            )
        )
        app.add_market_credential(
            MarketCredential(
                market=market,
                api_key=random_string(10),
                secret_key=random_string(10)
            )
        )
        algorithm = Algorithm()
        for cls in strategy_classes:
            algorithm.add_strategy(cls)
        app.add_algorithm(algorithm)
        return app


# ---------------------------------------------------------------------------
# Tests (previously spread across test_run.py, test_start.py,
# algorithm/test_run_strategy.py)
# ---------------------------------------------------------------------------

class TestRunWithIterations(RunTestBase):

    def test_with_number_of_iterations(self):
        app = self._create_app_with_strategies(
            [EmptyStrategyOne, EmptyStrategyTwo]
        )
        app.run(number_of_iterations=1)
        self.assertTrue(app.has_run("EmptyStrategyOne"))
        self.assertTrue(app.has_run("EmptyStrategyTwo"))

    def test_with_strategy_object(self):
        """Same as above but verifying strategy class names are used."""
        app = self._create_app_with_strategies(
            [EmptyStrategyOne, EmptyStrategyTwo], market="BITVAVO"
        )
        app.run(number_of_iterations=1)
        self.assertTrue(app.has_run("EmptyStrategyOne"))
        self.assertTrue(app.has_run("EmptyStrategyTwo"))

    def test_stateless(self):
        app = self._create_app_with_strategies(
            [EmptyStrategyOne, EmptyStrategyTwo], market="BITVAVO"
        )
        app.run(number_of_iterations=1)
        self.assertTrue(app.has_run("EmptyStrategyOne"))
        self.assertTrue(app.has_run("EmptyStrategyTwo"))


class TestStartDefault(RunTestBase):

    def test_default(self):
        app = self._create_app_with_strategies(
            [CountingStrategyOne, CountingStrategyTwo], market="BITVAVO"
        )
        app.run(number_of_iterations=2)
        self.assertTrue(app.has_run("CountingStrategyOne"))
        self.assertTrue(app.has_run("CountingStrategyTwo"))

    def test_web(self):
        app = self._create_app_with_strategies(
            [CountingStrategyOne, CountingStrategyTwo],
            market="BITVAVO",
            web=True
        )
        app.run(number_of_iterations=2)
        self.assertTrue(app.has_run("CountingStrategyOne"))
        self.assertTrue(app.has_run("CountingStrategyTwo"))
