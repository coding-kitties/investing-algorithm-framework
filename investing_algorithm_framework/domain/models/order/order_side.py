from enum import Enum


class OrderSide(Enum):
    SELL = 'SELL'
    BUY = 'BUY'

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for order_type in OrderSide:

                if value.upper() == order_type.value:
                    return order_type

        raise ValueError(f"Could not convert value {value} to OrderSide")

    @staticmethod
    def from_value(value):

        if isinstance(value, OrderSide):
            for order_side in OrderSide:

                if value == order_side:
                    return order_side

        return OrderSide.from_string(value)

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return OrderSide.from_string(other) == self
