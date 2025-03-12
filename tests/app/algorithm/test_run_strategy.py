import os
from unittest import TestCase

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    Algorithm, MarketCredential
from tests.resources import random_string, MarketServiceStub, \
    MarketDataSourceServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def apply_strategy(self, context, market_data):
        pass


class StrategyTwo(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def apply_strategy(self, context, market_data):
        pass


class Test(TestCase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    external_balances = {
        "EUR": 1000,
    }
    market_data_source_service = MarketDataSourceServiceStub()

    def setUp(self) -> None:
        super(Test, self).setUp()
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
        super().tearDown()
        # Delete the resources database directory

        database_dir = os.path.join(self.resource_dir, "databases")

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))


    def test_with_strategy_object(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.container.market_service.override(MarketServiceStub(None))
        app.container.portfolio_configuration_service().clear()
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BINANCE",
                trading_symbol="EUR",
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                api_key=random_string(10),
                secret_key=random_string(10)
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        algorithm.add_strategy(StrategyTwo)
        app.add_algorithm(algorithm)
        app.run(number_of_iterations=2)
        self.assertFalse(app.running)
        strategy_orchestration_service = app.algorithm\
            .strategy_orchestrator_service
        self.assertTrue(strategy_orchestration_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestration_service.has_run("StrategyTwo"))

    def test_with_decorator(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.container.market_service.override(MarketServiceStub(None))
        app.container.portfolio_configuration_service().clear()
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BINANCE",
                trading_symbol="EUR",
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                api_key=random_string(10),
                secret_key=random_string(10)
            )
        )
        algorithm = Algorithm()

        @algorithm.strategy(time_unit=TimeUnit.SECOND, interval=1)
        def run_strategy(algorithm, market_data):
            pass

        app.add_algorithm(algorithm)
        app.run(number_of_iterations=1)
        strategy_orchestration_service = app.algorithm\
            .strategy_orchestrator_service
        self.assertTrue(strategy_orchestration_service.has_run("run_strategy"))

    def test_stateless(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.container.market_service.override(MarketServiceStub(None))
        app.container.portfolio_configuration_service().clear()
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key=random_string(10),
                secret_key=random_string(10)
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        algorithm.add_strategy(StrategyTwo)
        app.add_algorithm(algorithm)
        app.run(
            number_of_iterations=2,
            payload={"ACTION": "RUN_STRATEGY"},
        )
        strategy_orchestration_service = app.algorithm\
            .strategy_orchestrator_service
        self.assertTrue(strategy_orchestration_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestration_service.has_run("StrategyTwo"))
