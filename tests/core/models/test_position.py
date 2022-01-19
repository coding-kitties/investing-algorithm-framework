from investing_algorithm_framework.core.models import OrderSide, OrderType, \
    OrderStatus
from tests.resources import TestBase


class TestPosition(TestBase):

    def setUp(self):
        super(TestPosition, self).setUp()
        self.start_algorithm()

    def test_creation(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertEqual(len(portfolio_manager.get_positions()), 2)

    def test_add_buy_order(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        portfolio_manager.add_order(order_a)
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.amount)

        order_a.set_pending()
        order_a.set_executed()

        self.assertNotEqual(0, position.amount)

    def test_add_sell_order(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        self.assertIsNone(order_a.status)

        portfolio_manager.add_order(order_a)

        self.assertTrue(OrderStatus.TO_BE_SENT.equals(order_a.status))
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.amount)

        order_a.set_pending()
        order_a.set_executed()

        self.assertEqual(1, position.amount)

        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        self.assertEqual(1, position.amount)

        order_a_sell.set_pending()
        order_a_sell.set_executed()

        self.assertEqual(0, position.amount)

    def test_delta(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        portfolio_manager.add_order(order_a)
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.amount)
        self.assertEqual(0, position.delta)

        order_a.set_pending()
        order_a.set_executed()

        self.assertNotEqual(0, position.amount)
        self.assertEqual(0, position.delta)

        # Increase price
        self.update_price(self.TARGET_SYMBOL_A, self.BASE_SYMBOL_A_PRICE * 1.1)

        self.assertNotEqual(0, position.delta)

        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        self.assertNotEqual(0, position.delta)

        order_a_sell.set_pending()
        order_a_sell.set_executed()

        self.assertEqual(0, position.delta)
