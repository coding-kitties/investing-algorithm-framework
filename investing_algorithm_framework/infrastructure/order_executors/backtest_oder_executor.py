from investing_algorithm_framework.domain import OrderExecutor, OrderStatus, \
    INDEX_DATETIME, Order


class BacktestOrderExecutor(OrderExecutor):
    """
    Backtest implementation of order executor. This executor is used to
    simulate order execution in a backtesting environment.

    !Important: This executor does not actually execute orders on any market.
        It should be used only for backtesting purposes.
    """

    def execute_order(self, portfolio, order, market_credential) -> Order:
        order.status = OrderStatus.OPEN.value
        order.remaining = order.get_amount()
        order.filled = 0
        order.updated_at = self.config[INDEX_DATETIME]
        return order

    def cancel_order(self, portfolio, order, market_credential) -> Order:
        order.status = OrderStatus.CANCELED.value
        order.remaining = 0
        order.updated_at = self.config[INDEX_DATETIME]
        return order

    def supports_market(self, market):
        return True
