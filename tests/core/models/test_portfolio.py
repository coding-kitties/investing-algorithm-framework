from datetime import datetime
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderSide, OrderType, \
    SQLLitePortfolio
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test_creation(self):
        self.assertEqual(1, SQLLitePortfolio.query.count())

    def test_allocated(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = self.algo_app.algorithm.get_portfolio_manager()\
            .get_portfolio()

        initial_unallocated = portfolio.unallocated

        self.assertEqual(1000, initial_unallocated)
        self.assertEqual(0, portfolio.allocated)
        self.assertEqual(0, portfolio.allocated_percentage)
        self.assertEqual(100, portfolio.unallocated_percentage)
        self.assertEqual(0, portfolio.positions.count())

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            context=None
        )
        portfolio.add_order(order_a)

        self.assertEqual(
            initial_unallocated - (self.BASE_SYMBOL_A_PRICE * 1),
            portfolio.unallocated
        )
        self.assertEqual(0, portfolio.allocated)

        order_a.set_pending()

        self.assertEqual(0, portfolio.allocated)

        order_a.set_executed()

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price * 1,
            portfolio.allocated
        )
        self.assertNotEqual(0, portfolio.allocated_percentage)
        self.assertNotEqual(100, portfolio.unallocated_percentage)
        self.assertEqual(1, portfolio.positions.count())

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )
        portfolio.add_order(order_b)

        self.assertEqual(
            initial_unallocated - self.BASE_SYMBOL_A_PRICE *
            1 - (self.get_price(self.TARGET_SYMBOL_B).price * 1),
            portfolio.unallocated
        )

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price * 1,
            portfolio.allocated
        )

        order_b.set_pending()

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price * 1,
            portfolio.allocated
        )

        order_b.set_executed()

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price *
            1 + self.get_price(self.TARGET_SYMBOL_B).price * 1,
            portfolio.allocated
        )

        self.assertNotEqual(0, portfolio.allocated_percentage)
        self.assertNotEqual(100, portfolio.unallocated_percentage)
        self.assertEqual(2, portfolio.positions.count())

        sell_order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        portfolio.add_order(sell_order_a)
        sell_order_a.set_pending()
        sell_order_a.set_executed()

        sell_order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )
        portfolio.add_order(sell_order_b)
        sell_order_b.set_pending()
        sell_order_b.set_executed()

        self.assertEqual(0, portfolio.allocated)
        self.assertEqual(2, portfolio.positions.count())

    def test_allocated_percentage(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = self.algo_app.algorithm.get_portfolio_manager()\
            .get_portfolio()

        initial_unallocated = portfolio.unallocated

        self.assertEqual(1000, initial_unallocated)
        self.assertEqual(0, portfolio.allocated)
        self.assertEqual(0, portfolio.allocated_percentage)
        self.assertEqual(100, portfolio.unallocated_percentage)
        self.assertEqual(0, portfolio.positions.count())

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )
        portfolio.add_order(order_a)

        self.assertEqual(
            initial_unallocated - (self.BASE_SYMBOL_A_PRICE * 1),
            portfolio.unallocated
        )
        self.assertEqual(0, portfolio.allocated_percentage)

        order_a.set_pending()

        self.assertEqual(0, portfolio.allocated_percentage)

        order_a.set_executed()

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price * 1,
            portfolio.allocated
        )
        self.assertNotEqual(0, portfolio.allocated_percentage)
        self.assertNotEqual(100, portfolio.unallocated_percentage)
        self.assertEqual(1, portfolio.positions.count())

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )
        portfolio.add_order(order_b)

        self.assertEqual(
            initial_unallocated - self.BASE_SYMBOL_A_PRICE *
            1 - (self.get_price(self.TARGET_SYMBOL_B).price * 1),
            portfolio.unallocated
        )

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price * 1,
            portfolio.allocated
        )

        order_b.set_pending()

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price * 1,
            portfolio.allocated
        )

        order_b.set_executed()

        self.assertEqual(
            self.get_price(self.TARGET_SYMBOL_A).price *
            1 + self.get_price(self.TARGET_SYMBOL_B).price * 1,
            portfolio.allocated
        )

        self.assertNotEqual(0, portfolio.allocated_percentage)
        self.assertNotEqual(100, portfolio.unallocated_percentage)
        self.assertEqual(2, portfolio.positions.count())

        sell_order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        portfolio.add_order(sell_order_a)
        sell_order_a.set_pending()
        sell_order_a.set_executed()

        sell_order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )
        portfolio.add_order(sell_order_b)
        sell_order_b.set_pending()
        sell_order_b.set_executed()

        self.assertEqual(0, portfolio.allocated_percentage)
        self.assertEqual(2, portfolio.positions.count())

    def test_limit_sell_order_creation(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )

        self.assertIsNotNone(order)
        self.assert_is_limit_order(order)

    def test_limit_buy_order_creation(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )

        self.assertIsNotNone(order)
        self.assert_is_limit_order(order)

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
                amount_target_symbol=1000,
                symbol=self.TARGET_SYMBOL_B,
                price=self.get_price(self.TARGET_SYMBOL_B).price,
                context=None
            )

            portfolio_manager.add_order(order)

    def test_get_positions(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = self.algo_app.algorithm.get_portfolio_manager()\
            .get_portfolio()

        self.assertEqual(len(portfolio_manager.get_positions()), 0)

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )
        portfolio.add_order(order_a)

        order_b = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_B,
            price=self.get_price(self.TARGET_SYMBOL_B).price,
            context=None
        )
        portfolio.add_order(order_b)

        self.assertEqual(len(portfolio_manager.get_positions()), 2)

        position_a = portfolio.positions\
            .filter_by(symbol=self.TARGET_SYMBOL_A)\
            .first()
        position_b = portfolio.positions\
            .filter_by(symbol=self.TARGET_SYMBOL_B)\
            .first()

        self.assertEqual(0, position_a.amount)
        self.assertEqual(0, position_b.amount)

        # After executed
        order_a.set_pending()
        order_a.set_executed()
        order_b.set_pending()
        order_b.set_executed()

        position_a = portfolio.positions\
            .filter_by(symbol=self.TARGET_SYMBOL_A)\
            .first()
        position_b = portfolio.positions\
            .filter_by(symbol=self.TARGET_SYMBOL_B)\
            .first()

        self.assertNotEqual(0, position_a.amount)
        self.assertNotEqual(0, position_b.amount)

    # def test_realized(self):
    #     portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
    #     portfolio = portfolio_manager.get_portfolio()
    #
    #     self.assertEqual(0, portfolio.realized)
    #
    #     order_a = portfolio_manager.create_order(
    #         order_type=OrderType.LIMIT.value,
    #         order_side=OrderSide.BUY.value,
    #         amount_target_symbol=1,
    #         symbol=self.TARGET_SYMBOL_A,
    #         price=self.get_price(self.TARGET_SYMBOL_A).price,
    #         validate_pair=True,
    #         context=None
    #     )
    #     portfolio.add_order(order_a)
    #
    #     order_a.set_pending()
    #     order_a.set_executed()
    #
    #     self.assertEqual(0, portfolio.realized)
    #
    #     self.update_price(
    #         self.TARGET_SYMBOL_A,
    #         1.1 * self.get_price(
    #             self.TARGET_SYMBOL_A, date=datetime.utcnow()
    #         ).price,
    #         date=datetime.utcnow()
    #     )
    #
    #     order_a = portfolio_manager.create_order(
    #         order_type=OrderType.LIMIT.value,
    #         order_side=OrderSide.SELL.value,
    #         amount_target_symbol=1,
    #         symbol=self.TARGET_SYMBOL_A,
    #         price=self.get_price(self.TARGET_SYMBOL_A).price,
    #         validate_pair=True,
    #         context=None
    #     )
    #     portfolio.add_order(order_a)
    #
    #     order_a.set_pending()
    #     order_a.set_executed()
    #
    #     self.assertNotEqual(0.0, portfolio.realized)

    def test_unallocated_percentage(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()
        portfolio = portfolio_manager.get_portfolio()
        initial_unallocated = portfolio.unallocated

        self.assertEqual(0, portfolio.realized)

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )

        self.assertEqual(initial_unallocated, portfolio.unallocated)

        portfolio.add_order(order_a)

        self.assertNotEqual(initial_unallocated, portfolio.unallocated)

        order_a.set_pending()
        order_a.set_executed()

        self.assertNotEqual(initial_unallocated, portfolio.unallocated)

        sell_order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount_target_symbol=1,
            symbol=self.TARGET_SYMBOL_A,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            context=None
        )
        portfolio.add_order(sell_order_a)

        sell_order_a.set_pending()
        sell_order_a.set_executed()

        self.assertEqual(initial_unallocated, portfolio.unallocated)
