from enum import Enum
from functools import lru_cache


class TimeFrame(Enum):
    CURRENT = "CURRENT"
    ONE_MINUTE = "1m"
    TWO_MINUTE = "2m"
    THREE_MINUTE = "3m"
    FOUR_MINUTE = "4m"
    FIVE_MINUTE = "5m"
    TEN_MINUTE = "10m"
    FIFTEEN_MINUTE = "15m"
    TWENTY_MINUTE = "20m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    TWO_HOUR = "2h"
    FOUR_HOUR = "4h"
    SIX_HOUR = "6h"
    EIGHT_HOUR = "8h"
    TWELVE_HOUR = "12h"
    ONE_DAY = "1d"
    THREE_DAY = "3d"
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    ONE_YEAR = "1Y"

    @staticmethod
    @lru_cache(maxsize=None)
    def _spellings():
        # Map every accepted spelling to its member: hour frames also
        # accept "H" and day frames also accept "D".
        spellings = {}

        for entry in TimeFrame:
            spellings[entry.value] = entry

            if "h" in entry.value:
                spellings.setdefault(entry.value.replace("h", "H"), entry)

            if "d" in entry.value:
                spellings.setdefault(entry.value.replace("d", "D"), entry)

        return spellings

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            entry = TimeFrame._spellings().get(value)

            if entry is not None:
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

    @staticmethod
    @lru_cache(maxsize=None)
    def _minutes():
        return {
            TimeFrame.ONE_MINUTE: 1,
            TimeFrame.TWO_MINUTE: 2,
            TimeFrame.THREE_MINUTE: 3,
            TimeFrame.FOUR_MINUTE: 4,
            TimeFrame.FIVE_MINUTE: 5,
            TimeFrame.TEN_MINUTE: 10,
            TimeFrame.FIFTEEN_MINUTE: 15,
            TimeFrame.TWENTY_MINUTE: 20,
            TimeFrame.THIRTY_MINUTE: 30,
            TimeFrame.ONE_HOUR: 60,
            TimeFrame.TWO_HOUR: 120,
            TimeFrame.FOUR_HOUR: 240,
            TimeFrame.SIX_HOUR: 360,
            TimeFrame.EIGHT_HOUR: 480,
            TimeFrame.TWELVE_HOUR: 720,
            TimeFrame.ONE_DAY: 1440,
            TimeFrame.THREE_DAY: 4320,
            TimeFrame.ONE_WEEK: 10080,
            TimeFrame.ONE_MONTH: 40320,
            TimeFrame.ONE_YEAR: 525600,
        }

    @property
    def amount_of_minutes(self):
        minutes = TimeFrame._minutes().get(self)

        if minutes is not None:
            return minutes

        raise ValueError(
            f"Could not determine amount of minutes for {self.value}"
        )

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
