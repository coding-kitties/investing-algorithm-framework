from enum import Enum


class PerformanceMetric(Enum):
    OVERALL_PERFORMANCE = "OVERALL_PERFORMANCE"
    DELTA = "DELTA"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in PerformanceMetric:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to PerformanceMetric"
            )

    @staticmethod
    def from_value(value):

        if isinstance(value, str):
            return PerformanceMetric.from_string(value)

        if isinstance(value, PerformanceMetric):

            for entry in PerformanceMetric:

                if value == entry:
                    return entry

        raise ValueError(
            f"Could not convert {value} to PerformanceMetric"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return PerformanceMetric.from_string(other) == self
