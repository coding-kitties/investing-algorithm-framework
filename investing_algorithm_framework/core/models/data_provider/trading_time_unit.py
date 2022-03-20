from enum import Enum
from datetime import timedelta, datetime

from investing_algorithm_framework.core.exceptions import OperationalException


class TradingTimeUnit(Enum):
    ONE_MINUTE = "ONE_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"
    ONE_HOUR = "ONE_HOUR"
    ONE_DAY = 'ONE_DAY'
    ONE_MONTH = "ONE_MONTH"
    ONE_YEAR = "ONE_YEAR"

    def create_time_frame(self, limit: int):

        if TradingTimeUnit.ONE_MINUTE.equals(self):
            return datetime.now() - timedelta(minutes=limit)

        if TradingTimeUnit.FIFTEEN_MINUTE.equals(self):
            return datetime.now() - timedelta(minutes=(limit * 15))

        if TradingTimeUnit.ONE_HOUR.equals(self):
            return datetime.now() - timedelta(hours=limit)

        if TradingTimeUnit.ONE_DAY.equals(self):
            return datetime.now() - timedelta(days=limit)

        if TradingTimeUnit.ONE_MONTH.equals(self):
            return datetime.now() - timedelta(weeks=(4 * limit))

        if TradingTimeUnit.ONE_YEAR.equals(self):
            return datetime.now() - timedelta(days=(limit * 365))

        raise OperationalException("Data time unit value is not supported")

    def to_ccxt_string(self):

        if TradingTimeUnit.ONE_MINUTE.equals(self):
            return "1m"

        if TradingTimeUnit.FIFTEEN_MINUTE.equals(self):
            return "15m"

        if TradingTimeUnit.ONE_HOUR.equals(self):
            return "1h"

        if TradingTimeUnit.ONE_DAY.equals(self):
            return "1d"

        if TradingTimeUnit.ONE_MONTH.equals(self):
            return "1m"

        if TradingTimeUnit.ONE_YEAR.equals(self):
            return "1y"

        raise OperationalException("Data time unit value is not supported")

    @staticmethod
    def from_value(value):

        if isinstance(value, TradingTimeUnit):
            for data_time_unit in TradingTimeUnit:

                if value == data_time_unit:
                    return data_time_unit

        elif isinstance(value, str):
            return TradingTimeUnit.from_string(value)

        raise ValueError(
            "Could not convert value to data time unit"
        )

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for data_time_unit in TradingTimeUnit:

                if value.upper() == data_time_unit.value:
                    return data_time_unit

        raise ValueError(
            "Could not convert value to data time unit"
        )

    def equals(self, other):

        if other is None:
            return False

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return TradingTimeUnit.from_string(other) == self
