# import os
#
# from investing_algorithm_framework import create_app, PortfolioConfiguration, \
#     RESOURCE_DIRECTORY
# from tests.resources import TestBase
#
#
# class Test(TestBase):
#
#     def setUp(self) -> None:
#         super(Test, self).setUp()
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
#         app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
#         app.add_portfolio_configuration(
#             PortfolioConfiguration(
#                 api_key="a427b767722f60338fbda9782e3d3af48583e9bdc3a25d0f65611a15b5a5b912",
#                 secret_key="1cd87221cd3775d5e008c05487bfeb8b738a657e4f12a64b4d70078e12700915b7a665bb19e94abc0ccecf2095e29d1671f90b27f2a8fcb945faf40abc953c87",
#                 market="BITVAVO",
#                 trading_symbol="EUR",
#             )
#         )
#         app.run(number_of_iterations=1)
#         order_service = app.container.order_service()
#         position_service = app.container.position_service()
#         self.assertNotEqual(0, len(order_service.get_all()))
#         self.assertNotEqual(0, len(position_service.get_all()))
