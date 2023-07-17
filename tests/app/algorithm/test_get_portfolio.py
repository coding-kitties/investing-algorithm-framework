# import os
#
# from investing_algorithm_framework import create_app, Strategy, TimeUnit, \
#     RESOURCE_DIRECTORY, PortfolioConfiguration
# from tests.resources import TestBase, MarketServiceStub
#
#
# class StrategyOne(Strategy):
#     time_unit = TimeUnit.SECOND
#     interval = 2
#
#     def apply_strategy(
#         self,
#         algorithm,
#         market_date=None,
#         **kwargs
#     ):
#         algorithm.create_limit_order(
#             target_symbol="BTC",
#             amount=1,
#             side="BUY",
#             price=10,
#         )
#
#
# class Test(TestBase):
#
#     def setUp(self) -> None:
#         self.resource_dir = os.path.abspath(
#             os.path.join(
#                 os.path.join(
#                     os.path.join(
#                         os.path.join(
#                             os.path.realpath(__file__),
#                             os.pardir
#                         ),
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
#                 market="BINANCE",
#                 api_key="test",
#                 secret_key="test",
#                 trading_symbol="USDT"
#             )
#         )
#         self.app.container.market_service.override(MarketServiceStub())
#         self.app.add_strategy(StrategyOne)
#
#     def test_get_portfolio(self):
#         self.app.run(number_of_iterations=1, sync=False)
#         self.app.algorithm.order_service.check_pending_orders()
#         portfolio = self.app.algorithm.get_portfolio()
#         self.assertEqual(portfolio.market.upper(), "BINANCE")
#         self.assertEqual(portfolio.trading_symbol, "USDT")
