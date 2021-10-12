from enum import Enum


class OrderStatus(Enum):
    SUCCESS = 'SUCCESS'
    PENDING = 'PENDING'
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    CLOSED = "CLOSED"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for order_type in OrderStatus:

                if value.upper() == order_type.value:
                    return order_type

        raise ValueError("Could not convert value to OrderStatus")

    def equals(self, other):

        if other is None:
            return False

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return OrderStatus.from_string(other) == self
