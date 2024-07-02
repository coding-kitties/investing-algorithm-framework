# from investing_algorithm_framework.core.exceptions import
# OperationalException
# from investing_algorithm_framework.core.models import OrderSide, OrderStatus
# from investing_algorithm_framework.core.models import OrderType
# from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
#
#
# class Test(TestBase, TestOrderAndPositionsObjectsMixin):
#
#     def setUp(self):
#         super(Test, self).setUp()
#         self.start_algorithm()
#
#     def test_validate_limit_buy_order(self):
#         portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
#
#         order_a = portfolio_manager.create_order(
#             order_type=OrderType.LIMIT.value,
#             order_side=OrderSide.BUY.value,
#             amount=1,
#             target_symbol=self.TARGET_SYMBOL_A,
#             price=self.BASE_SYMBOL_A_PRICE,
#             algorithm_context=None
#         )
#         order_a.set_reference_id(10)
#         portfolio_manager.add_order(order_a, algorithm_context=False)
#
#     def test_validate_limit_sell_order(self):
#         portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
#
#         order_a = portfolio_manager.create_order(
#             order_type=OrderType.LIMIT.value,
#             order_side=OrderSide.BUY.value,
#             amount=1,
#             target_symbol=self.TARGET_SYMBOL_A,
#             price=self.BASE_SYMBOL_A_PRICE,
#             algorithm_context=None
#         )
#         order_a.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
#         order_a.set_reference_id(10)
#         order_a.set_status(OrderStatus.CLOSED)
#         portfolio_manager.add_order(order_a, algorithm_context=None)
#         order_a.set_status(OrderStatus.PENDING)
#         order_a_sell = portfolio_manager.create_order(
#             order_type=OrderType.LIMIT.value,
#             order_side=OrderSide.SELL.value,
#             amount=1,
#             target_symbol=self.TARGET_SYMBOL_A,
#             price=self.BASE_SYMBOL_A_PRICE,
#             algorithm_context=None
#         )
#         order_a_sell.set_reference_id(11)
#         order_a_sell.set_status(OrderStatus.CLOSED)
#         order_a_sell.set_initial_price(
#             self.get_price(self.TARGET_SYMBOL_A).price
#         )
#         portfolio_manager.add_order(order_a_sell, algorithm_context=None)
#
#     def test_validate_limit_sell_order_larger_then_position(self):
#         portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
#
#         order_a = portfolio_manager.create_order(
#             order_type=OrderType.LIMIT.value,
#             order_side=OrderSide.BUY.value,
#             amount=1,
#             target_symbol=self.TARGET_SYMBOL_A,
#             price=self.BASE_SYMBOL_A_PRICE,
#             algorithm_context=None
#         )
#         order_a.set_reference_id(10)
#         order_a.set_status(OrderStatus.CLOSED)
#         order_a.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
#         portfolio_manager.add_order(order_a, algorithm_context=None)
#
#         with self.assertRaises(OperationalException) as exc:
#             portfolio_manager.create_order(
#                 order_type=OrderType.LIMIT.value,
#                 order_side=OrderSide.SELL.value,
#                 amount=2,
#                 target_symbol=self.TARGET_SYMBOL_A,
#                 price=self.BASE_SYMBOL_A_PRICE,
#                 algorithm_context=None
#             )
#
#     def test_validate_limit_order_with_unallocated_error(self):
#         portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
#
#         with self.assertRaises(OperationalException):
#             portfolio_manager.create_order(
#                 order_type=OrderType.LIMIT.value,
#                 order_side=OrderSide.BUY.value,
#                 amount=10000,
#                 target_symbol=self.TARGET_SYMBOL_A,
#                 price=self.BASE_SYMBOL_A_PRICE,
#                 algorithm_context=None
#             )
