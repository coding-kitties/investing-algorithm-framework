from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderSide, Portfolio, \
    OrderType
from tests.resources import TestBase, SYMBOL_A, SYMBOL_A_PRICE, \
    TestOrderAndPositionsObjectsMixin, SYMBOL_B, SYMBOL_B_PRICE, \
    set_symbol_a_price, set_symbol_b_price


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def test_creation(self):
        self.assertEqual(1, Portfolio.query.count())

    def test_sell_order_creation(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertIsNotNone(order)

        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))
        self.assertIsNone(order.order_reference)
        self.assertEqual(1, order.amount)
        self.assertEqual(SYMBOL_A_PRICE, order.price)
        self.assertIsNone(order.status)
        self.assertIsNone(order.executed_at)

    def test_buy_order_creation(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertIsNotNone(order)

        self.assertTrue(OrderSide.BUY.equals(order.order_side))
        self.assertTrue(OrderType.LIMIT.equals(order.order_type))
        self.assertIsNone(order.order_reference)
        self.assertEqual(1, order.amount)
        self.assertEqual(SYMBOL_A_PRICE, order.price)
        self.assertIsNone(order.status)
        self.assertIsNone(order.executed_at)

    def test_buy_order_creation_larger_then_unallocated(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.assertEqual(
            float(1000),
            float(portfolio_manager.get_portfolio().unallocated)
        )

        with self.assertRaises(OperationalException) as e:
            order = portfolio_manager.create_order(
                order_type=OrderType.LIMIT.value,
                order_side=OrderSide.BUY.value,
                amount=10000,
                symbol=SYMBOL_A,
                price=SYMBOL_A_PRICE,
                validate_pair=True,
                context=None
            )

            portfolio_manager.add_order(order)

    def test_get_positions(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_B,
            price=SYMBOL_B_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        # Before executed
        portfolio = portfolio_manager.get_portfolio()

        position_a = portfolio.positions.filter_by(symbol=SYMBOL_A).first()
        position_b = portfolio.positions.filter_by(symbol=SYMBOL_B).first()

        self.assertEqual(0, position_a.amount)
        self.assertEqual(0, position_b.amount)

        # After executed
        order_a.set_executed()
        order_b.set_executed()

        position_a = portfolio.positions.filter_by(symbol=SYMBOL_A).first()
        position_b = portfolio.positions.filter_by(symbol=SYMBOL_B).first()

        self.assertNotEqual(0, position_a.amount)
        self.assertNotEqual(0, position_b.amount)

    def test_delta(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_B,
            price=SYMBOL_B_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        # Before executed
        portfolio = portfolio_manager.get_portfolio()

        self.assertEqual(0, portfolio.delta)

        # After executed
        order_a.set_executed()
        order_b.set_executed()

        self.assertEqual(0, portfolio.delta)

        # Increase prices
        set_symbol_a_price(SYMBOL_A_PRICE * 1.1)
        set_symbol_b_price(SYMBOL_B_PRICE * 1.1)

        self.assertNotEqual(0, portfolio.delta)

    def test_realized(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = portfolio_manager.get_portfolio()
        initial_realized = portfolio.realized

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_B,
            price=SYMBOL_B_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)
        self.assertEqual(portfolio.unallocated, portfolio.realized)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        # Before executed
        self.assertNotEqual(portfolio.unallocated, portfolio.realized)
        self.assertEqual(initial_realized, portfolio.realized)

        # After executed
        order_a.set_executed()
        order_b.set_executed()

        self.assertNotEqual(portfolio.unallocated, portfolio.realized)
        self.assertEqual(initial_realized, portfolio.realized)

        # Increase prices
        set_symbol_a_price(SYMBOL_A_PRICE * 1.1)
        set_symbol_b_price(SYMBOL_B_PRICE * 1.1)

        self.assertNotEqual(portfolio.unallocated, portfolio.realized)
        self.assertEqual(initial_realized, portfolio.realized)

        # Sell position a
        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE * 1.1,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

        order_a_sell.set_executed()

        self.assertNotEqual(portfolio.unallocated, portfolio.realized)
        self.assertNotEqual(initial_realized, portfolio.realized)

    def test_allocated(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = portfolio_manager.get_portfolio()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_B,
            price=SYMBOL_B_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)
        self.assertEqual(0, portfolio.allocated)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertEqual(0, portfolio.allocated)
        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        # Before executed
        self.assertEqual(0, portfolio.allocated)

        # After executed
        order_a.set_executed()
        order_b.set_executed()

        self.assertNotEqual(0, portfolio.allocated)

    def test_allocated_percentage(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = portfolio_manager.get_portfolio()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_B,
            price=SYMBOL_B_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)
        self.assertEqual(0, portfolio.allocated_percentage)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertEqual(0, portfolio.allocated_percentage)
        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        # Before executed
        self.assertEqual(0, portfolio.allocated)

        # After executed
        order_a.set_executed()
        order_b.set_executed()

        self.assertNotEqual(0, portfolio.allocated_percentage)

    def test_unallocated_percentage(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = portfolio_manager.get_portfolio()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_B,
            price=SYMBOL_B_PRICE,
            validate_pair=True,
            context=None
        )

        self.assertEqual(len(portfolio_manager.get_positions()), 0)
        self.assertEqual(100, portfolio.unallocated_percentage)

        portfolio_manager.add_order(order_a)
        portfolio_manager.add_order(order_b)

        self.assertTrue(100 > portfolio.unallocated_percentage)
        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        # Before executed
        self.assertTrue(100 > portfolio.unallocated_percentage)

        # After executed
        order_a.set_executed()
        order_b.set_executed()

        self.assertTrue(100 > portfolio.unallocated_percentage)
