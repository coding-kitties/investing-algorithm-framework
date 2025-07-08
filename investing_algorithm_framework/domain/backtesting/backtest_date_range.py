from datetime import datetime
from dateutil.parser import parse


class BacktestDateRange:
    """
    Represents a date range for a backtest
    """
    def __init__(self, start_date, end_date=None, name=None):

        if isinstance(start_date, str):
            start_date = parse(start_date)

        if end_date is not None and isinstance(end_date, str):
            end_date = parse(end_date)

        self._start_date = start_date
        self._end_date = end_date
        self._name = name

        if end_date is None:
            self._end_date = datetime.now()

        if end_date < start_date:
            raise ValueError(
                "End date cannot be before start date for a backtest "
                "date range. " +
                f"(start_date: {start_date}, end_date: {end_date})"
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

    def __repr__(self):
        return f"{self.name}: {self._start_date} - {self._end_date}"

    def __str__(self):
        return self.__repr__()
