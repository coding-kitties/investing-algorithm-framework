from investing_algorithm_framework import OrderStatus, OrderType, OrderSide
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('default')

        order = portfolio_manager.create_order(
            type=OrderType.LIMIT.value,
            side=OrderSide.BUY.value,
            amount_target_symbol=1,
            target_symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            algorithm_context=None
        )
        order.set_status(OrderStatus.PENDING)
        order.set_reference_id(2)
        order.set_initial_price(self.get_price(self.TARGET_SYMBOL_A).price)
        portfolio_manager.add_order(order, algorithm_context=None)

        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager('default')
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)

        self.assertIsNotNone(position)
        self.assertEqual(1, len(portfolio.get_orders()))
        self.assertEqual(2, len(portfolio.get_positions()))
        self.assertEqual(0, position.get_amount())
        self.assertEqual(self.TARGET_SYMBOL_A, position.get_target_symbol())

        self.algo_app.algorithm.check_order_status(identifier="default")
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertIsNotNone(position)
        self.assertEqual(1, len(portfolio.get_orders()))
        self.assertEqual(2, len(portfolio.get_positions()))
        self.assertEqual(1, position.get_amount())
        self.assertEqual(self.TARGET_SYMBOL_A, position.get_target_symbol())
