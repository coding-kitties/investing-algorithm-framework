from enum import Enum
from datetime import datetime, timedelta


class TimeUnit(Enum):
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in TimeUnit:

                if value.upper() == entry.value:
                    return entry

        raise ValueError(
            f"Could not convert value {value} to time unit"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return TimeUnit.from_string(other) == self

    @staticmethod
    def from_value(value):

        if isinstance(value, TimeUnit):

            for entry in TimeUnit:

                if entry == value:
                    return entry

        return TimeUnit.from_string(value)

    def create_date(self, start_date, interval):

        if TimeUnit.SECOND.equals(self):
            return timedelta(minutes=interval)
        elif TimeUnit.MINUTE.equals(self):
            return timedelta(minutes=interval)
        else:
            return timedelta(hours=interval)

    @property
    def single_name(self):

        if TimeUnit.SECOND.equals(self.value):
            return "second"

        if TimeUnit.MINUTE.equals(self.value):
            return "minute"

        if TimeUnit.HOUR.equals(self.value):
            return "hour"

    @property
    def plural_name(self):

        if TimeUnit.SECOND.equals(self.value):
            return "seconds"

        if TimeUnit.MINUTE.equals(self.value):
            return "minutes"

        if TimeUnit.HOUR.equals(self.value):
            return "hours"

