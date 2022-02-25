from investing_algorithm_framework.core.models import Order, OrderSide, \
    OrderType, OrderStatus, Position
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestPositionModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestPositionModel, self).setUp()
        self.position = Position(
            symbol=self.TARGET_SYMBOL_A,
            amount=10
        )

    def test_get_symbol(self):
        self.assertIsNotNone(self.position.get_symbol())

    def test_get_amount(self):
        self.assertIsNotNone(self.position.get_amount())

    def test_get_order(self):
        pass

    def test_get_orders(self):
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
            )
        ]
        self.position.add_orders(orders)
        self.assertIsNotNone(self.position.get_orders())

    def test_from_dict(self):
        position = Position.from_dict(
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
        position = Position.from_dict(
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

        orders = position.get_orders()
        self.assertNotEqual(0, len(orders))

        for order in orders:
            self.assertTrue(isinstance(order, Order))

    def test_to_dict(self):
        self.assertIsNotNone(self.position.to_dict())

    def test_add_orders(self):
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
                target_symbol=self.TARGET_SYMBOL_A,
                trading_symbol="USDT"
            )
        ]
        self.position.add_orders(orders)
        self.assertEqual(2, len(self.position.get_orders()))

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
                target_symbol=self.TARGET_SYMBOL_A,
                trading_symbol="USDT"
            )
        ]
        self.position.add_orders(orders)
        self.assertEqual(2, len(self.position.get_orders()))

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
                target_symbol=self.TARGET_SYMBOL_A,
                trading_symbol="USDT"
            )
        ]
        self.position.add_orders(orders)
        self.assertEqual(4, len(self.position.get_orders()))

    def test_add_order(self):
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
        self.position.add_order(order)
        self.assertEqual(1, len(self.position.get_orders()))

        order = Order(
            reference_id=2,
            status=OrderStatus.PENDING.value,
            type=OrderType.LIMIT.value,
            side=OrderSide.SELL.value,
            amount_trading_symbol=10,
            price=10,
            target_symbol=self.TARGET_SYMBOL_A,
            trading_symbol="USDT"
        )
        self.position.add_order(order)
        self.assertEqual(2, len(self.position.get_orders()))
