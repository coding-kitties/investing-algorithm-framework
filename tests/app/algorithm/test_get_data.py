# import os
# from datetime import datetime, timedelta
# from investing_algorithm_framework import create_app, TradingStrategy, TimeUnit, \
#     RESOURCE_DIRECTORY, PortfolioConfiguration, TradingDataType, \
#     TradingTimeFrame
# from tests.resources import TestBase, MarketServiceStub
#
#
# class StrategyOne(TradingStrategy):
#     time_unit = TimeUnit.SECOND
#     interval = 2
#     trading_data_types = [
#         TradingDataType.OHLCV,
#         TradingDataType.TICKER,
#         TradingDataType.ORDER_BOOK
#     ]
#     trading_time_frame = TradingTimeFrame.ONE_MINUTE
#     trading_time_frame_start_date = datetime.utcnow() - timedelta(days=1)
#     symbols = ["ETH/EUR", "BTC/EUR"]
#     market = "BITVAVO"
#     market_data = False
#
#     def apply_strategy(self, algorithm, market_data):
#         algorithm.create_limit_order(
#             target_symbol="BTC",
#             amount=1,
#             order_side="BUY",
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
#                 market="bitvavo",
#                 api_key="test",
#                 secret_key="test",
#                 trading_symbol="USDT"
#             )
#         )
#         self.app.container.market_service.override(MarketServiceStub())
#         self.app.add_strategy(StrategyOne)
#         self.app.initialize()
#
#     def test_get_data(self):
#         self.app.run(number_of_iterations=1, sync=False)
#         order_service = self.app.container.order_service()
#         order_service.check_pending_orders()
