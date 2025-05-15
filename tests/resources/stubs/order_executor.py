from investing_algorithm_framework import Order
from investing_algorithm_framework.domain import OrderExecutor, OrderStatus
from tests.resources.utils import random_string


class OrderExecutorTest(OrderExecutor):
    """
    Test order executor for testing purposes.
    """

    def __init__(self):
        super().__init__()
        self.order_amount = None
        self.order_amount_filled = None
        self.order_status = None

    def execute_order(self, portfolio, order, market_credential) -> Order:
        order.external_id = random_string(10)
        order.status = OrderStatus.OPEN

        if self.order_amount is not None:
            order.amount = self.order_amount
            order.remaining = self.order_amount

        if self.order_amount_filled is not None:
            order.filled = self.order_amount_filled
            order.remaining = order.amount - self.order_amount_filled

        if self.order_status is not None:
            order.status = self.order_status

        return order

    def supports_market(self, market):
        return True

    def cancel_order(self, portfolio, order, market_credential) -> Order:
        order.status = OrderStatus.CANCELED
        return order
