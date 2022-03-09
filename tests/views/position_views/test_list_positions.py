import json

from investing_algorithm_framework import OrderSide, \
    OrderType, OrderStatus, Order
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import position_serialization_dict


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

        orders = [
            Order.from_dict(
                {
                    "reference_id": 2,
                    "target_symbol": self.TARGET_SYMBOL_A,
                    "trading_symbol": "usdt",
                    "amount_target_symbol": 4,
                    "price": self.get_price(self.TARGET_SYMBOL_A).price,
                    "status": OrderStatus.PENDING.value,
                    "side": OrderSide.BUY.value,
                    "type": OrderType.LIMIT.value
                }
            ),
            Order.from_dict(
                {
                    "reference_id": 3,
                    "target_symbol": self.TARGET_SYMBOL_B,
                    "trading_symbol": "usdt",
                    "amount_target_symbol": 4,
                    "price": self.get_price(self.TARGET_SYMBOL_A).price,
                    "status": OrderStatus.SUCCESS.value,
                    "initial_price": self.get_price(
                        self.TARGET_SYMBOL_A).price,
                    "side": OrderSide.BUY.value,
                    "type": OrderType.LIMIT.value
                }
            )
        ]

        self.algo_app.algorithm.add_orders(orders, identifier="default")

    def tearDown(self):
        self.algo_app.algorithm.stop()
        super(Test, self).tearDown()

    def test(self):
        query_params = {'identifier': "default"}
        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(3, len(data["items"]))
        self.assertEqual(
            position_serialization_dict, set(data.get("items")[0])
        )

    def test_list_orders_with_identifier_query_params(self):
        query_params = {
            'identifier': "default"
        }
        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(3, len(data["items"]))
        self.assertEqual(
            position_serialization_dict, set(data.get("items")[0])
        )

        query_params = {
            'identifier': "random"
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert404(response)
