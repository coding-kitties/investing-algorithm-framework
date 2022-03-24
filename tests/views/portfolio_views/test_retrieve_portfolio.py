import json

from investing_algorithm_framework.core.models import OrderSide, \
    Order, OrderStatus, OrderType
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import portfolio_serialization_dict


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
                    "status": OrderStatus.CLOSED.value,
                    "initial_price": self.get_price(
                        self.TARGET_SYMBOL_A).price,
                    "side": OrderSide.BUY.value,
                    "type": OrderType.LIMIT.value
                }
            )
        ]

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        portfolio.add_orders(orders)

    def test_retrieve(self):
        portfolio = self.algo_app.algorithm.get_portfolio()

        response = self.client.get(
            f"/api/portfolios/{portfolio.get_identifier()}"
        )
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(portfolio_serialization_dict, set(data.keys()))

    def test_retrieve_default(self):
        response = self.client.get(f"/api/portfolios/default")
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(portfolio_serialization_dict, set(data.keys()))
