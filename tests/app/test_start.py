import os

from investing_algorithm_framework import create_app, TradingStrategy, TimeUnit, \
    RESOURCE_DIRECTORY, PortfolioConfiguration
from tests.resources import TestBase, MarketServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def apply_strategy(
        self,
        algorithm,
        market_date=None,
        **kwargs
    ):
        pass


class StrategyTwo(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def apply_strategy(
        self,
        algorithm,
        market_date=None,
        **kwargs
    ):
        pass


class Test(TestBase):

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
        self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                api_key="test",
                secret_key="test",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub())
        self.app.add_strategy(StrategyOne)
        self.app.add_strategy(StrategyTwo)

    def test_default(self):
        self.app.run(number_of_iterations=2, sync=False)
        self.assertFalse(self.app.running)
        strategy_orchestrator_service = self.app \
            .algorithm.strategy_orchestrator_service
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))

    def test_web(self):
        self.app.run(number_of_iterations=2, sync=False)
        self.assertFalse(self.app.running)
        strategy_orchestrator_service = self.app \
            .algorithm.strategy_orchestrator_service
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))

    def test_stateless(self):
        self.app.run(
            number_of_iterations=2,
            payload={"ACTION": "RUN_STRATEGY"},
            sync=False
        )
        strategy_orchestrator_service = self.app\
            .algorithm.strategy_orchestrator_service
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
        self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))
