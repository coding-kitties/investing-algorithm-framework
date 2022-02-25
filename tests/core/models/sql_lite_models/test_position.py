from datetime import datetime

from investing_algorithm_framework.core.models import SQLLitePosition, \
    SQLLiteOrder, Order, OrderStatus, OrderType, OrderSide
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

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)

        self.assertEqual(
            1, len(position.get_orders())
        )
        orders = position.get_orders()
        self.assertTrue(isinstance(orders[0], SQLLiteOrder))

    def test_get_order(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")

        self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            portfolio_manager,
            reference_id=1
        )

        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)

        self.assertEqual(1, len(position.get_orders()))
        order = position.get_order(reference_id=1)
        self.assertTrue(isinstance(order, SQLLiteOrder))

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
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")

        positions = portfolio_manager.get_positions(algorithm_context=None)
        position = positions[0]

        orders = [
            Order(
                reference_id=1,
                status=OrderStatus.PENDING.value,
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_trading_symbol=10,
                price=10,
                target_symbol=self.TARGET_SYMBOL_A,
                trading_symbol="USDT"
            ),
            Order(
                reference_id=2,
                status=OrderStatus.PENDING.value,
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_trading_symbol=10,
                price=10,
                target_symbol=self.TARGET_SYMBOL_B,
                trading_symbol="USDT"
            )
        ]
        position.add_orders(orders)
        self.assertEqual(2, len(position.get_orders()))

        orders = [
            Order(
                reference_id=1,
                status=OrderStatus.PENDING.value,
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_trading_symbol=10,
                price=10,
                target_symbol=self.TARGET_SYMBOL_A,
                trading_symbol="USDT"
            ),
            Order(
                reference_id=2,
                status=OrderStatus.PENDING.value,
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_trading_symbol=10,
                price=10,
                target_symbol=self.TARGET_SYMBOL_B,
                trading_symbol="USDT"
            )
        ]
        position.add_orders(orders)
        self.assertEqual(2, len(position.get_orders()))

        orders = [
            Order(
                reference_id=3,
                status=OrderStatus.PENDING.value,
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_trading_symbol=10,
                price=10,
                target_symbol=self.TARGET_SYMBOL_A,
                trading_symbol="USDT"
            ),
            Order(
                reference_id=4,
                status=OrderStatus.PENDING.value,
                type=OrderType.LIMIT.value,
                side=OrderSide.SELL.value,
                amount_trading_symbol=10,
                price=10,
                target_symbol=self.TARGET_SYMBOL_B,
                trading_symbol="USDT"
            )
        ]
        position.add_orders(orders)
        self.assertEqual(4, len(position.get_orders()))

    def test_add_order(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("sqlite")

        positions = portfolio_manager.get_positions(algorithm_context=None)
        position = positions[0]

        order = Order(
            reference_id=1,
            status=OrderStatus.PENDING.value,
            type=OrderType.LIMIT.value,
            side=OrderSide.SELL.value,
            amount_trading_symbol=10,
            price=10,
            target_symbol=self.TARGET_SYMBOL_A,
            trading_symbol="USDT"
        )
        position.add_order(order)
        self.assertEqual(1, len(position.get_orders()))

        order = Order(
            reference_id=2,
            status=OrderStatus.PENDING.value,
            type=OrderType.LIMIT.value,
            side=OrderSide.SELL.value,
            amount_trading_symbol=10,
            price=10,
            target_symbol=self.TARGET_SYMBOL_B,
            trading_symbol="USDT"
        )
        position.add_order(order)
        self.assertEqual(2, len(position.get_orders()))
