from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderSide
from investing_algorithm_framework.core.models import OrderType
from tests.resources import SYMBOL_A, SYMBOL_A_PRICE
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

    def test_validate_limit_buy_order(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a)

    def test_validate_limit_sell_order(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a)

        order_a.set_executed()
        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a_sell)

    def test_validate_limit_sell_order_larger_then_position(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=1,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        portfolio_manager.add_order(order_a)

        order_a.set_executed()
        order_a_sell = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value,
            amount=2,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        with self.assertRaises(OperationalException) as exc:
            portfolio_manager.add_order(order_a_sell)

    def test_validate_limit_order_with_unallocated_error(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order_a = portfolio_manager.create_order(
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.BUY.value,
            amount=10000,
            symbol=SYMBOL_A,
            price=SYMBOL_A_PRICE,
            validate_pair=True,
            context=None
        )

        with self.assertRaises(OperationalException):
            portfolio_manager.add_order(order_a)
