from investing_algorithm_framework.schemas import OrderSerializer
from investing_algorithm_framework import Order, OrderSide, db
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_A_PRICE

serialization_dict = {
    'id',
    'order_reference',
    'price',
    'identifier',
    'position_id',
    'amount',
    'amount_trading_symbol',
    'trading_symbol',
    'executed_at',
    'status',
    'target_symbol',
    'order_type',
    'order_side'
}


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()

        self.create_buy_order(
            10,
            SYMBOL_A,
            SYMBOL_A_PRICE,
            self.algo_app.algorithm.get_portfolio_manager()
        )

    def test(self):
        order = Order.query.first()
        serializer = OrderSerializer()
        data = serializer.dump(order)
        self.assertEqual(set(data), serialization_dict)
