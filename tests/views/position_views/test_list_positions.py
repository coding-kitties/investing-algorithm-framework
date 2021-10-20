import json
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_B, SYMBOL_B_PRICE, SYMBOL_A_PRICE
from tests.resources.serialization_dicts import position_serialization_dict
from investing_algorithm_framework import db, Position


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

        order = self.algo_app.algorithm.create_limit_buy_order(
            "test",
            SYMBOL_A,
            SYMBOL_A_PRICE,
            10,
            True
        )
        order.save(db)

        order = self.algo_app.algorithm.create_limit_buy_order(
            "test",
            SYMBOL_B,
            SYMBOL_B_PRICE,
            10,
            True
        )
        order.save(db)
        order.set_executed()

        self.algo_app.algorithm.create_limit_sell_order(
            "test",
            SYMBOL_B,
            SYMBOL_B_PRICE,
            10,
            True
        )
        order.save(db)

    def tearDown(self):
        self.algo_app.algorithm.stop()
        super(Test, self).tearDown()

    def test_list_orders(self):

        response = self.client.get("/api/positions")
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(Position.query.count(), len(data["items"]))
        self.assertEqual(position_serialization_dict, set(data.get("items")[0]))

    def test_list_orders_with_target_symbol_query_params(self):

        query_params = {
            'symbol': SYMBOL_B
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(
            Position.query.filter_by(symbol=SYMBOL_B).count(),
            len(data["items"])
        )
        self.assertEqual(
            position_serialization_dict, set(data.get("items")[0])
        )

    def test_list_orders_with_identifier_query_params(self):
        query_params = {
            'identifier': "test"
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(
            Position.query.count(),
            len(data["items"])
        )
        self.assertEqual(
            position_serialization_dict, set(data.get("items")[0])
        )

        query_params = {
            'identifier': "random"
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(0, len(data["items"]))
