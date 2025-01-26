from enum import Enum


class MarketDataType(Enum):
    OHLCV = "OHLCV"
    TICKER = "TICKER"
    ORDER_BOOK = "ORDER_BOOK"
    CUSTOM = "CUSTOM"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in MarketDataType:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to MarketDataType"
            )

    @staticmethod
    def from_value(value):

        if isinstance(value, str):
            return MarketDataType.from_string(value)

        if isinstance(value, MarketDataType):

            for entry in MarketDataType:

                if value == entry:
                    return entry

        raise ValueError(
            f"Could not convert {value} to TimeFrame"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return MarketDataType.from_string(other) == self
