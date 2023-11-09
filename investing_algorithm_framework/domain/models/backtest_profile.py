from .base_model import BaseModel
from .time_unit import TimeUnit


class BacktestProfile(BaseModel):

    def __init__(
        self,
        strategy_id=None,
        interval=None,
        time_unit=None,
        backtest_start_date_data=None,
        backtest_start_date=None,
        backtest_end_date=None,
        backtest_index_date=None,
        trading_time_frame=None,
        trading_time_frame_start_date=None,
        symbols=None,
        market=None,
        number_of_days=0,
        number_of_orders=0,
        number_of_positions=0
    ):
        self._strategy_id = strategy_id
        self._interval = interval
        self._time_unit = time_unit
        self._backtest_start_date_data = backtest_start_date_data
        self._backtest_start_date = backtest_start_date
        self._backtest_end_date = backtest_end_date
        self._backtest_index_date = backtest_index_date
        self._number_of_runs = 0
        self._trading_time_frame = trading_time_frame
        self._trading_time_frame_start_date = trading_time_frame_start_date
        self._symbols = symbols
        self._market = market
        self._number_of_days = number_of_days
        self._number_of_orders = number_of_orders
        self._number_of_positions = number_of_positions

    @property
    def strategy_id(self):
        return self._strategy_id

    @strategy_id.setter
    def strategy_id(self, strategy_id):
        self._strategy_id = strategy_id

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, value):
        self._interval = value

    @property
    def time_unit(self):
        return self._time_unit

    @time_unit.setter
    def time_unit(self, value):
        self._time_unit = value

    @property
    def symbols(self):
        return self._symbols

    @property
    def backtest_start_date_data(self):
        return self._backtest_start_date_data

    @property
    def backtest_start_date(self):
        return self._backtest_start_date

    @property
    def backtest_end_date(self):
        return self._backtest_end_date

    @property
    def backtest_index_date(self):
        return self._backtest_index_date

    @property
    def trading_time_frame(self):
        return self._trading_time_frame

    @property
    def trading_time_frame_start_date(self):
        return self._trading_time_frame_start_date

    @property
    def number_of_runs(self):
        return self._number_of_runs

    @property
    def market(self):
        return self._market

    @property
    def number_of_days(self):
        return self._number_of_days

    @symbols.setter
    def symbols(self, value):
        self._symbols = value

    @market.setter
    def market(self, value):
        self._market = value

    @backtest_start_date.setter
    def backtest_start_date(self, value):
        self._backtest_start_date = value

    @backtest_start_date_data.setter
    def backtest_start_date_data(self, value):
        self._backtest_start_date_data = value

    @backtest_end_date.setter
    def backtest_end_date(self, value):
        self._backtest_end_date = value

    @backtest_index_date.setter
    def backtest_index_date(self, value):
        self._backtest_index_date = value

    @number_of_runs.setter
    def number_of_runs(self, value):
        self._number_of_runs = value

    @trading_time_frame.setter
    def trading_time_frame(self, value):
        self._trading_time_frame = value

    @trading_time_frame_start_date.setter
    def trading_time_frame_start_date(self, value):
        self._trading_time_frame_start_date = value

    @number_of_days.setter
    def number_of_days(self, value):
        self._number_of_days = value

    @property
    def number_of_orders(self):
        return self._number_of_orders

    @number_of_orders.setter
    def number_of_orders(self, value):
        self._number_of_orders = value

    @property
    def number_of_positions(self):
        return self._number_of_positions

    @number_of_positions.setter
    def number_of_positions(self, value):
        self._number_of_positions = value


    def get_runs_per_day(self):

        if self.time_unit is None:
            return 0
        elif TimeUnit.SECOND.equals(self.time_unit):
            return 86400 / self.interval
        elif TimeUnit.MINUTE.equals(self.time_unit):
            return 1440 / self.interval
        else:
            return 24 / self.interval

    def __repr__(self):
        return self.repr(
            strategy_id=self._strategy_id,
            start_date=self.backtest_start_date,
            end_date=self.backtest_end_date,
            backtest_index_date=self.backtest_index_date,
            start_date_data=self.backtest_start_date_data,
            time_unit=self.time_unit,
            interval=self.interval
        )
