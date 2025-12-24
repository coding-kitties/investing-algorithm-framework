from datetime import datetime, timezone
from dateutil.parser import parse
from logging import getLogger

from investing_algorithm_framework.domain.exceptions import \
    OperationalException

logger = getLogger("investing_algorithm_framework")


class BacktestDateRange:
    """
    Represents a date range for a backtest. This class
    will check that the start and end dates are valid for a backtest.

    Attributes:
        _start_date (datetime): The start date of the backtest.
        _end_date (datetime): The end date of the backtest. If not provided,
            it defaults to the current UTC time.
        _name (str): An optional name for the backtest date range.
    """
    def __init__(self, start_date, end_date=None, name=None):

        if isinstance(start_date, str):
            start_date = parse(start_date)

        if end_date is not None and isinstance(end_date, str):
            end_date = parse(end_date)

        if end_date is None:
            self._end_date = datetime.now(tz=timezone.utc)

        # Check if start_date end end_date are utc datetime objects
        time_zone_info = start_date.tzinfo

        if time_zone_info is None or time_zone_info is not timezone.utc:
            logger.warning(
                "Start date must be a UTC datetime object. "
                f"Received: {start_date}"
            )
            # Convert to UTC if not already
            start_date = start_date.astimezone(timezone.utc)

        time_zone_info = end_date.tzinfo

        if time_zone_info is None or time_zone_info is not timezone.utc:
            logger.warning(
                "End date must be a UTC datetime object. "
                f"Received: {end_date}"
            )
            # Convert to UTC if not already
            end_date = end_date.astimezone(timezone.utc)

        self._start_date = start_date
        self._end_date = end_date
        self._name = name

        if end_date < start_date:
            raise ValueError(
                "End date cannot be before start date for a backtest "
                "date range. " +
                f"(start_date: {start_date}, end_date: {end_date})"
            )

        # Check if the start date is rounded to the nearest hour
        if start_date.minute != 0 or start_date.second != 0 \
                or start_date.microsecond != 0:
            raise OperationalException(
                "Start date must be rounded to the nearest hour. "
                f"Received: {start_date}"
            )
        # Check if the end date is rounded to the nearest hour
        if end_date.minute != 0 or end_date.second != 0 \
                or end_date.microsecond != 0:
            raise OperationalException(
                "End date must be rounded to the nearest hour. "
                f"Received: {end_date}"
            )

    @property
    def start_date(self):
        return self._start_date

    @property
    def end_date(self):
        return self._end_date

    @property
    def name(self):
        return self._name

    def __eq__(self, other):
        """
        Two BacktestDateRange objects are equal if they have the same
        start and end dates, regardless of their names.
        """
        if not isinstance(other, BacktestDateRange):
            return False
        return (self._start_date == other._start_date and
                self._end_date == other._end_date)

    def __hash__(self):
        """
        Hash based on start and end dates to make the object hashable
        for use in sets and as dictionary keys.
        """
        return hash((self._start_date, self._end_date))

    def __repr__(self):
        return f"{self.name}: {self._start_date} - {self._end_date}"

    def __str__(self):
        return self.__repr__()
