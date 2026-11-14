import os
import shutil
from unittest import TestCase

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration, Algorithm, \
    MarketCredential, Schedule
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from tests.resources import OrderExecutorTest, PortfolioProviderTest


class StrategyOne(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)
    number_of_runs = 0

    def __init__(
        self,
        strategy_id=None,
        time_unit=None,
        interval=None,
        market_data_sources=None,
        worker_id=None,
        decorated=None
    ):
        super().__init__(
            strategy_id,
            time_unit,
            interval,
            market_data_sources,
            worker_id,
            decorated
        )
        StrategyOne.number_of_runs = 0

    def apply_strategy(
        self,
        context,
        data,
    ):
        StrategyOne.number_of_runs += 1


class StrategyTwo(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)
    number_of_runs = 0

    def __init__(
        self,
        strategy_id=None,
        time_unit=None,
        interval=None,
        market_data_sources=None,
        worker_id=None,
        decorated=None
    ):
        super().__init__(
            strategy_id,
            time_unit,
            interval,
            market_data_sources,
            worker_id,
            decorated
        )
        StrategyOne.number_of_runs = 0

    def apply_strategy(
        self,
        context,
        data,
    ):
        StrategyTwo.number_of_runs += 1

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

    def tearDown(self):
        teardown_sqlalchemy()
        for subdir in ("databases", "backtest_databases"):
            path = os.path.join(self.resource_dir, subdir)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def test_default(self):
        app = create_app({
            RESOURCE_DIRECTORY: self.resource_dir
        })
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        algorithm.add_strategy(StrategyTwo)
        app.add_algorithm(algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.run(number_of_iterations=2)
        self.assertTrue(app.has_run("StrategyOne"))
        self.assertTrue(app.has_run("StrategyTwo"))

    def test_web(self):
        app = create_app(
            web=True,
            config={ RESOURCE_DIRECTORY: self.resource_dir }
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        algorithm.add_strategy(StrategyTwo)
        app.add_algorithm(algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.run(number_of_iterations=2)
        self.assertTrue(app.has_run("StrategyOne"))
        self.assertTrue(app.has_run("StrategyTwo"))
