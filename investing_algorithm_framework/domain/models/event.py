from enum import Enum


class Event(Enum):
    PORTFOLIO_CREATED = "PORTFOLIO_CREATED"
    ORDER_CREATED = "ORDER_CREATED"
    TRADE_CLOSED = "TRADE_CLOSED"
    STRATEGY_RUN = "STRATEGY_RUN"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for status in Event:

                if value.upper() == status.value:
                    return status

        raise ValueError("Could not convert value to Event")

    @staticmethod
    def from_value(value):

        if isinstance(value, Event):
            for status in Event:

                if value == status:
                    return status
        elif isinstance(value, str):
            return Event.from_string(value)

        raise ValueError(f"Could not convert value {value} to Event")

    def equals(self, other):
        return Event.from_value(other) == self
