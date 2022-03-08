from abc import abstractmethod
from typing import List

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderStatus
from investing_algorithm_framework.core.models.order import Order, OrderSide
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.order_validators import \
    OrderValidatorFactory


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
        self.positions = []
        self.trading_symbol = self.trading_symbol.upper()
        self.add_positions(positions)
        self.validate_trading_symbol_position()
        self.add_orders(orders)

    def validate_trading_symbol_position(self):
        trading_symbol_position_found = False

        if self.positions is None:
            raise OperationalException(
                "No position provided with trading symbol amount"
            )

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
        symbol = symbol.upper()

        for position in self.get_positions():

            if position.get_symbol() == symbol:
                return position

        return None

    def get_positions(self, **kwargs) -> List[Position]:
        return self.positions

    @abstractmethod
    def get_number_of_positions(self):
        return len(self.positions)

    def get_order(self, reference_id):
        all_orders = []
        positions = self.get_positions()

        for position in positions:
            orders = position.get_orders()

            if len(orders) != 0:
                all_orders += orders

        for order in all_orders:

            if order.get_reference_id() == reference_id:
                return order

        return None

    def get_orders(
        self,
        type=None,
        status=None,
        side=None,
        target_symbol=None,
        trading_symbol=None,
    ) -> List[Order]:
        positions = self.get_positions()

        all_orders = []

        if target_symbol is not None:
            position = self.get_position(target_symbol)
            return position.get_orders(status=status, type=type, side=side)

        for position in positions:
            orders = position.get_orders(status=status, type=type, side=side)

            if len(orders) != 0:
                all_orders += orders

        return all_orders

    def get_number_of_orders(self):
        return len(self.get_orders())

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

        if self.get_positions() is None:
            raise OperationalException(
                "Trading symbol position is not specified"
            )

        for position in self.get_positions():

            if position.get_symbol() == self.get_trading_symbol():
                return position

        raise OperationalException(
            "Trading symbol position is not specified"
        )

    def get_allocated(self):
        allocated = 0

        for position in self.get_positions():
            allocated += position.get_allocated()

        return allocated

    def get_realized(self):
        realized = 0

        for order in self.get_orders():
            if OrderSide.BUY.equals(order.get_side()) and\
                    OrderStatus.CLOSED.equals(order.get_status()):
                realized += order.get_closing_price() \
                           * order.get_amount_target_symbol()
        return realized

    def get_total_revenue(self):
        revenue = 0

        for order in self.get_orders():
            if OrderSide.BUY.equals(order.get_side()) and \
                    OrderStatus.CLOSED.equals(order.get_status()):
                revenue += order.get_closing_price() \
                            * order.get_amount_target_symbol()
        return revenue

    def add_position(self, position):

        if isinstance(position, dict):
            position = Position.from_dict(position)
        elif not isinstance(position, Position):
            raise OperationalException(
                "Can't add position that is not an instance "
                "of a Position object"
            )

        self.positions.append(position)

    def add_positions(self, positions):
        new_positions = []

        for position in positions:

            if isinstance(position, dict):
                position = Position.from_dict(position)
            elif not isinstance(position, Position):
                raise OperationalException(
                    "Can't add position that is not an instance "
                    "of a Position object"
                )

            matching = next(
                (existing_position for existing_position in self.positions
                 if position.get_symbol() == existing_position.get_symbol()),
                None
            )

            if matching is None:
                new_positions.append(position)
            else:
                matching.set_amount(position.amount)
                matching.set_price(position.get_price())

        self.positions += new_positions

    def add_order(self, order):
        position = next(
            (position for position in self.positions
             if position.get_symbol() == order.get_target_symbol()), None
        )

        if position is None:
            position = Position(symbol=order.get_target_symbol())
            position.add_order(order)
            self.positions.append(position)
        else:
            position.add_order(order)

    def add_orders(self, orders):

        if orders is not None:

            for order in orders:

                if isinstance(order, Order):
                    position = next(
                        (position for position in self.positions
                         if position.get_symbol() == order.get_target_symbol()), None
                    )

                    if position is None:
                        position = Position(symbol=order.get_target_symbol())
                        position.add_order(order)
                        self.positions.append(position)
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
