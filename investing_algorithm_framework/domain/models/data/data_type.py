from enum import Enum


class DataType(Enum):
    OHLCV = "OHLCV"
    TICKER = "TICKER"
    ORDER_BOOK = "ORDER_BOOK"
    CUSTOM = "CUSTOM"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in DataType:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to DataType"
            )

    @staticmethod
    def from_value(value):

        if isinstance(value, str):
            return DataType.from_string(value)

        if isinstance(value, DataType):

            for entry in DataType:

                if value == entry:
                    return entry

        raise ValueError(
            f"Could not convert {value} to TimeFrame"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return DataType.from_string(other) == self
