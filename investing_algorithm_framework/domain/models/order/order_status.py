from enum import Enum


class OrderStatus(Enum):
    CREATED = 'CREATED'
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for order_type in OrderStatus:

                if value.upper() == order_type.value:
                    return order_type

        raise ValueError(f"Could not convert value {value} to OrderStatus")

    @staticmethod
    def from_value(value):

        if isinstance(value, OrderStatus):
            for order_status in OrderStatus:

                if value == order_status:
                    return order_status
        elif isinstance(value, str):
            return OrderStatus.from_string(value)

        raise ValueError(f"Could not convert value: {value} to OrderStatus")

    def equals(self, other):
        return OrderStatus.from_value(other) == self

    @staticmethod
    def is_pending(value) -> bool:
        """Return True if the given status represents an order that is
        still working at the venue (i.e. not in a terminal state).

        In v9.0 ``OPEN`` is the only non-terminal status. A STOP order
        that has been triggered but not yet filled is still ``OPEN``;
        callers that need to distinguish that case should use
        :meth:`Order.is_triggered` (an orthogonal axis based on
        ``triggered_at``).
        """
        return OrderStatus.from_value(value) == OrderStatus.OPEN
