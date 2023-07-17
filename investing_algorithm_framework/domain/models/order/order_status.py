from enum import Enum


class OrderStatus(Enum):
    PENDING = 'PENDING'
    TO_BE_SENT = "TO_BE_SENT"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    CLOSED = "CLOSED"
    SUCCESS = "SUCCESS"

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

    @staticmethod
    def from_ccxt_status(ccxt_status):
        status = OrderStatus.PENDING.value

        if ccxt_status == "open":
            status = OrderStatus.PENDING.value
        if ccxt_status == "closed":
            status = OrderStatus.SUCCESS.value
        if ccxt_status == "canceled":
            status = OrderStatus.CANCELED.value
        if ccxt_status == "expired":
            status = OrderStatus.FAILED.value
        if ccxt_status == "rejected":
            status = OrderStatus.FAILED.value

        return OrderStatus.from_value(status)

    def equals(self, other):
        return OrderStatus.from_value(other) == self
