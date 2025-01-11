# import os

# from investing_algorithm_framework import create_app, TradingStrategy, \
#     TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration, Algorithm, \
#     MarketCredential
# from tests.resources import TestBase, MarketServiceStub


# class StrategyOne(TradingStrategy):
#     time_unit = TimeUnit.SECOND
#     interval = 2

#     def apply_strategy(
#         self,
#         algorithm,
#         market_date=None,
#         **kwargs
#     ):
#         pass


# class StrategyTwo(TradingStrategy):
#     time_unit = TimeUnit.SECOND
#     interval = 2

#     def apply_strategy(
#         self,
#         algorithm,
#         market_date=None,
#         **kwargs
#     ):
#         pass


# class Test(TestBase):

#     def setUp(self) -> None:
#         self.resource_dir = os.path.abspath(
#             os.path.join(
#                 os.path.join(
#                     os.path.join(
#                         os.path.realpath(__file__),
#                         os.pardir
#                     ),
#                     os.pardir
#                 ),
#                 "resources"
#             )
#         )
#         self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
#         self.app.add_portfolio_configuration(
#             PortfolioConfiguration(
#                 market="BITVAVO",
#                 trading_symbol="EUR"
#             )
#         )

#         self.app.container.market_service.override(MarketServiceStub(None))
#         algorithm = Algorithm()
#         algorithm.add_strategy(StrategyOne)
#         algorithm.add_strategy(StrategyTwo)
#         self.app.add_algorithm(algorithm)
#         self.app.add_market_credential(
#             MarketCredential(
#                 market="BITVAVO",
#                 api_key="api_key",
#                 secret_key="secret_key"
#             )
#         )

#     def test_default(self):
#         self.app.run(number_of_iterations=2)
#         self.assertFalse(self.app.running)
#         strategy_orchestrator_service = self.app \
#             .algorithm.strategy_orchestrator_service
#         self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
#         self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))

#     def test_web(self):
#         self.app.run(number_of_iterations=2)
#         self.assertFalse(self.app.running)
#         strategy_orchestrator_service = self.app \
#             .algorithm.strategy_orchestrator_service
#         self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
#         self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))

#     def test_stateless(self):
#         self.app.run(
#             number_of_iterations=2,
#             payload={"ACTION": "RUN_STRATEGY"},
#         )
#         strategy_orchestrator_service = self.app\
#             .algorithm.strategy_orchestrator_service
#         self.assertTrue(strategy_orchestrator_service.has_run("StrategyOne"))
#         self.assertTrue(strategy_orchestrator_service.has_run("StrategyTwo"))
