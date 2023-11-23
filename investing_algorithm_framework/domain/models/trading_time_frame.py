from enum import Enum
from datetime import timedelta, datetime

from investing_algorithm_framework.domain.exceptions import \
    OperationalException


class TradingTimeFrame(Enum):
    ONE_MINUTE = "ONE_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"
    ONE_HOUR = "ONE_HOUR"
    TWO_HOUR = "TWO_HOUR"
    ONE_DAY = 'ONE_DAY'
    ONE_MONTH = "ONE_MONTH"
    ONE_YEAR = "ONE_YEAR"

    def create_time_frame_from_limit(self, limit: int = 50):

        if TradingTimeFrame.ONE_MINUTE.equals(self):
            hold = 1
            start_date = datetime.now() - timedelta(minutes=limit)
        elif TradingTimeFrame.FIFTEEN_MINUTE.equals(self):
            hold = 15
            start_date = datetime.now() - timedelta(minutes=(limit * 15))
        elif TradingTimeFrame.ONE_HOUR.equals(self):
            hold = 60
            start_date = datetime.now() - timedelta(hours=limit)
        elif TradingTimeFrame.TWO_HOUR.equals(self):
            hold = 60 * 2
            start_date = datetime.now() - timedelta(hours=limit)
        elif TradingTimeFrame.ONE_DAY.equals(self):
            hold = 60 * 24
            start_date = datetime.now() - timedelta(days=limit)
        elif TradingTimeFrame.ONE_MONTH.equals(self):
            hold = 60 * 24 * 30
            start_date = datetime.now() - timedelta(weeks=(4 * limit))
        else:
            hold = 60 * 24 * 365
            start_date = datetime.now() - timedelta(days=(limit * 365))

        iteration = 1
        dates = []
        while iteration < limit or \
                start_date + timedelta(minutes=hold) < datetime.now():
            dates.append(start_date + timedelta(minutes=hold))
            start_date += timedelta(minutes=hold)
            iteration += 1

        dates.append(datetime.now())
        return dates

    def create_time_frame_from_start_date(self, start_date: datetime):

        if start_date > datetime.now():
            raise OperationalException("Start date cannot be in the future")

        if TradingTimeFrame.ONE_MINUTE.equals(self):
            hold = 1
        elif TradingTimeFrame.FIFTEEN_MINUTE.equals(self):
            hold = 15
        elif TradingTimeFrame.ONE_HOUR.equals(self):
            hold = 60
        elif TradingTimeFrame.TWO_HOUR.equals(self):
            hold = 60 * 2
        elif TradingTimeFrame.ONE_DAY.equals(self):
            hold = 60 * 24
        elif TradingTimeFrame.ONE_MONTH.equals(self):
            hold = 60 * 24 * 30
        else:
            hold = 60 * 24 * 365

        iteration = 1
        dates = []

        while start_date < datetime.now():
            dates.append(start_date + timedelta(minutes=hold))
            start_date += timedelta(minutes=hold)
            iteration += 1

        dates.append(datetime.now())
        return dates

    def to_ccxt_string(self):

        if TradingTimeFrame.ONE_MINUTE.equals(self):
            return "1m"

        if TradingTimeFrame.FIFTEEN_MINUTE.equals(self):
            return "15m"

        if TradingTimeFrame.ONE_HOUR.equals(self):
            return "1h"

        if TradingTimeFrame.TWO_HOUR.equals(self):
            return "2h"

        if TradingTimeFrame.ONE_DAY.equals(self):
            return "1d"

        if TradingTimeFrame.ONE_MONTH.equals(self):
            return "1m"

        if TradingTimeFrame.ONE_YEAR.equals(self):
            return "1y"

        raise OperationalException("Data time unit value is not supported")

    @staticmethod
    def from_value(value):

        if isinstance(value, TradingTimeFrame):
            for data_time_unit in TradingTimeFrame:

                if value == data_time_unit:
                    return data_time_unit

        elif isinstance(value, str):
            return TradingTimeFrame.from_string(value)

        raise ValueError(
            "Could not convert value to data time unit"
        )

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for data_time_unit in TradingTimeFrame:

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
            return TradingTimeFrame.from_string(other) == self

    def create_start_date(self, limit=50):

        if TradingTimeFrame.ONE_MINUTE.equals(self):
            return datetime.now() - timedelta(minutes=limit)

        if TradingTimeFrame.FIFTEEN_MINUTE.equals(self):
            return datetime.now() - timedelta(minutes=(limit * 15))

        if TradingTimeFrame.ONE_HOUR.equals(self):
            return datetime.now() - timedelta(hours=limit)

        if TradingTimeFrame.TWO_HOUR.equals(self):
            return datetime.now() - timedelta(hours=limit * 2)

        if TradingTimeFrame.ONE_DAY.equals(self):
            return datetime.now() - timedelta(days=limit)

        if TradingTimeFrame.ONE_MONTH.equals(self):
            return datetime.now() - timedelta(weeks=(4 * limit))

        if TradingTimeFrame.ONE_YEAR.equals(self):
            return datetime.now() - timedelta(days=(limit * 365))

        raise OperationalException("Data time unit value is not supported")

    @property
    def minutes(self):

        if TradingTimeFrame.ONE_MINUTE.equals(self):
            return 1

        if TradingTimeFrame.FIFTEEN_MINUTE.equals(self):
            return 15

        if TradingTimeFrame.ONE_HOUR.equals(self):
            return 60

        if TradingTimeFrame.TWO_HOUR.equals(self):
            return 120

        if TradingTimeFrame.ONE_DAY.equals(self):
            return 60 * 24

        if TradingTimeFrame.ONE_MONTH.equals(self):
            return 60 * 24 * 30

        if TradingTimeFrame.ONE_YEAR.equals(self):
            return 60 * 24 * 365

        raise OperationalException("Data time frame value is not supported")

    @property
    def milliseconds(self):

        if TradingTimeFrame.ONE_MINUTE.equals(self):
            return 60 * 1000

        if TradingTimeFrame.FIFTEEN_MINUTE.equals(self):
            return 15 * 60 * 1000

        if TradingTimeFrame.ONE_HOUR.equals(self):
            return 60 * 60 * 1000

        if TradingTimeFrame.TWO_HOUR.equals(self):
            return 2* 60 * 60 * 1000

        if TradingTimeFrame.ONE_DAY.equals(self):
            return 60 * 60 * 24 * 1000

        if TradingTimeFrame.ONE_MONTH.equals(self):
            return 60 * 60 * 24 * 30 * 1000

        if TradingTimeFrame.ONE_YEAR.equals(self):
            return 60 * 60 * 24 * 365 * 1000

        raise OperationalException("Data time frame value is not supported")
