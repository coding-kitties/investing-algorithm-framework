from enum import Enum


class OrderType(Enum):
    SELL = 'SELL'
    BUY = 'BUY'

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            if value.lower() == 'sell':
                return OrderType.SELL
            elif value.lower() == 'buy':
                return OrderType.BUY
            else:
                raise ValueError("Could not convert value to OrderType")

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return OrderType.from_string(other) == self
