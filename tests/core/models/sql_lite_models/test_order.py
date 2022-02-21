from datetime import datetime
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderSide, db, \
    OrderStatus, OrderType, SQLLiteOrder
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()

        self.start_algorithm()
        self.portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            self.portfolio_manager
        )

    def tearDown(self) -> None:
        super(TestOrderModel, self).tearDown()

    def test_creation_limit_order(self):
        self.assertEqual(1, SQLLiteOrder.query.count())

        order = SQLLiteOrder.query.first()

        self.assertIsNotNone(order.amount_trading_symbol)
        self.assertIsNotNone(order.amount_target_symbol)
        self.assertIsNotNone(order.initial_price)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNotNone(order.status)
        self.assertTrue(OrderStatus.TO_BE_SENT.equals(order.status))

    def test_creation_market_sell_order(self):
        self.create_limit_order(
            self.portfolio_manager.get_portfolio(),
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            side=OrderSide.BUY.value,
            executed=True,
        )

        self.create_market_sell_order(
            1, self.TARGET_SYMBOL_A, self.portfolio_manager
        )

        order = SQLLiteOrder.query\
            .filter_by(order_type=OrderType.MARKET.value)\
            .filter_by(order_side=OrderSide.SELL.value)\
            .first()

        self.assert_is_market_order(order)

        order.set_pending()
        order.set_executed(price=10, amount=1)

        order = SQLLiteOrder.query\
            .filter_by(order_type=OrderType.MARKET.value) \
            .filter_by(order_side=OrderSide.SELL.value) \
            .first()

        self.assert_is_market_order(order)

    def test_buy_set_executed(self):
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()
        order.set_pending()

        self.assertTrue(OrderStatus.PENDING.equals(order.status))

        order.set_executed()

        self.assertTrue(OrderStatus.SUCCESS.equals(order.status))

    def test_sell_order_set_executed(self):

        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        buy_orders = SQLLiteOrder.query\
            .filter_by(order_side=OrderSide.BUY.value)\
            .filter_by(target_symbol=self.TARGET_SYMBOL_A)\
            .all()

        for buy_order in buy_orders:
            buy_order.set_pending()
            buy_order.set_executed()

        self.create_sell_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            portfolio_manager
        )

        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_pending()

        self.assertTrue(OrderStatus.PENDING.equals(order.status))

        order.set_executed()

        self.assertTrue(OrderStatus.SUCCESS.equals(order.status))

    def test_deleting(self):
        for order in SQLLiteOrder.query.all():
            order.delete(db)

        self.assertEqual(0, SQLLiteOrder.query.count())

    def test_delta(self):
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()
        order.set_pending()

        self.assertEqual(0, order.delta)

        order.set_executed()

        self.assertEqual(0, order.delta)

        self.update_price(
            self.TARGET_SYMBOL_A,
            1.1 * self.get_price(
                self.TARGET_SYMBOL_A, date=datetime.utcnow()
            ).price,
            date=datetime.utcnow()
        )
        self.assertEqual(
            1.1 * self.BASE_SYMBOL_A_PRICE - self.BASE_SYMBOL_A_PRICE,
            order.delta
        )

    def test_percentage_realized(self):
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()
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

        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_pending()
        order.set_executed()

        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertNotEqual(0, order.percentage_realized)

    def test_percentage_position(self):
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()

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

        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.SELL.value).first()

        order.set_pending()
        order.set_executed()

        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.percentage_position)

    def test_current_value(self):
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()

        self.assertEqual(0, order.delta)

        order.set_pending()
        order.set_executed()

        old_value = order.current_value

        self.assertEqual(self.BASE_SYMBOL_A_PRICE, old_value)

        self.update_price(
            self.TARGET_SYMBOL_A, 1.1 * self.BASE_SYMBOL_A_PRICE,
            date=datetime.utcnow()
        )

        new_value = order.current_value

        self.assertEqual(1.1 * self.BASE_SYMBOL_A_PRICE, new_value)
        self.assertNotEqual(old_value, new_value)

    def test_split(self):
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()

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
        order = SQLLiteOrder.query.filter_by(order_side=OrderSide.BUY.value).first()

        with self.assertRaises(OperationalException) as e:
            _, _ = order.split(0.5)

    def test_cancel(self):
        portfolio = self.algo_app.algorithm \
            .get_portfolio_manager() \
            .get_portfolio()

        initial_unallocated = portfolio.unallocated

        order = self.create_limit_order(
            portfolio,
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            executed=False
        )

        self.assertNotEqual(initial_unallocated, portfolio.unallocated)

        order.set_pending()

        self.assertNotEqual(initial_unallocated, portfolio.unallocated)

        order.cancel()

        self.assertEqual(initial_unallocated, portfolio.unallocated)

    def test_get_id(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_id())

    def test_get_reference_id(self):
        order = SQLLiteOrder.query.first()
        order.reference_id = order.id
        self.assertIsNotNone(order.get_reference_id())

    def test_get_target_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_target_symbol())

    def test_get_trading_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_trading_symbol())

    def test_get_amount_of_trading_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_amount_trading_symbol())

    def test_get_amount_of_target_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_amount_target_symbol())

    def test_get_initial_price(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_initial_price())

    def test_get_price(self):
        order = SQLLiteOrder.query.first()
        order.price = 10
        self.assertIsNotNone(order.get_price())

    def test_get_closing_price(self):
        order = SQLLiteOrder.query.first()
        order.closing_price = 10
        self.assertIsNotNone(order.get_closing_price())

    def test_get_side(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_side())

    def test_get_status(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_status())

    def test_get_type(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_type())
