from datetime import datetime

from investing_algorithm_framework.core.models import SQLLitePosition, \
    SQLLiteOrder
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestPosition(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestPosition, self).setUp()
        self.start_algorithm()

    def test_get_symbol(self):
        portfolio_manager = self.algo_app.algorithm\
            .get_portfolio_manager("sqlite")
        positions = portfolio_manager.get_positions(algorithm_context=None)
        self.assertIsNotNone(positions[0].get_symbol())

    def test_get_amount(self):
        portfolio_manager = self.algo_app.algorithm\
            .get_portfolio_manager("sqlite")
        positions = portfolio_manager.get_positions(algorithm_context=None)
        self.assertIsNotNone(positions[0].get_amount())
        self.assertNotEqual(0, positions[0].get_amount())

    def test_get_orders(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")

        self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            portfolio_manager
        )

        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")

        positions = portfolio_manager.get_positions(algorithm_context=None)

        print(positions)
        self.assertEqual(
            1, len(positions[0].get_orders())
        )
        orders = positions[0].get_orders()
        self.assertTrue(isinstance(orders[0], SQLLiteOrder))

    def test_from_dict(self):
        position = SQLLitePosition.from_dict(
            {
                "symbol": "DOT",
                "amount": 40,
                "price": 10,
            }
        )

        self.assertIsNotNone(position.get_price())
        self.assertIsNotNone(position.get_symbol())
        self.assertIsNotNone(position.get_amount())

    def test_from_dict_with_orders(self):
        position = SQLLitePosition.from_dict(
            {
                "symbol": "DOT",
                "amount": 40,
                "price": 10,
                "orders": [
                    {
                        "target_symbol": "DOT",
                        "trading_symbol": "USDT",
                        "amount_target_symbol": 40,
                        "status": "PENDING",
                        "price": 10,
                        "side": "BUY",
                        "type": "LIMIT"
                    }
                ]
            }
        )

        self.assertIsNotNone(position.get_price())
        self.assertIsNotNone(position.get_symbol())
        self.assertIsNotNone(position.get_amount())
        self.assertIsNotNone(position.get_orders())
        self.assertEqual(1, SQLLiteOrder.query.count())

        orders = position.get_orders()

        for order in orders:
            self.assertTrue(isinstance(order, SQLLiteOrder))

    def test_to_dict(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")
        positions = portfolio_manager.get_positions(algorithm_context=None)
        self.assertIsNotNone(positions[0].get_symbol())
        data = positions[0].to_dict()
        self.assertTrue(isinstance(data, dict))

    def test_add_orders(self):
        pass

    def test_add_order(self):
        pass
