from investing_algorithm_framework.core.models import OrderSide, OrderType
from tests.resources import TestBase, SYMBOL_B, SYMBOL_A, SYMBOL_A_PRICE, \
    SYMBOL_B_PRICE, set_symbol_a_price


class TestPosition(TestBase):

    def test_creation(self):
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

    def test_add_buy_order(self):
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

        portfolio_manager.add_order(order_a)
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.amount)

        order_a.set_executed()

        self.assertNotEqual(0, position.amount)

    def test_add_sell_order(self):
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

        portfolio_manager.add_order(order_a)
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.amount)

        order_a.set_executed()

        self.assertNotEqual(0, position.amount)

        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        self.assertNotEqual(0, position.amount)

        order_a_sell.set_executed()

        self.assertEqual(0, position.amount)

    def test_total_cost(self):
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

        portfolio_manager.add_order(order_a)
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.cost)
        self.assertEqual(0, position.amount)
        self.assertEqual(0, position.delta)

        order_a.set_pending()
        order_a.set_executed()

        self.assertNotEqual(0.0, position.cost)
        self.assertNotEqual(0, position.amount)
        self.assertEqual(0, position.delta)

        # Increase price
        set_symbol_a_price(SYMBOL_A_PRICE * 1.1)

        self.assertNotEqual(0, position.cost)
        self.assertNotEqual(0, position.delta)

        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        self.assertNotEqual(0, position.delta)

        order_a_sell.set_pending()
        order_a_sell.set_executed()

        self.assertEqual(0, position.delta)
        self.assertEqual(0, position.cost)

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

        portfolio_manager.add_order(order_a)
        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        portfolio = portfolio_manager.get_portfolio()
        position = portfolio.positions.first()

        self.assertEqual(0, position.amount)
        self.assertEqual(0, position.delta)

        order_a.set_executed()

        self.assertNotEqual(0, position.amount)
        self.assertEqual(0, position.delta)

        # Increase price
        set_symbol_a_price(SYMBOL_A_PRICE * 1.1)

        self.assertNotEqual(0, position.delta)

        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

        self.assertEqual(len(portfolio_manager.get_positions()), 1)

        self.assertNotEqual(0, position.delta)

        order_a_sell.set_executed()

        self.assertEqual(0, position.delta)
