from investing_algorithm_framework.core.models import OrderStatus, OrderSide, \
    Order, OrderType
from investing_algorithm_framework.core.exceptions import OperationalException


class Position:

    def __init__(self, symbol, amount=0, price=None, orders=None):
        self.symbol = symbol
        self.amount = amount
        self.price = price
        self.cost = 0

        self.initialize_orders(orders)

    def initialize_orders(self, orders):
        self.orders = []

        if orders is not None:
            for order in orders:

                if isinstance(order, dict):
                    order = Order.from_dict(order)
                elif not isinstance(order, Order):
                    raise OperationalException(
                        "Order data model not supported"
                    )

            self.orders.append(order)

    def add_order(self, order):
        matching_order = next(
            (old_order for old_order in self.orders
             if old_order.get_reference_id() == order.get_reference_id()),
            None
        )

        if matching_order:
            raise OperationalException("Order already exists")

        self.orders.append(order)

    def get_symbol(self):
        return self.symbol

    def get_orders(self, status=None, type=None, side=None):

        if hasattr(self, "orders"):
            selected_orders = self.orders

            if status is not None:
                new = []

                for order in self.orders:
                    if not OrderStatus.from_value(
                            order.get_status()).equals(status):
                        new = selected_orders.remove(order)

                selected_orders = new

            if type is not None:
                new = []

                for order in self.orders:
                    if not OrderType.from_value(
                            order.get_type()).equals(type):
                        new = selected_orders.remove(order)

                selected_orders = new

            if side is not None:
                new = []

                for order in self.orders:
                    if not OrderSide.from_value(
                            order.get_side()).equals(side):
                        new = selected_orders.remove(order)

                selected_orders = new

            return selected_orders

        return []

    def set_orders(self, orders):
        self.orders = orders

    def get_amount(self):
        return self.amount

    def get_price(self):
        return self.price

    def get_cost(self):

        if not hasattr(self, "orders"):
            return 0

        if self.orders is None:
            return 0

        cost = 0

        for order in self.get_orders():

            if OrderSide.BUY.equals(order.side) and \
                    OrderStatus.SUCCESS.equals(order.status):
                cost += order.get_initial_price() * \
                       order.get_amount_target_symbol()

        return cost

    def get_allocated(self):

        if not hasattr(self, "orders"):
            return 0

        if self.orders is None:
            return 0

        allocated = 0

        for order in self.get_orders():

            if OrderSide.BUY.equals(order.side) and \
                    OrderStatus.SUCCESS.equals(order.status):
                allocated += order.get_price() \
                             * order.get_amount_target_symbol()

        return allocated

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
            price=data.get("price", None),
            amount=data.get("amount", None),
            orders=data.get("orders", None)
        )

    def __repr__(self):
        return self.to_string()

    def to_dict(self):
        return {
            "symbol": self.get_symbol(),
            "price": self.get_price(),
            "amount": self.get_amount(),
            "orders": self.get_orders()
        }
