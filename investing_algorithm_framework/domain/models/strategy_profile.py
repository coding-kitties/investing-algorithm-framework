from .base_model import BaseModel
from .time_unit import TimeUnit


class StrategyProfile(BaseModel):

    def __init__(
        self,
        strategy_id=None,
        interval=None,
        time_unit=None,
        trading_time_frame=None,
        trading_time_frame_start_date=None,
        symbols=None,
        market=None,
        backtest_start_date_data=None,
        backtest_data_index_date=None,
        trading_data_type=None,
        trading_data_types=None,
    ):
        self._strategy_id = strategy_id
        self._interval = interval
        self._time_unit = time_unit
        self._number_of_runs = 0
        self._trading_time_frame = trading_time_frame
        self._trading_time_frame_start_date = trading_time_frame_start_date
        self._backtest_start_date_data = backtest_start_date_data
        self._backtest_data_index_date = backtest_data_index_date
        self._symbols = symbols
        self._market = market
        self._trading_data_type = trading_data_type
        self._trading_data_types = trading_data_types

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

    @symbols.setter
    def symbols(self, value):
        self._symbols = value

    @market.setter
    def market(self, value):
        self._market = value

    @number_of_runs.setter
    def number_of_runs(self, value):
        self._number_of_runs = value

    @trading_time_frame.setter
    def trading_time_frame(self, value):
        self._trading_time_frame = value

    @property
    def backtest_start_date_data(self):
        return self._backtest_start_date_data

    @backtest_start_date_data.setter
    def backtest_start_date_data(self, value):
        self._backtest_start_date_data = value

    @property
    def backtest_data_index_date(self):
        return self._backtest_data_index_date

    @backtest_data_index_date.setter
    def backtest_data_index_date(self, value):
        self._backtest_data_index_date = value

    @property
    def trading_data_type(self):
        return self._trading_data_type

    @trading_data_type.setter
    def trading_data_type(self, value):
        self._trading_data_type = value

    @property
    def trading_data_types(self):

        if self.trading_data_type is not None:
            return [self.trading_data_type]

        return self._trading_data_types

    @trading_data_types.setter
    def trading_data_types(self, value):
        self._trading_data_types = value

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
            number_of_runs=self._number_of_runs,
            trading_time_frame=self._trading_time_frame,
            trading_time_frame_start_date=self._trading_time_frame_start_date,
            symbols=self._symbols,
            time_unit=self.time_unit,
            interval=self.interval,
            market=self._market,
            backtest_start_date_data=self._backtest_start_date_data,
            backtest_data_index_date=self._backtest_data_index_date,
            trading_data_type=self._trading_data_type,
            trading_data_types=self._trading_data_types,
        )
