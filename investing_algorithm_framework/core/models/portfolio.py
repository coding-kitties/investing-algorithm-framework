from abc import abstractmethod
from typing import List

from investing_algorithm_framework.core.models import OrderSide, \
    OrderStatus
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.order import Order
from investing_algorithm_framework.core.exceptions import OperationalException


class Portfolio:

    def __init__(
        self,
        identifier,
        unallocated_position,
        trading_symbol,
        positions=None,
        market=None,
        orders=None
    ):
        self.unallocated_position = unallocated_position
        self.positions = positions
        self.trading_symbol = trading_symbol
        self.identifier = identifier
        self.orders = orders
        self.market = market

        if positions is None:
            self.positions = []

        if orders is None:
            self.orders = []

    def get_identifier(self):
        return self.identifier

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_positions(self, symbol: str = None) -> List[Position]:
        return self.positions

    @abstractmethod
    def get_number_of_positions(self):
        return len(self.positions)

    def get_orders(
        self,
        status: OrderStatus = None,
        side: OrderSide = None,
        target_symbol: str = None,
        trading_symbol: str = None,
        lazy: bool = False
    ) -> List[Order]:
        return self.orders

    def get_number_of_orders(self):
        return len(self.orders)

    def get_market(self) -> str:
        return self.market

    @staticmethod
    def from_dict(data):
        pass

    def to_dict(self):
        pass

    def get_unallocated(self) -> Position:

        if self.unallocated_position is None:
            raise OperationalException(
                "Trading symbol position is not specified"
            )

        return self.unallocated_position

    def get_allocated(self):
        allocated = 0

        for position in self.positions:
            price = position.get_price()

            if price is not None:
                allocated += position.get_amount() * price

        return allocated

    def get_realized(self):
        realized = 0

        for order in self.orders:
            if OrderStatus.CLOSED.equals(order.get_status()):

                realized += order.get_closing_price() \
                           * order.get_amount_target_symbol()
        return realized

    @abstractmethod
    def get_total_revenue(self):
        revenue = 0

        for order in self.orders:
            if OrderStatus.CLOSED.equals(order.get_status()):
                revenue += order.get_closing_price() \
                            * order.get_amount_target_symbol()
        return revenue

    @abstractmethod
    def snapshot(
        self, withdrawel=0, deposit=0, commit=True, creation_datetime=None
    ):
        pass

    def create_order(
        self,
        context,
        order_type,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_side=OrderSide.BUY.value,
    ) -> Order:
        return Order(
            id=None,
            order_type=order_type,
            order_side=order_side,
            initial_price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            status=OrderStatus.TO_BE_SENT,
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol()
        )

    def repr(self, **fields) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():
            field_strings.append(f'{key}={field!r}')
            at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"

    def to_string(self):
        return self.repr(
            identifier=self.get_identifier(),
            trading_symbol=self.get_trading_symbol(),
            number_of_positions=self.get_number_of_positions(),
            number_of_orders=self.get_number_of_orders(),
            unallocated=f"{self.get_unallocated()}",
            allocated=self.get_allocated(),
            realized=f"{self.get_realized()}",
            total_revenue=f"{self.get_total_revenue()}",
        )

    def __repr__(self):
        return self.to_string()
