from enum import Enum


class OrderType(Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for order_type in OrderType:

                if value.upper() == order_type.value:
                    return order_type

        raise ValueError("Could not convert value to OrderType")

    @staticmethod
    def from_value(value):

        if isinstance(value, OrderType):
            for order_type in OrderType:

                if value == order_type:
                    return order_type

        return OrderType.from_string(value)

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return OrderType.from_string(other) == self
