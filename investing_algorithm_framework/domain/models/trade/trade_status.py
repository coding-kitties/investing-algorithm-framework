from enum import Enum
from investing_algorithm_framework.domain.exceptions import \
    OperationalException


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

        raise OperationalException(
            f"Could not convert value: '{value}' to TradeStatus"
        )

    @staticmethod
    def from_value(value):

        if isinstance(value, TradeStatus):
            for status in TradeStatus:

                if value == status:
                    return status
        elif isinstance(value, str):
            return TradeStatus.from_string(value)

        raise OperationalException(
            f"Could not convert value: {value} to TradeStatus"
        )

    def equals(self, other):
        return TradeStatus.from_value(other) == self
