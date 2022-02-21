from random import randrange
from abc import abstractmethod, ABC
from typing import List

from investing_algorithm_framework.configuration.constants import \
    TRADING_SYMBOL
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.market_identifier import \
    MarketIdentifier
from investing_algorithm_framework.core.models import OrderSide, OrderType, \
    Portfolio
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.order import Order


class PortfolioManager(ABC, Identifier, MarketIdentifier):
    trading_symbol = None

    @abstractmethod
    def get_unallocated(self, algorithm_context, sync=False) -> Position:
        pass

    @abstractmethod
    def get_positions(self, algorithm_context) -> List[Position]:
        pass

    @abstractmethod
    def get_orders(self, algorithm_context) -> List[Order]:
        pass

    def initialize(self, algorithm_context):
        pass

    def get_portfolio(self, algorithm_context) -> Portfolio:
        return Portfolio.of(
            positions=self.get_positions(algorithm_context),
            unallocated=self.get_unallocated(algorithm_context),
            orders=self.get_orders(algorithm_context)
        )

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

    def create_order(
        self,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_type=OrderType.LIMIT.value,
        order_side=OrderSide.BUY.value,
        algorithm_context=None
    ) -> Order:

        return Order(
            id=randrange(100000),
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol(algorithm_context),
            price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            order_type=order_type,
            order_side=order_side,
        )

    @abstractmethod
    def add_order(self, order):
        pass
