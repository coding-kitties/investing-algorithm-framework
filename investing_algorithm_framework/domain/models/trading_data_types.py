from enum import Enum


class TradingDataType(Enum):
    TICKER = 'TICKER'
    ORDER_BOOK = 'ORDER_BOOK'
    OHLCV = "OHLCV"

    @staticmethod
    def from_value(value):

        if isinstance(value, TradingDataType):
            for trading_data_type in TradingDataType:

                if value == trading_data_type:
                    return trading_data_type

        elif isinstance(value, str):
            return TradingDataType.from_string(value)

        raise ValueError(
            "Could not convert value to trading data type"
        )

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for order_type in TradingDataType:

                if value.upper() == order_type.value:
                    return order_type

        raise ValueError(
            "Could not convert value to trading data type"
        )

    def equals(self, other):

        if other is None:
            return False

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return TradingDataType.from_string(other) == self
