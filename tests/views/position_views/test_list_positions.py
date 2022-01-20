import json
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import position_serialization_dict
from investing_algorithm_framework import db, SQLLitePosition


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

        order = self.algo_app.algorithm.create_limit_buy_order(
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A).price,
            10,
            True
        )
        order.save(db)

        order = self.algo_app.algorithm.create_limit_buy_order(
            self.TARGET_SYMBOL_B,
            self.get_price(self.TARGET_SYMBOL_B).price,
            10,
            True
        )
        order.save(db)
        order.set_executed()

        self.algo_app.algorithm.create_limit_sell_order(
            self.TARGET_SYMBOL_B,
            self.get_price(self.TARGET_SYMBOL_B).price,
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

        self.assertEqual(SQLLitePosition.query.count(), len(data["items"]))
        self.assertEqual(position_serialization_dict, set(data.get("items")[0]))

    def test_list_orders_with_target_symbol_query_params(self):

        query_params = {
            'symbol': self.TARGET_SYMBOL_B
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(
            SQLLitePosition.query.filter_by(symbol=self.TARGET_SYMBOL_B).count(),
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
            SQLLitePosition.query.count(),
            len(data["items"])
        )
        self.assertEqual(
            position_serialization_dict, set(data.get("items")[0])
        )

        query_params = {
            'identifier': "random"
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert404(response)
