from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import OrderStatus, OrderSide
from investing_algorithm_framework.core.models import db


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()

        self.start_algorithm()

        self.order = self.create_limit_order(
            self.algo_app.algorithm.get_portfolio_manager().get_portfolio(),
            self.TARGET_SYMBOL_A,
            amount=1,
            price=self.get_price(self.TARGET_SYMBOL_A).price,
            side=OrderSide.BUY,
        )

        self.order.status = OrderStatus.TO_BE_SENT.value
        db.session.commit()

        self.order.set_pending()

    def test(self) -> None:
        self.assertNotEqual(
            0, len(self.algo_app.algorithm.get_orders(
                "test", status=OrderStatus.PENDING
            ))
        )

        self.algo_app.algorithm.check_order_status("test")

        self.assertEqual(
            0, len(self.algo_app.algorithm.get_orders(
                "test", status=OrderStatus.PENDING
            ))
        )
