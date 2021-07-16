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

        raise ValueError("Could not convert value to OrderSide")

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return OrderSide.from_string(other) == self
