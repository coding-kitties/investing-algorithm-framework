class BacktestProfile:

    def __init__(self, strategy_id, interval, time_unit):
        self._strategy_id = strategy_id
        self._interval = interval
        self._time_unit = time_unit
        self._backtest_start_date_data = None
        self._backtest_start_date = None
        self._backtest_index_date = None
        self._backtest_end_date = None

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
