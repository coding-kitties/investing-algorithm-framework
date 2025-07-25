from enum import Enum


class SnapshotInterval(Enum):
    STRATEGY_ITERATION = "STRATEGY_ITERATION"
    DAILY = "DAILY"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in SnapshotInterval:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to SnapshotInterval"
            )
        return None

    @staticmethod
    def from_value(value):

        if isinstance(value, str):
            return SnapshotInterval.from_string(value)

        if isinstance(value, SnapshotInterval):

            for entry in SnapshotInterval:

                if value == entry:
                    return entry

        raise ValueError(
            f"Could not convert {value} to SnapshotInterval"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return SnapshotInterval.from_string(other) == self
