from datetime import datetime, timedelta
from enum import Enum

from dateutil import relativedelta


class TimeFrame(Enum):
    CURRENT = "CURRENT"
    ONE_HOUR = "ONE_HOUR"
    ONE_DAY = "ONE_DAY"
    ONE_WEEK = "ONE_WEEK"
    ONE_MONTH = "ONE_MONTH"
    ONE_YEAR = "ONE_YEAR"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in TimeFrame:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to TimeFrame"
            )

    @staticmethod
    def from_value(value):

        if isinstance(value, str):
            return TimeFrame.from_string(value)

        if isinstance(value, TimeFrame):

            for entry in TimeFrame:

                if value == entry:
                    return entry

        raise ValueError(
            f"Could not convert {value} to TimeFrame"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return TimeFrame.from_string(other) == self

    def create_time_frame(self, end_datetime=None):

        if end_datetime is None:
            end_datetime = datetime.utcnow()

        if TimeFrame.ONE_HOUR.equals(self):
            start_datetime = end_datetime - \
                             relativedelta.relativedelta(hours=1)
        elif TimeFrame.ONE_DAY.equals(self):
            start_datetime = end_datetime - \
                             relativedelta.relativedelta(hours=24)
        elif TimeFrame.ONE_WEEK.equals(self):
            start_datetime = end_datetime - \
                             relativedelta.relativedelta(days=7)
        elif TimeFrame.ONE_MONTH.equals(self):
            start_datetime = \
                end_datetime - relativedelta.relativedelta(days=28)
        elif TimeFrame.ONE_YEAR.equals(self):
            start_datetime = \
                end_datetime - relativedelta.relativedelta(days=365)
        else:
            raise NotImplementedError(
                f"Timeframe {self.value} not implemented"
            )

        return start_datetime, end_datetime

    def duration(self):
        if TimeFrame.ONE_HOUR.equals(self):
            return relativedelta.relativedelta(hours=1)
        elif TimeFrame.ONE_DAY.equals(self):
            return relativedelta.relativedelta(hours=24)
        elif TimeFrame.ONE_WEEK.equals(self):
            return relativedelta.relativedelta(days=7)
        elif TimeFrame.ONE_MONTH.equals(self):
            return relativedelta.relativedelta(days=28)
        elif TimeFrame.ONE_YEAR.equals(self):
            return relativedelta.relativedelta(days=365)
        else:
            raise NotImplementedError(
                f"Timeframe {self.value} not implemented"
            )

    @property
    def time_interval(self):
        from investing_algorithm_framework.core.models import TimeInterval

        if TimeFrame.CURRENT.equals(self):
            return TimeInterval.CURRENT
        elif TimeFrame.ONE_HOUR.equals(self):
            return TimeInterval.MINUTES_ONE
        elif TimeFrame.ONE_DAY.equals(self):
            return TimeInterval.MINUTES_FIFTEEN
        elif TimeFrame.ONE_WEEK.equals(self):
            return TimeInterval.HOURS_ONE
        elif TimeFrame.ONE_MONTH.equals(self):
            return TimeInterval.HOURS_FOUR
        elif TimeFrame.ONE_YEAR.equals(self):
            return TimeInterval.DAYS_ONE
        else:
            raise NotImplementedError(
                f"Timeframe {self.value} not implemented"
            )

    @property
    def intervals(self):
        intervals = []
        start_datetime, end_datetime = self.create_time_frame()
        delta = end_datetime - start_datetime

        intervals.append(end_datetime)

        if TimeFrame.ONE_HOUR.equals(self):

            for i in range(1, int(delta.total_seconds() / 60)):
                intervals.append(end_datetime - timedelta(minutes=i))

        elif TimeFrame.ONE_DAY.equals(self):

            for i in range(1, int((delta.total_seconds() / 60) / 15)):
                intervals.append(end_datetime - timedelta(minutes=i * 15))

        elif TimeFrame.ONE_WEEK.equals(self):

            for i in range(1, int((delta.total_seconds() / 60) / 60)):
                intervals.append(end_datetime - timedelta(hours=i))

        elif TimeFrame.ONE_MONTH.equals(self):

            for i in range(1, int(((delta.total_seconds() / 60) / 60) / 4)):
                intervals.append(end_datetime - timedelta(hours=i * 4))

        elif TimeFrame.ONE_YEAR.equals(self):

            for i in range(1, int(delta.days)):
                intervals.append(
                    end_datetime - relativedelta.relativedelta(days=i)
                )

        else:
            raise NotImplementedError(
                f"Timeframe {self.value} not implemented"
            )

        return intervals
