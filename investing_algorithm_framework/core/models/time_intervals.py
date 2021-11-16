from enum import Enum
from .time_frame import TimeFrame


class TimeInterval(Enum):
    CURRENT = "CURRENT"
    MINUTES_ONE = "MINUTES_ONE"
    MINUTES_FIFTEEN = "MINUTES_FIFTEEN"
    HOURS_ONE = "HOURS_ONE"
    HOURS_FOUR = "HOURS_FOUR"
    DAYS_ONE = "DAYS_ONE"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in TimeInterval:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to TimeInterval"
            )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value

        else:
            return TimeInterval.from_string(other) == self

    @staticmethod
    def from_time_frame(time_frame):

        if TimeFrame.CURRENT.equals(time_frame):
            return TimeInterval.CURRENT
        elif TimeFrame.ONE_HOUR.equals(time_frame):
            return TimeInterval.MINUTES_ONE
        elif TimeFrame.ONE_DAY.equals(time_frame):
            return TimeInterval.MINUTES_FIFTEEN
        elif TimeFrame.ONE_WEEK.equals(time_frame):
            return TimeInterval.HOURS_ONE
        elif TimeFrame.ONE_MONTH.equals(time_frame):
            return TimeInterval.HOURS_FOUR
        elif TimeFrame.ONE_YEAR.equals(time_frame):
            return TimeInterval.DAYS_ONE
        else:
            raise NotImplementedError(
                f"Timeframe {time_frame} not implemented"
            )

    def amount_of_data_points(self):

        if TimeInterval.CURRENT.equals(self):
            return 1
        elif TimeInterval.MINUTES_ONE.equals(self):
            return 60
        elif TimeInterval.MINUTES_FIFTEEN.equals(self):
            return 96
        elif TimeInterval.HOURS_ONE.equals(self):
            return 168
        elif TimeInterval.HOURS_FOUR.equals(self):
            return 168
        elif TimeInterval.DAYS_ONE.equals(self):
            return 365
        else:
            raise NotImplementedError(f"Timeframe {self} not implemented")

    @property
    def time_frame(self):
        from investing_algorithm_framework.core.models.time_frame import \
            TimeFrame

        if TimeInterval.MINUTES_ONE.equals(self):
            return TimeFrame.ONE_HOUR
        elif TimeInterval.MINUTES_FIFTEEN.equals(self):
            return TimeFrame.ONE_DAY
        elif TimeInterval.HOURS_ONE.equals(self):
            return TimeFrame.ONE_WEEK
        elif TimeInterval.HOURS_FOUR.equals(self):
            return TimeFrame.ONE_MONTH
        elif TimeInterval.DAYS_ONE.equals(self):
            return TimeFrame.ONE_YEAR
        else:
            raise NotImplementedError(
                f"TimeInterval {self.value} not implemented"
            )
