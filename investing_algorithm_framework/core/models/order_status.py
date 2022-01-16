from enum import Enum


class OrderStatus(Enum):
    SUCCESS = 'SUCCESS'
    PENDING = 'PENDING'
    TO_BE_SENT = "TO_BE_SENT"
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

    @staticmethod
    def from_value(value):

        if isinstance(value, OrderStatus):
            for order_status in OrderStatus:

                if value == order_status:
                    return order_status
        elif isinstance(value, str):
            return OrderStatus.from_string(value)

        raise ValueError("Could not convert value to OrderStatus")


    def equals(self, other):

        if other is None:
            return False

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return OrderStatus.from_string(other) == self
