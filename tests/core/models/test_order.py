from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderSide, db, \
    OrderStatus, OrderType
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()

        self.start_algorithm()
        self.portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A).price,
            self.portfolio_manager
        )

    def tearDown(self) -> None:
        super(TestOrderModel, self).tearDown()

    def test_creation_limit_order(self):
        self.assertEqual(1, Order.query.count())

        order = Order.query.first()

        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertIsNotNone(order.amount_target_symbol)
        self.assertIsNotNone(order.initial_price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNotNone(order.status)
        self.assertTrue(OrderStatus.TO_BE_SENT.equals(order.status))

    def test_creation_market_buy_order(self):
        self.assertEqual(1, Order.query.count())

        self.create_market_buy_order(
            1, self.TARGET_SYMBOL_A, self.portfolio_manager
        )

        order = Order.query\
            .filter_by(order_type=OrderType.MARKET.value)\
            .first()

        self.assert_is_market_order(order)

    def test_creation_market_sell_order(self):
        self.create_market_buy_order(
            1, self.TARGET_SYMBOL_A, self.portfolio_manager
        )
        order = Order.query\
            .filter_by(order_type=OrderType.MARKET.value)\
            .first()
        order.set_pending()
        order.set_executed(price=1000, amount=1)

        self.create_market_sell_order(
            1, self.TARGET_SYMBOL_A, self.portfolio_manager
        )

        order = Order.query\
            .filter_by(order_type=OrderType.MARKET.value)\
            .filter_by(order_side=OrderSide.SELL.value)\
            .first()

        self.assert_is_market_order(order)

        order.set_pending()
        order.set_executed(price=10, amount=1)

        order = Order.query\
            .filter_by(order_type=OrderType.MARKET.value) \
            .filter_by(order_side=OrderSide.SELL.value) \
            .first()

        self.assert_is_market_order(order)

    def test_buy_set_executed(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()
        order.set_pending()

        self.assertTrue(OrderStatus.PENDING.equals(order.status))

        order.set_executed()

        self.assertTrue(OrderStatus.SUCCESS.equals(order.status))

    def test_sell_order_set_executed(self):

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        buy_orders = Order.query\
            .filter_by(order_side=OrderSide.BUY.value)\
            .filter_by(target_symbol=self.TARGET_SYMBOL_A)\
            .all()

        for buy_order in buy_orders:
            buy_order.set_pending()
            buy_order.set_executed()

        self.create_sell_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A).price,
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
        order.set_pending()

        self.assertEqual(0, order.delta)

        order.set_executed()

        self.assertEqual(0, order.delta)

        self.update_price(
            self.TARGET_SYMBOL_A,
            1.1 * self.get_price(self.TARGET_SYMBOL_A).price
        )
        self.assertEqual(
            1.1 * self.BASE_SYMBOL_A_PRICE - self.BASE_SYMBOL_A_PRICE,
            order.delta
        )

    def test_percentage_realized(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()
        order.set_pending()
        self.assertEqual(0, order.percentage_realized)

        order.set_executed()

        self.assertEqual(0, order.percentage_realized)

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_sell_order(
            1,
            self.TARGET_SYMBOL_A,
            1.1 * self.BASE_SYMBOL_A_PRICE,
            portfolio_manager
        )

        order = Order.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_pending()
        order.set_executed()

        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertNotEqual(0, order.percentage_realized)

    def test_percentage_position(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.percentage_position)

        order.set_pending()
        order.set_executed()

        self.assertNotEqual(0, order.percentage_position)

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_sell_order(
            1,
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE,
            portfolio_manager
        )

        order = Order.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_pending()
        order.set_executed()

        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.percentage_position)

    def test_current_value(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.delta)

        order.set_pending()
        order.set_executed()

        old_value = order.current_value

        self.assertEqual(self.BASE_SYMBOL_A_PRICE, old_value)

        self.update_price(self.TARGET_SYMBOL_A, 1.1 * self.BASE_SYMBOL_A_PRICE)

        new_value = order.current_value

        self.assertEqual(1.1 * self.BASE_SYMBOL_A_PRICE, new_value)
        self.assertNotEqual(old_value, new_value)

    def test_split(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        order.set_pending()
        order.set_executed()

        og, split_order = order.split(0.5)

        self.assertEqual(og.target_symbol, split_order.target_symbol)
        self.assertEqual(og.trading_symbol, split_order.trading_symbol)
        self.assertEqual(og.amount_target_symbol, 0.5)
        self.assertEqual(split_order.amount_target_symbol, 0.5)
        self.assertEqual(split_order.initial_price, self.BASE_SYMBOL_A_PRICE)
        self.assertEqual(og.initial_price, self.BASE_SYMBOL_A_PRICE)
        self.assertEqual(og.status, split_order.status)

    def test_split_without_executed(self):
        order = Order.query.filter_by(order_side=OrderSide.BUY.value).first()

        with self.assertRaises(OperationalException) as e:
            _, _ = order.split(0.5)
