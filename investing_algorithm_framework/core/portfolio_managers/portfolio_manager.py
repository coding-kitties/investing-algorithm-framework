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
    def get_orders(self, algorithm_context, **kwargs) -> List[Order]:
        pass

    @abstractmethod
    def get_price(
        self, target_symbol, trading_symbol, algorithm_context, **kwargs
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

    def get_portfolio(self, algorithm_context, **kwargs) -> Portfolio:

        if self.portfolio is None:
            self.portfolio = Portfolio(
                identifier=self.get_identifier(),
                trading_symbol=self.get_trading_symbol(algorithm_context),
                positions=self.get_positions(algorithm_context),
                orders=self.get_orders(algorithm_context)
            )

        if self._requires_update():
            orders = self.get_orders(algorithm_context)
            positions = self.get_positions(algorithm_context)
            self.portfolio.add_positions(positions)
            self.portfolio.add_orders(orders)

            for position in self.portfolio.get_positions():
                position.set_price(
                    self.get_price(
                        position.get_symbol(),
                        self.get_trading_symbol(algorithm_context),
                        algorithm_context
                    )
                )

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
        portfolio = self.get_portfolio(algorithm_context=algorithm_context)
        unallocated = portfolio.get_unallocated()

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

        if OrderSide.BUY.equals(order.get_side()) and OrderType.LIMIT.equals(order.type):
            total = order.get_amount_target_symbol() * order.get_price()

            if total > unallocated.get_amount():
                raise OperationalException(
                    f"Order amount {total} {unallocated.get_symbol()} is "
                    f"larger then unallocated "
                    f"position {unallocated.get_amount()} "
                    f"{unallocated.get_symbol()}"
                )
        elif OrderSide.SELL.equals(order.get_side()):
            portfolio = self.get_portfolio(algorithm_context)
            position = portfolio.get_position(order.get_target_symbol())

            if position is None:
                raise OperationalException(
                    f"Can't create sell order for non existing position"
                )

            if position.get_amount() < order.get_amount_target_symbol():
                raise OperationalException(
                    f"Sell amount {order.get_amount_target_symbol()} "
                    f"{order.get_target_symbol()} is "
                    f"larger then position {position.get_amount()} "
                    f"{position.get_symbol()}"
                )

        # Validate the order
        order_validator = OrderValidatorFactory.of(self.identifier)
        order_validator.validate(order, self)

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

    def update_order_status(self, order, status, algorithm_context):
        order.set_status(OrderStatus.from_value(status))
        portfolio = self.get_portfolio(algorithm_context)
        # self.snapshot_portfolio(portfolio)

    # def snapshot_portfolio(
    #     self, portfolio, creation_datetime=None, withdrawel=0, deposit=0
    # ):
    #     PortfolioSnapshot.from_portfolio(
    #         portfolio, creation_datetime, withdrawel, deposit
    #     )
