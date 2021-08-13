from investing_algorithm_framework.schemas import OrderSerializer
from investing_algorithm_framework import Order, OrderSide, db
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin

serialization_dict = {
    'id',
    'price',
    'broker',
    'position_id',
    'amount',
    'trading_symbol',
    'executed',
    'successful',
    'executed',
    'target_symbol',
    'order_type',
    'order_side'
}


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()

        for i in range(0, 10):
            order = Order(
                target_symbol="DOT",
                trading_symbol="USDT",
                price=10,
                amount=10 * i,
                order_side=OrderSide.BUY.value
            )

            order.save(db)

    def test(self):
        order = Order.query.first()
        serializer = OrderSerializer()
        data = serializer.dump(order)
        self.assertEqual(set(data), serialization_dict)
