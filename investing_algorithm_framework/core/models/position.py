from typing import List

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import OrderStatus, OrderSide, \
    Order, OrderType


class Position:

    def __init__(
        self,
        target_symbol=None,
        trading_symbol=None,
        symbol=None,
        amount=0,
        price=None,
        orders=None
    ):
        self.trading_symbol = None
        self.target_symbol = None

        if target_symbol is not None:
            self.target_symbol = target_symbol.upper()

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol

        if symbol is not None:
            self.target_symbol = symbol.upper()

        self.amount = amount
        self.price = price
        self.cost = 0
        self.orders = []
        self.add_orders(orders)

    def set_trading_symbol(self, trading_symbol):
        self.trading_symbol = trading_symbol

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_target_symbol(self):
        return self.target_symbol

    def get_symbol(self):
        return f"{self.get_target_symbol().upper()}" \
               f"/{self.get_trading_symbol()}"

    def get_order(self, reference_id) -> Order:
        for order in self.orders:

            if order.get_reference_id() == reference_id:
                return order

        return None

    def get_orders(self, status=None, type=None, side=None) -> List[Order]:

        if hasattr(self, "orders"):
            selected_orders = self.orders.copy()
            loop_list = selected_orders.copy()

            if status is not None:

                for order in loop_list:
                    if not order.get_status().equals(status):
                        selected_orders.remove(order)

            loop_list = selected_orders.copy()

            if type is not None:

                for order in loop_list:
                    if not OrderType.from_value(order.get_type()).equals(type):
                        selected_orders.remove(order)

            loop_list = selected_orders.copy()

            if side is not None:
                for order in loop_list:
                    if not OrderSide.from_value(order.get_side()).equals(side):
                        selected_orders.remove(order)

            return selected_orders
        else:
            return []

    def add_order(self, order: Order):

        if isinstance(order, dict):
            order = Order.from_dict(order)
        elif not isinstance(order, Order):
            raise OperationalException(
                "Can't add order that is not an instance "
                "of a Order object"
            )

        # Check if the reference id is set
        if order.get_reference_id() is None:
            raise OperationalException(
                "Can't add order to position with no reference id defined"
            )

        # Check if the order belongs to this position
        if order.get_target_symbol() != self.get_target_symbol():
            raise OperationalException(
                "Order does not belong to this position"
            )

        matching_order = next(
            (old_order for old_order in self.get_orders()
             if old_order.get_reference_id() == order.get_reference_id()),
            None
        )

        if matching_order is not None:
            matching_order.update(
                status=order.get_status(),
                price=order.get_price(),
                initial_price=order.get_initial_price(),
                closing_price=order.get_closing_price(),
                amount_trading_symbol=order.get_amount_trading_symbol(),
                amount_target_symbol=order.get_amount_target_symbol()
            )
        else:
            if OrderStatus.CLOSED.equals(order.status):

                if OrderSide.BUY.equals(order.side):
                    self.amount += order.get_amount_target_symbol()
                else:
                    self.amount -= order.get_amount_target_symbol()

            self.orders.append(order)

        self.update_amount()

    def add_orders(self, orders: List):

        if orders is not None:

            for order in orders:

                if isinstance(order, dict):
                    order = Order.from_dict(order)
                elif not isinstance(order, Order):
                    raise OperationalException(
                        "Can't add order that is not an instance "
                        "of a Order object"
                    )

                # Check if the reference id is set
                if order.get_reference_id() is None:
                    raise OperationalException(
                        "Can't add order to position with no reference "
                        "id defined"
                    )

                if order.get_target_symbol() != self.get_target_symbol():
                    raise OperationalException(
                        "Order does not belong to this position"
                    )

                matching = next(
                    (old_order for old_order in self.get_orders()
                     if old_order.get_reference_id() == order.get_reference_id()),
                    None
                )

                if not matching:

                    if OrderStatus.CLOSED.equals(order.status):
                        if OrderSide.BUY.equals(order.side):
                            self.amount += order.get_amount_target_symbol()
                        else:
                            self.amount -= order.get_amount_target_symbol()

                    self.orders.append(order)

                else:
                    matching.update(
                        status=order.get_status(),
                        price=order.get_price(),
                        initial_price=order.get_initial_price(),
                        closing_price=order.get_closing_price(),
                        amount_trading_symbol=order.get_amount_trading_symbol(),
                        amount_target_symbol=order.get_amount_target_symbol()
                    )

    def get_amount(self):
        return self.amount

    def set_amount(self, amount):
        self.amount = amount

    def get_price(self):

        if self.price is None:
            return 0

        return self.price

    def set_price(self, price):
        self.price = price

    def get_cost(self):

        if not hasattr(self, "orders"):
            return 0

        if self.orders is None:
            return 0

        cost = 0

        for order in self.get_orders():

            if OrderSide.BUY.equals(order.side) and \
                    OrderStatus.CLOSED.equals(order.status):
                cost += order.get_initial_price() * \
                       order.get_amount_target_symbol()

        return cost

    def get_allocated(self):
        return self.get_amount() * self.get_price()

    def get_pending_value(self):

        if not hasattr(self, "orders"):
            return 0

        if self.orders is None:
            return 0

        pending_value = 0

        for order in self.get_orders():

            if OrderSide.BUY.equals(order.side) and\
                    OrderStatus.PENDING.equals(order.status):
                pending_value += order.get_price() * \
                       order.get_amount_target_symbol()

        return pending_value

    def update_amount(self):
        buy_orders = self.get_orders(
            status=OrderStatus.CLOSED, side=OrderSide.BUY
        )

        sell_orders = self.get_orders(
            status=OrderStatus.CLOSED, side=OrderSide.SELL
        )

        amount = 0

        for order in buy_orders:
            amount += order.get_amount_target_symbol()

        for order in sell_orders:
            amount -= order.get_amount_target_symbol()

        self.amount = amount

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
            symbol=f"{self.get_symbol()}",
            amount=self.get_amount(),
            price=self.price,
            cost=self.get_cost()
        )

    @staticmethod
    def from_dict(data):
        return Position(
            symbol=data.get("symbol"),
            target_symbol=data.get("target_symbol"),
            price=data.get("price", None),
            amount=data.get("amount", None),
            orders=data.get("orders", None),
        )

    def __repr__(self):
        return self.to_string()

    def to_dict(self):
        return {
            "target_symbol": self.get_target_symbol(),
            "price": self.get_price(),
            "amount": self.get_amount(),
            "orders": self.get_orders()
        }
