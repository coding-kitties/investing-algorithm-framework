from enum import Enum


class TradingDataTypes(Enum):
    TICKER = 'TICKER'
    ORDER_BOOK = 'ORDER_BOOK'
    UN_SPECIFIED = "UN_SPECIFIED"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for order_type in TradingDataTypes:

                if value.upper() == order_type.value:
                    return order_type

        raise ValueError(
            "Could not convert value to data_provider provider "
            "data_provider type"
        )

    def equals(self, other):

        if other is None:
            return False

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return TradingDataTypes.from_string(other) == self
