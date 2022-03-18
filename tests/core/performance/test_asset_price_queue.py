# from investing_algorithm_framework.core.models import TimeFrame
# from investing_algorithm_framework.core.models.snapshots \
#     import SQLLiteAssetPriceHistory, \
#     SQLLiteAssetPrice
# from investing_algorithm_framework.core.performance import AssetPricesQueue
# from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
#
#
# class TestClass(TestBase, TestOrderAndPositionsObjectsMixin):
#
#     def test_asset_price_queue(self):
#         symbol_a_asset_price_history = SQLLiteAssetPriceHistory\
#             .of("test", self.TARGET_SYMBOL_A, "USDT", TimeFrame.ONE_DAY)
#
#         symbol_a_prices = symbol_a_asset_price_history.get_prices()
#
#         symbol_b_asset_price_history = SQLLiteAssetPriceHistory\
#             .of("test", self.TARGET_SYMBOL_B, "USDT", TimeFrame.ONE_DAY)
#
#         symbol_b_prices = symbol_b_asset_price_history.get_prices()
#
#         symbol_c_asset_price_history = SQLLiteAssetPriceHistory\
#             .of("test", self.TARGET_SYMBOL_C, "USDT", TimeFrame.ONE_DAY)
#
#         symbol_c_prices = symbol_c_asset_price_history.get_prices()
#
#         prices = [symbol_a_prices, symbol_b_prices, symbol_c_prices]
#
#         asset_price_queue = AssetPricesQueue(prices, TimeFrame.ONE_DAY)
#
#         self.assertFalse(asset_price_queue.empty())
#         self.assertTrue(asset_price_queue.size > 0)
#         self.assertEqual(
#             len(asset_price_queue.intervals),
#             TimeFrame.ONE_DAY.time_interval.amount_of_data_points()
#         )
#         self.assertEqual(
#             len(asset_price_queue.asset_prices),
#             TimeFrame.ONE_DAY.time_interval.amount_of_data_points()
#         )
#
#         while not asset_price_queue.empty():
#             date, current_selection = asset_price_queue.pop()
#             peek_date, peek_selection = asset_price_queue.peek()
#
#             if peek_selection is not None:
#                 self.assertTrue(date < peek_date)
#                 self.assertTrue(
#                     current_selection[0].datetime < peek_selection[0].datetime
#                 )
#
#     def test_removing(self):
#         symbol_a_asset_price_history = SQLLiteAssetPriceHistory\
#             .of("test", self.TARGET_SYMBOL_A, "USDT", TimeFrame.ONE_DAY)
#
#         self.assertEqual(
#             SQLLiteAssetPrice.query.count(),
#             TimeFrame.ONE_DAY.time_interval.amount_of_data_points()
#         )
#
#         symbol_a_asset_price_history.remove_prices()
#         self.assertEqual(SQLLiteAssetPrice.query.count(), 0)
