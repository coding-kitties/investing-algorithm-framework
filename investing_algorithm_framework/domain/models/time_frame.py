from enum import Enum


class TimeFrame(Enum):
    CURRENT = "CURRENT"
    ONE_MINUTE = "1m"
    TWO_MINUTE = "2m"
    THREE_MINUTE = "3m"
    FOUR_MINUTE = "4m"
    FIVE_MINUTE = "5m"
    TEN_MINUTE = "10m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    TWO_HOUR = "2h"
    FOUR_HOUR = "4h"
    TWELVE_HOUR = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    ONE_YEAR = "1Y"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in TimeFrame:

                # For hour timeframes compare with and without H
                if "H" in entry.value:

                    if value == entry.value:
                        return entry

                    if value == entry.value.replace("H", "h"):
                        return entry

                # For hour timeframes compare with and without H
                if "d" in entry.value:

                    if value == entry.value:
                        return entry

                    if value == entry.value.replace("d", "D"):
                        return entry

                if value == entry.value:
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

    @property
    def amount_of_minutes(self):

        if self.equals(TimeFrame.ONE_MINUTE):
            return 1

        if self.equals(TimeFrame.TWO_MINUTE):
            return 2

        if self.equals(TimeFrame.THREE_MINUTE):
            return 3

        if self.equals(TimeFrame.FOUR_MINUTE):
            return 4

        if self.equals(TimeFrame.FIVE_MINUTE):
            return 5

        if self.equals(TimeFrame.TEN_MINUTE):
            return 10

        if self.equals(TimeFrame.FIFTEEN_MINUTE):
            return 15

        if self.equals(TimeFrame.THIRTY_MINUTE):
            return 30

        if self.equals(TimeFrame.ONE_HOUR):
            return 60

        if self.equals(TimeFrame.TWO_HOUR):
            return 120

        if self.equals(TimeFrame.FOUR_HOUR):
            return 240

        if self.equals(TimeFrame.TWELVE_HOUR):
            return 720

        if self.equals(TimeFrame.ONE_DAY):
            return 1440

        if self.equals(TimeFrame.ONE_WEEK):
            return 10080

        if self.equals(TimeFrame.ONE_MONTH):
            return 40320

    # Add comparison methods for ordering
    def __lt__(self, other):
        if isinstance(other, TimeFrame):
            return self.amount_of_minutes < other.amount_of_minutes
        raise TypeError(f"Cannot compare TimeFrame with {type(other)}")

    def __le__(self, other):
        if isinstance(other, TimeFrame):
            return self.amount_of_minutes <= other.amount_of_minutes
        raise TypeError(f"Cannot compare TimeFrame with {type(other)}")

    def __gt__(self, other):
        if isinstance(other, TimeFrame):
            return self.amount_of_minutes > other.amount_of_minutes
        raise TypeError(f"Cannot compare TimeFrame with {type(other)}")

    def __ge__(self, other):
        if isinstance(other, TimeFrame):
            return self.amount_of_minutes >= other.amount_of_minutes
        raise TypeError(f"Cannot compare TimeFrame with {type(other)}")
