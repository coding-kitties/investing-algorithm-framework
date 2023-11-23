# import os
# from datetime import datetime, timedelta
# from investing_algorithm_framework import create_app, PortfolioConfiguration, \
#     RESOURCE_DIRECTORY
# from investing_algorithm_framework.dependency_container import \
#     DependencyContainer
# from tests.resources import TestBase, MarketServiceStub
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
#
#     def test(self):
#         app = create_app(
#             config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
#         )
#         app.backtest(
#             start_date=datetime.utcnow() - timedelta(days=1),
#             end_date=datetime.utcnow(),
#             unallocated=1000,
#             trading_symbol="EUR"
#         )
