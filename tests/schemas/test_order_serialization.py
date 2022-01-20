from investing_algorithm_framework import SQLLiteOrder
from investing_algorithm_framework.schemas import OrderSerializer
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import order_serialization_dict


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()

        self.start_algorithm()
        self.create_buy_order(
            10,
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE,
            self.algo_app.algorithm.get_portfolio_manager()
        )

    def test(self):
        order = SQLLiteOrder.query.first()
        serializer = OrderSerializer()
        data = serializer.dump(order)
        self.assertEqual(set(data), order_serialization_dict)
