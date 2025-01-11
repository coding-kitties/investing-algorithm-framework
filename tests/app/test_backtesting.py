# from investing_algorithm_framework import TradingStrategy, Algorithm


# class SimpleTradingStrategy(TradingStrategy):
#     interval = 2
#     time_unit = "hour"

#     def apply_strategy(self, algorithm: Algorithm, market_data):

#         if algorithm.has_open_orders():
#             return

#         algorithm.create_limit_order(
#             target_symbol="BTC",
#             amount=0.01,
#             price=10000,
#             order_side="buy"
#         )


# # class Test(TestCase):
# #
# #     def setUp(self) -> None:
# #         self.resource_dir = os.path.abspath(
# #             os.path.join(
# #                 os.path.join(
# #                     os.path.join(
# #                         os.path.realpath(__file__),
# #                         os.pardir
# #                     ),
# #                     os.pardir
# #                 ),
# #                 "resources"
# #             )
# #         )
# #         self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
# #         self.app.add_portfolio_configuration(
# #             PortfolioConfiguration(
# #                 market="BITVAVO",
# #                 trading_symbol="USDT"
# #             )
# #         )
# #         self.app.add_strategy(SimpleTradingStrategy)
