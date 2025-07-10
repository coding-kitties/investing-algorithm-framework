from datetime import timedelta
from enum import Enum


class TimeUnit(Enum):
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in TimeUnit:

                if value.upper() == entry.value:
                    return entry

        raise ValueError(
            f"Could not convert value {value} to time unit," +
            " please make sure that the value is either of type string or" +
            f"TimeUnit. Its current type is {type(value)}"
        )

    @staticmethod
    def from_ohlcv_data_file(file_path: str):
        """
        Extracts the time unit from the file name of an OHLCV data file.
        The file name should contain the time unit in the
        format 'symbol_timeunit.csv'.

        Args:
            file_path (str): The file path of the OHLCV data file.

        Returns:
            TimeUnit: The extracted time unit.
        """
        if not isinstance(file_path, str):
            raise ValueError("File path must be a string.")

        parts = file_path.split('_')
        if len(parts) < 2:
            raise ValueError("File name does not contain a valid time unit.")

        time_unit_str = parts[-1].split('.')[0].upper()
        try:
            return TimeUnit.from_string(time_unit_str)
        except ValueError:
            raise ValueError(
                f"Could not extract time unit from file name: {file_path}. "
                "Expected format 'symbol_timeunit.csv', "
                f"got '{time_unit_str}'."
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
        elif TimeUnit.HOUR.equals(self):
            return timedelta(hours=interval)
        elif TimeUnit.DAY.equals(self):
            return timedelta(days=interval)

        raise ValueError(f"Unsupported time unit: {self}")

    @property
    def single_name(self):

        if TimeUnit.SECOND.equals(self.value):
            return "second"

        if TimeUnit.MINUTE.equals(self.value):
            return "minute"

        if TimeUnit.HOUR.equals(self.value):
            return "hour"

        if TimeUnit.DAY.equals(self.value):
            return "day"

    @property
    def plural_name(self):

        if TimeUnit.SECOND.equals(self.value):
            return "seconds"

        if TimeUnit.MINUTE.equals(self.value):
            return "minutes"

        if TimeUnit.HOUR.equals(self.value):
            return "hours"

        if TimeUnit.DAY.equals(self.value):
            return "days"
