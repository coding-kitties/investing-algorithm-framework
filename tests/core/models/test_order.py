from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderSide, db, \
    OrderStatus
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_A_BASE_PRICE, SYMBOL_A_PRICE, \
    set_symbol_a_price


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()

        self.start_algorithm()
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_buy_order(
            1,
            SYMBOL_A,
            SYMBOL_A_PRICE,
            portfolio_manager
        )

    def tearDown(self) -> None:
        set_symbol_a_price(SYMBOL_A_BASE_PRICE)
        super(TestOrderModel, self).tearDown()

    def test_creation(self):
        self.assertEqual(1, Order.query.count())

        order = Order.query.first()

        self.assertIsNotNone(order.amount)
        self.assertIsNotNone(order.price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNotNone(order.status)

    def test_buy_set_executed(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertFalse(OrderStatus.SUCCESS.equals(order.status))

        order.set_executed()

        self.assertTrue(OrderStatus.SUCCESS.equals(order.status))

    def test_sell_order_set_executed(self):

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        buy_orders = Order.query\
            .filter_by(order_side=OrderSide.BUY.value)\
            .filter_by(target_symbol=SYMBOL_A)\
            .all()

        for buy_order in buy_orders:
            buy_order.set_executed()

        self.create_sell_order(
            1,
            SYMBOL_A,
            SYMBOL_A_PRICE,
            portfolio_manager
        )
        order = Order.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_pending()

        self.assertTrue(OrderStatus.PENDING.equals(order.status))

        order.set_executed()

        self.assertTrue(OrderStatus.SUCCESS.equals(order.status))

    def test_deleting(self):
        for order in Order.query.all():
            order.delete(db)

        self.assertEqual(0, Order.query.count())

    def test_delta(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.delta)

        order.set_executed()

        self.assertEqual(0, order.delta)

        set_symbol_a_price(1.1 * SYMBOL_A_BASE_PRICE)

        self.assertEqual(
            1.1 * SYMBOL_A_BASE_PRICE - SYMBOL_A_BASE_PRICE, order.delta
        )

    def test_percentage_realized(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.percentage_realized)

        order.set_executed()

        self.assertEqual(0, order.percentage_realized)

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_sell_order(
            1,
            SYMBOL_A,
            1.1 * SYMBOL_A_BASE_PRICE,
            portfolio_manager
        )

        order = Order.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_executed()

        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertNotEqual(0, order.percentage_realized)

    def test_percentage_position(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.percentage_position)

        order.set_executed()

        self.assertNotEqual(0, order.percentage_position)

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_sell_order(
            1,
            SYMBOL_A,
            SYMBOL_A_BASE_PRICE,
            portfolio_manager
        )

        order = Order.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_executed()

        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.percentage_position)

    def test_current_value(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.delta)

        order.set_executed()

        old_value = order.current_value

        self.assertEqual(SYMBOL_A_BASE_PRICE, old_value)

        set_symbol_a_price(1.1 * SYMBOL_A_PRICE)

        new_value = order.current_value

        self.assertEqual(1.1 * SYMBOL_A_PRICE, new_value)
        self.assertNotEqual(old_value, new_value)

    def test_split(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        order.set_executed()

        og, split_order = order.split(0.5)

        self.assertEqual(og.target_symbol, split_order.target_symbol)
        self.assertEqual(og.trading_symbol, split_order.trading_symbol)
        self.assertEqual(og.amount, 0.5)
        self.assertEqual(split_order.amount, 0.5)
        self.assertEqual(split_order.price, SYMBOL_A_BASE_PRICE)
        self.assertEqual(og.price, SYMBOL_A_BASE_PRICE)
        self.assertEqual(og.status, split_order.status)

    def test_split_without_executed(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        with self.assertRaises(OperationalException) as e:
            _, _ = order.split(0.5)
