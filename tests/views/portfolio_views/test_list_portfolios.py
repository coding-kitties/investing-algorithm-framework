import json

from investing_algorithm_framework import db, Portfolio
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin, \
    SYMBOL_A, SYMBOL_B, SYMBOL_A_PRICE, SYMBOL_B_PRICE
from tests.resources.serialization_dicts import portfolio_serialization_dict


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
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

    def test_list_orders(self):
        response = self.client.get("/api/portfolios")
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(Portfolio.query.count(), len(data["items"]))
        self.assertEqual(
            portfolio_serialization_dict, set(data.get("items")[0])
        )
