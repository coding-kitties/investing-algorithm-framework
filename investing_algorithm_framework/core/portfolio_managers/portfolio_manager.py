from datetime import datetime, timedelta
from abc import abstractmethod, ABC
from typing import List

from investing_algorithm_framework.configuration.constants import \
    TRADING_SYMBOL
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.models import OrderSide, OrderType, \
    Portfolio
from investing_algorithm_framework.core.models.order import Order, OrderStatus
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.order_validators import \
    OrderValidatorFactory


class PortfolioManager(ABC, Identifier):
    trading_symbol = None
    portfolio = None
    last_updated = None
    update_minutes = 5

    @abstractmethod
    def get_positions(self, algorithm_context, **kwargs) -> List[Position]:
        pass

    @abstractmethod
    def get_orders(
        self, symbol, algorithm_context, **kwargs
    ) -> List[Order]:
        pass

    @abstractmethod
    def get_prices(
        self, symbols, algorithm_context, **kwargs
    ) -> float:
        pass

    def initialize(self, algorithm_context):
        self.portfolio = self.get_portfolio(algorithm_context)

    def get_trading_symbol(self, algorithm_context) -> str:
        trading_symbol = getattr(self, "trading_symbol", None)

        if trading_symbol is None:
            trading_symbol = algorithm_context.config.get(TRADING_SYMBOL, None)

        if trading_symbol is None:
            raise OperationalException(
                "Trading symbol is not set. Either override "
                "'get_trading_symbol' method or set "
                "the 'trading_symbol' attribute in the algorithm config."
            )

        return trading_symbol

    def sync_portfolio(self, algorithm_context):
        positions = self.get_positions(algorithm_context)
        self.portfolio.add_positions(positions)
        positions = self.portfolio.get_positions()

        for position in positions:
            price = self.get_prices(
                position.get_symbol(),
                algorithm_context
            )
            position.set_price(price)
            orders = self.get_orders(
                symbol=f"f{position.get_symbol()}/{self.get_trading_symbol(algorithm_context)}",
                algorithm_context=algorithm_context
            )
            self.portfolio.add_orders(orders)

    def get_portfolio(
        self,
        algorithm_context,
        update=False,
        execute_update=True,
        **kwargs
    ) -> Portfolio:

        if execute_update and (self._requires_update() or update):
            self.sync_portfolio(algorithm_context)

        return self.portfolio

    def _requires_update(self):
        update_time = datetime.utcnow() \
                      + timedelta(minutes=-self.update_minutes)
        return self.last_updated is None or update_time > self.last_updated

    def create_order(
        self,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        type=OrderType.LIMIT.value,
        side=OrderSide.BUY.value,
        algorithm_context=None
    ) -> Order:
        order = Order(
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol(algorithm_context),
            price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            type=type,
            side=side,
            status=OrderStatus.TO_BE_SENT.value
        )

        # Validate the order
        order_validator = OrderValidatorFactory.of(self.identifier)
        order_validator.validate(
            order, self.get_portfolio(algorithm_context=algorithm_context)
        )

        return order

    def add_order(self, order, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_order(order)

    def add_orders(self, orders, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_orders(orders)

    def add_position(self, position, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_position(position)

    def add_positions(self, positions, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_positions(positions)
