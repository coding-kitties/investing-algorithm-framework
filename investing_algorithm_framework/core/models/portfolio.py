from abc import abstractmethod
from typing import List

from investing_algorithm_framework.core.models import OrderSide, \
    OrderStatus, OrderType
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.order import Order
from investing_algorithm_framework.core.exceptions import OperationalException


class Portfolio:

    def __init__(
        self,
        identifier,
        trading_symbol,
        positions,
        market=None,
        orders=None
    ):
        self.positions = positions
        self.trading_symbol = trading_symbol
        self.identifier = identifier
        self.market = market

        if positions is None:
            self.positions = []

        self.trading_symbol = self.trading_symbol.upper()
        self.initialize_positions()

    def initialize_positions(self):
        trading_symbol_position_found = False

        if self.positions is None:
            raise OperationalException(
                "Trading symbol position is not defined"
            )

        new_positions = []

        for position in self.positions:

            if isinstance(position, dict):
                position = Position.from_dict(position)
            elif not isinstance(position, Position):
                raise OperationalException("Wrong position data")

            new_positions.append(position)

        self.positions = new_positions

        for position in self.positions:

            if self.trading_symbol == position.get_symbol():
                trading_symbol_position_found = True

        if not trading_symbol_position_found:
            raise OperationalException(
                "No position provided with trading symbol amount"
            )

    def get_identifier(self):
        return self.identifier

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_position(self, symbol) -> Position:

        for position in self.positions:

            if position.get_symbol() == symbol:
                return position

        return None

    def get_positions(self) -> List[Position]:
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
        positions = self.positions

        orders = []

        for position in positions:
            orders.append(position.get_orders())

        return orders

    def get_number_of_orders(self):
        return len(self.orders)

    def get_market(self) -> str:
        return self.market

    @staticmethod
    def from_dict(data):

        if data is None:
            return None

        return Portfolio(
            identifier=data.get("identifier", None),
            trading_symbol=data.get("trading_symbol", None),
            market=data.get("market", None),
            positions=data.get("positions", None),
            orders=data.get("orders", None)
        )

    def get_unallocated(self) -> Position:

        if self.positions is None:
            raise OperationalException(
                "Trading symbol position is not specified"
            )

        for position in self.positions:

            if position.get_symbol() == self.get_trading_symbol():
                return position

        raise OperationalException(
            "Trading symbol position is not specified"
        )

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

    def create_order(
        self,
        algorithm_context,
        type,
        status,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        side=OrderSide.BUY,
    ) -> Order:
        return Order(
            type=OrderType.LIMIT,
            side=OrderSide.BUY,
            initial_price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            status=OrderStatus.TO_BE_SENT,
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol()
        )

    def add_position(self, position):

        if not isinstance(position, Position):
            raise OperationalException("Object is not a position")

        self.positions.append(position)

    def add_positions(self, positions):
        self.positions = positions

    def add_order(self, order):
        pass

    def add_orders(self, orders):

        for order in orders:
            position = next(
                (position for position in self.positions
                 if position.get_symbol() == order.get_target_symbol()), None
            )

            if position is None:
                position = Position(symbol=order.get_target_symbol())
                position.add_order(order)
            else:
                position = self.get_position(order.get_target_symbol())
                position.add_order(order)

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

    def to_dict(self):
        data = {
            "identifier": self.get_identifier(),
            "trading_symbol": self.get_trading_symbol(),
            "market": self.get_market(),
            "positions": self.get_positions(),
            "orders": self.get_orders()
        }

        if self.get_unallocated() is not None:
            data["unallocated"] = self.get_unallocated().get_amount()

        return data

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
