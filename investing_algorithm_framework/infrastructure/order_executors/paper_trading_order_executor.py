from logging import getLogger

from investing_algorithm_framework.domain import OrderExecutor, \
    OrderStatus, Order, OperationalException, random_string

logger = getLogger("investing_algorithm_framework")


class PaperTradingOrderExecutor(OrderExecutor):
    """
    Broker-agnostic paper-trading executor (see
    ``PaperTradingMode.LOCAL``/``AUTO`` fallback). No network calls are
    ever made — every order is filled immediately at ``order.price``
    (already resolved by the time an order reaches an executor, for
    both LIMIT and MARKET orders — see ``Context.create_market_order``)
    for the full requested amount.

    Scoped to the specific market(s) it was registered for so it never
    shadows a real ``OrderExecutor`` for a live-traded market in the
    same app.
    """

    def __init__(self, markets, priority=0):
        super().__init__(priority=priority)
        self._markets = {market.upper() for market in markets}

    def supports_market(self, market) -> bool:
        return market.upper() in self._markets

    def execute_order(self, portfolio, order, market_credential) -> Order:
        try:
            order.external_id = f"paper-{random_string(16)}"
            order.filled = order.amount
            order.remaining = 0
            order.status = OrderStatus.CLOSED.value
            return order
        except Exception as e:
            logger.exception(e)
            order.status = OrderStatus.REJECTED.value
            return order

    def cancel_order(self, portfolio, order, market_credential) -> Order:
        if OrderStatus.CLOSED.equals(order.status):
            raise OperationalException(
                "Cannot cancel a paper order that has already filled"
            )

        order.status = OrderStatus.CANCELED.value
        return order
