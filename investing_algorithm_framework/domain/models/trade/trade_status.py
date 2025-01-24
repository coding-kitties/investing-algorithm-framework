from enum import Enum


class TradeStatus(Enum):
    CREATED = "CREATED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for status in TradeStatus:

                if value.upper() == status.value:
                    return status

        raise ValueError("Could not convert value to TradeStatus")

    @staticmethod
    def from_value(value):

        if isinstance(value, TradeStatus):
            for status in TradeStatus:

                if value == status:
                    return status
        elif isinstance(value, str):
            return TradeStatus.from_string(value)

        raise ValueError("Could not convert value to TradeStatus")

    def equals(self, other):
        return TradeStatus.from_value(other) == self
