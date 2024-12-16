from datetime import datetime
from typing import Union
from .backtesting.backtest_date_range import BacktestDateRange


class DateRange:
    """
    DateRange class. This class is used to define a date range and the name of
    the range. Also, it can be used to store trading metadata such as
    classification of the trend (Up or Down).
    """

    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        name: str,
        up_trend: bool = False,
        down_trend: bool = False
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.name = name
        self._up_trend = up_trend
        self._down_trend = down_trend

    @property
    def up_trend(self) -> Union[bool, None]:

        if self._up_trend and not self._down_trend:
            return True
        else:
            return None

    @up_trend.setter
    def up_trend(self, value: bool):
        self._up_trend = value

    @property
    def down_trend(self) -> Union[bool, None]:

        if self._down_trend and not self._up_trend:
            return True
        else:
            return None

    @down_trend.setter
    def down_trend(self, value: bool):
        self._down_trend = value

    def __str__(self):
        return f"DateRange({self.start_date}, {self.end_date}, {self.name})"

    def __repr__(self):
        return f"DateRange(Name: {self.name} " + \
            f"Start date: {self.start_date} " + \
            f"End date: {self.end_date})"

    def to_backtest_date_range(self):
        return BacktestDateRange(
            start_date=self.start_date,
            end_date=self.end_date,
            name=self.name
        )
