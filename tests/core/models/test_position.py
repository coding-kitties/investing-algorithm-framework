from datetime import datetime
from investing_algorithm_framework.core.models import Order, OrderSide, \
    OrderType, OrderStatus, Position
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestPositionModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestPositionModel, self).setUp()
        self.algo_app.algorithm.start()

    def test_get_symbol(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position("usdt")
        self.assertIsNotNone(position.get_symbol())

    def test_get_amount(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertIsNotNone(position.get_amount())
        self.assertNotEqual(0, position.get_amount())

    def test_get_orders(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")

        self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            portfolio_manager,
            10
        )

        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertEqual(2, len(position.get_orders()))
        self.assertEqual(
            1, len(position.get_orders(status=OrderStatus.SUCCESS))
        )
        self.assertEqual(
            1, len(position.get_orders(status=OrderStatus.PENDING))
        )
        self.assertEqual(
            1, len(position.get_orders(status=OrderStatus.TO_BE_SENT))
        )
        self.assertEqual(
            1, len(position.get_orders(side=OrderSide.SELL))
        )
        self.assertEqual(
            1, len(position.get_orders(type=OrderType.MARKET))
        )
        self.assertEqual(
            1, len(position.get_orders(
                status=OrderStatus.TO_BE_SENT,
                type=OrderType.LIMIT,
                side=OrderSide.BUY
            ))
        )

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
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)
        self.assertIsNotNone(position.to_dict())

    def test_add_orders(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)

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
        position.add_orders(orders)
        self.assertEqual(3, len(position.get_orders()))

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
        position.add_orders(orders)
        self.assertEqual(3, len(position.get_orders()))

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
        position.add_orders(orders)
        self.assertEqual(5, len(position.get_orders()))

    def test_add_order(self):
        portfolio_manager = self.algo_app.algorithm \
            .get_portfolio_manager("default")
        portfolio = portfolio_manager.get_portfolio(algorithm_context=None)
        position = portfolio.get_position(self.TARGET_SYMBOL_A)

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
        self.assertEqual(2, len(position.get_orders()))

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
        position.add_order(order)
        self.assertEqual(3, len(position.get_orders()))
