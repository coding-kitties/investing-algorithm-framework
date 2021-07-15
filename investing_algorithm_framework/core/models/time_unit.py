from enum import Enum


class TimeUnit(Enum):
    SECONDS = "SECONDS"
    MINUTE = "MINUTE"
    HOUR = "HOUR"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in TimeUnit:

                if value.upper() == entry.value:
                    return entry

        raise ValueError(
            "Could not convert value to time unit"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return TimeUnit.from_string(other) == self
