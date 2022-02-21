from investing_algorithm_framework.core.models import OrderStatus


class Position:

    def __init__(self, symbol, amount, price=None, orders=None):
        self.symbol = symbol
        self.amount = amount
        self.orders = orders
        self.price = price
        self.cost = 0

    def get_symbol(self):
        return self.symbol

    def get_orders(self):
        return self.orders

    def get_amount(self):
        return self.amount

    def get_price(self):
        return self.price

    def get_cost(self):

        if self.orders is None:
            return 0

        cost = 0

        for order in self.orders:

            if OrderStatus.SUCCESS.equals(order.status):
                cost += order.get_initial_price() * \
                       order.get_amount_target_symbol()

        return cost

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
            symbol=f"{self.symbol()}",
            amount=self.get_amount(),
            price=self.price,
            cost=self.get_cost()
        )

    def __repr__(self):
        return self.to_string()
