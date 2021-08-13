from abc import ABC, abstractmethod
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderSide, OrderType


class OrderValidator(ABC):

    def validate(self, order, portfolio):

        if OrderSide.BUY.equals(order.order_side):
            self.validate_buy_order(order, portfolio)
        else:
            self.validate_sell_order(order, portfolio)

        if OrderType.LIMIT.equals(order.order_type):
            self.validate_limit_order(order, portfolio)
        else:
            self.validate_market_order(order, portfolio)

        self._validate_order(order, portfolio)

    def validate_sell_order(self, order, portfolio):

        position = portfolio.positions\
            .filter_by(portfolio=portfolio)\
            .filter_by(symbol=order.trading_symbol)\
            .first()

        if position is None:
            raise OperationalException(
                "Can't add sell order to non existing position"
            )

        if position.amount < order.amount:
            raise OperationalException(
                "Order amount is larger then amount of open position"
            )

        if not order.target_symbol == portfolio.trading_currency:
            raise OperationalException(
                f"Can't add sell order with target "
                f"symbol {order.target_symbol} to "
                f"portfolio with trading currency {portfolio.trading_currency}"
            )

    @staticmethod
    def validate_buy_order(order, portfolio):

        if not order.trading_symbol == portfolio.trading_currency:
            raise OperationalException(
                f"Can't add buy order with trading "
                f"symbol {order.trading_symbol} to "
                f"portfolio with trading currency {portfolio.trading_currency}"
            )

    @staticmethod
    def validate_limit_order(order, portfolio):

        total_price = order.amount * order.price

        if float(portfolio.unallocated) < total_price:
            raise OperationalException(
                f"Order total: {total_price} {portfolio.trading_currency}, is "
                f"larger then unallocated size: {portfolio.unallocated} "
                f"{portfolio.trading_currency} of the portfolio"
            )

    @staticmethod
    def validate_market_order(order, _):

        if order.amount is None:
            raise OperationalException("Market order needs an amount")

    @abstractmethod
    def _validate_order(self, order, portfolio):
        pass
