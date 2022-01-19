from investing_algorithm_framework import OrderSide, OrderType
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework.core.models import db, Portfolio


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def tearDown(self) -> None:
        Portfolio.query.delete()
        db.session.commit()
        super(Test, self).tearDown()

    def test(self) -> None:
        order = self.algo_app.algorithm\
            .create_market_sell_order(
                identifier="test",
                symbol=self.TARGET_SYMBOL_A,
                amount_target_symbol=10
            )

        self.assertIsNone(order.amount_trading_symbol)
        self.assertEqual(order.target_symbol, self.TARGET_SYMBOL_A)
        self.assertIsNotNone(order.target_symbol)
        self.assertIsNotNone(order.trading_symbol)
        self.assertIsNotNone(order.order_side)
        self.assertIsNone(order.status)
        self.assertTrue(OrderSide.SELL.equals(order.order_side))
        self.assertTrue(OrderType.MARKET.equals(order.order_type))

    def test_with_execution(self) -> None:
        self.create_limit_order(
            self.algo_app.algorithm.get_portfolio_manager().get_portfolio(),
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            side=OrderSide.BUY.value,
            executed=True,
        )

        sell_order = self.algo_app.algorithm.create_market_sell_order(
            symbol=self.TARGET_SYMBOL_A,
            amount_target_symbol=1,
            execute=True
        )

        self.assertEqual(sell_order.amount_target_symbol, 1)
        self.assertEqual(sell_order.position.amount, 1)
        self.assertEqual(sell_order.amount_target_symbol, 1)
        self.assertIsNone(sell_order.amount_trading_symbol)

        self.assert_is_market_order(sell_order)

        sell_order.set_executed(
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            amount=self.get_price(self.TARGET_SYMBOL_A).price
        )

        self.assertEqual(sell_order.amount_target_symbol, 1)
        self.assertEqual(sell_order.position.amount, 0)
        self.assertEqual(sell_order.amount_target_symbol, 1)
        self.assertEqual(
            sell_order.amount_trading_symbol,
            self.get_price(self.TARGET_SYMBOL_A).price
        )
