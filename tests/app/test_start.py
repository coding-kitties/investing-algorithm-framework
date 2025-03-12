import os
from unittest import TestCase

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration, Algorithm, \
    MarketCredential
from tests.resources import MarketServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2
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
        market_date=None,
        **kwargs
    ):
        StrategyOne.number_of_runs += 1


class StrategyTwo(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2
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
        market_date=None,
        **kwargs
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
        paths = [
            os.path.join(
                self.resource_dir, "databases"
            ),
            os.path.join(
                self.resource_dir, "backtest_databases"
            )
        ]

        for path in paths:
            self._remove_directory(path)

    def _remove_directory(self, path):
        if os.path.exists(path):
            for root, dirs, files in os.walk(path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    def test_default(self):
        app = create_app({
            RESOURCE_DIRECTORY: self.resource_dir
        })
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        app.container.market_service.override(MarketServiceStub(None))
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
        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000
        }
        app.container.market_service.override(market_service_stub)
        # while app.running:
        #     time.sleep(1)
        app.run(number_of_iterations=2)
        # self.assertEqual(2, StrategyOne.number_of_runs)
        # self.assertEqual(2, StrategyTwo.number_of_runs)
        self.assertFalse(app.running)
        strategy_orchestrator_service = app \
            .algorithm.strategy_orchestrator_service
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))

    def test_web(self):
        app = create_app(
            web=True,
            config={ RESOURCE_DIRECTORY: self.resource_dir }
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        app.container.market_service.override(MarketServiceStub(None))
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
        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000
        }
        app.container.market_service.override(market_service_stub)
        app.run(number_of_iterations=2)
        # self.assertEqual(2, StrategyOne.number_of_runs)
        # self.assertEqual(2, StrategyTwo.number_of_runs)
        self.assertFalse(app.running)
        strategy_orchestrator_service = app \
            .algorithm.strategy_orchestrator_service
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))

    def test_with_payload(self):
        app = create_app(
            config={ RESOURCE_DIRECTORY: self.resource_dir }
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        app.container.market_service.override(MarketServiceStub(None))
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
        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000
        }
        app.container.market_service.override(market_service_stub)
        app.run(
            number_of_iterations=2,
            payload={"ACTION": "RUN_STRATEGY"},
        )
        # self.assertEqual(2, StrategyOne.number_of_runs)
        # self.assertEqual(2, StrategyTwo.number_of_runs)
        strategy_orchestrator_service = app\
            .algorithm.strategy_orchestrator_service
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))
