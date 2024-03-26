from enum import Enum


class AppMode(Enum):
    STATELESS = "STATELESS"
    DEFAULT = "DEFAULT"
    WEB = "WEB"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for status in AppMode:

                if value.upper() == status.value:
                    return status

        raise ValueError("Could not convert value to AppMode")

    @staticmethod
    def from_value(value):

        if isinstance(value, AppMode):
            for status in AppMode:

                if value == status:
                    return status
        elif isinstance(value, str):
            return AppMode.from_string(value)

        raise ValueError(f"Could not convert value {value} to AppMode")

    def equals(self, other):
        return AppMode.from_value(other) == self
