from typing import Union

from investing_algorithm_framework import Position, Order, OrderStatus
from investing_algorithm_framework.domain import PortfolioProvider


class PortfolioProviderTest(PortfolioProvider):

    def __init__(self):
        super().__init__()
        self.status = OrderStatus.CLOSED.value
        self.external_balances = {
            "EUR": 1000,
        }
        self.order_amount = None
        self.order_amount_filled = None

    def get_order(
        self, portfolio, order, market_credential
    ) -> Union[Order, None]:

        if self.order_amount is not None:
            order.amount = self.order_amount

        if self.order_amount_filled is not None:
            order.filled = self.order_amount_filled
        else:
            order.filled = order.amount

        order.status = self.status
        order.remaining = 0
        return order

    def get_position(
        self, portfolio, symbol, market_credential
    ) -> Union[Position, None]:
        if symbol not in self.external_balances:
            position = Position(
                symbol=symbol,
                amount=1000,
                portfolio_id=portfolio.id
            )
        else:
            position = Position(
                symbol=symbol,
                amount=self.external_balances[symbol],
                portfolio_id=portfolio.id
            )
        return position

    def supports_market(self, market) -> bool:
        return True