from datetime import datetime


class BacktestDateRange:
    """
    Represents a date range for a backtest
    """
    def __init__(self, start_date, end_date = None, name = None):
        self._start_date = start_date
        self._end_date = end_date
        self._name = name

        if end_date is None:
            self._end_date = datetime.now()

    @property
    def start_date(self):
        return self._start_date

    @property
    def end_date(self):
        return self._end_date

    @property
    def name(self):
        return self._name
