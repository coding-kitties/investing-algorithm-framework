import json

from investing_algorithm_framework import OrderSide, OrderStatus, \
    Order, OrderType
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import order_serialization_dict


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")

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

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        portfolio.add_orders(orders)

    def test_list_orders(self):
        query_params = {'identifier': "default"}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(2, len(data["items"]))
        self.assertEqual(order_serialization_dict, set(data.get("items")[0]))

    def test_list_orders_with_position(self):
        query_params = {
            'target_symbol': self.TARGET_SYMBOL_B,
            'identifier': "default"
        }
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(1, len(data["items"]))

    def test_list_orders_with_identifier(self):
        query_params = {'identifier': "default"}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(2, len(data["items"]))

        query_params = {'identifier': "sqlite"}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(0, len(data["items"]))

    def test_list_orders_with_target_symbol_query_params(self):
        query_params = {
            'identifier': "default", 'target_symbol': self.TARGET_SYMBOL_A
        }
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(1, len(data["items"]))

    def test_list_orders_with_status_query_params(self):
        query_params = {
            'identifier': "default",
            'status': OrderStatus.SUCCESS.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(1, len(data["items"]))

        query_params = {
            'identifier': "default",
            'status': OrderStatus.PENDING.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(1, len(data["items"]))

        query_params = {
            'identifier': "default",
            'status': OrderStatus.CLOSED.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(0, len(data["items"]))

    def test_list_orders_with_order_side_query_params(self):
        query_params = {
            'identifier': "default",
            'side': OrderSide.BUY.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(2, len(data["items"]))

        query_params = {
            'identifier': "default",
            'side': OrderSide.SELL.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(0, len(data["items"]))