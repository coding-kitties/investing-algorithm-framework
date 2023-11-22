from .base_model import BaseModel
from .time_unit import TimeUnit


class BacktestPosition(BaseModel):

    def __init__(self, position, trading_symbol=False):
        self.symbol = position.symbol
        self.amount = position.amount
        self._cost = position.cost
        self._price = 0.0
        self._trading_symbol = trading_symbol

    @property
    def price(self):
        return self._price

    @price.setter
    def price(self, value):
        self._price = value

    @property
    def cost(self):

        if self._trading_symbol:
            return self.amount

        return self._cost

    @property
    def value(self):

        if self._trading_symbol:
            return self.amount

        return self._price * self.amount

    @property
    def growth(self):

        if self._trading_symbol:
            return 0.0

        return self.value - self.cost

    @property
    def growth_rate(self):

        if self._trading_symbol:
            return 0.0

        if self.cost == 0:
            return 0.0

        return self.growth / self.cost * 100


class BacktestProfile(BaseModel):

    def __init__(
        self,
        portfolio_id=None,
        initial_unallocated=0.0,
        interval=None,
        time_unit=None,
        backtest_start_date_data=None,
        backtest_data_index_date=None,
        backtest_start_date=None,
        backtest_end_date=None,
        backtest_index_date=None,
        trading_time_frame=None,
        trading_time_frame_start_date=None,
        symbols=None,
        market=None,
        number_of_days=0,
        number_of_orders=0,
        number_of_positions=0,
        market_data_file=None,
        number_of_trades_closed=0,
        number_of_trades_open=0,
        percentage_positive_trades=0.0,
        percentage_negative_trades=0.0,
        total_cost=0.0,
        trading_symbol=None,
        total_net_gain_percentage=0.0,
        total_net_gain=0,
        growth_rate=0.0,
        growth=0,
        total_value=0.0,
        positions=None,
        average_trade_duration=0,
        average_trade_size=0.0,
        trades=None
    ):
        self._portfolio_id = portfolio_id
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
        self._market_data_file = market_data_file
        self._percentage_positive_trades = percentage_positive_trades
        self._percentage_negative_trades = percentage_negative_trades
        self._number_of_trades_closed = number_of_trades_closed
        self._number_of_trades_open = number_of_trades_open
        self._total_cost = total_cost
        self._growth_rate = 0.0
        self._growth = 0.0
        self._initial_unallocated = initial_unallocated
        self._trading_symbol = trading_symbol
        self._total_net_gain_percentage = total_net_gain_percentage
        self._total_net_gain = total_net_gain
        self._backtest_data_index_date = backtest_data_index_date
        self._growth_rate = growth_rate
        self._growth = growth
        self._total_value = total_value
        self.positions = positions
        self._average_trade_duration = average_trade_duration
        self._average_trade_size = average_trade_size
        self._trades = trades

    @property
    def portfolio_id(self):
        return self._portfolio_id

    @portfolio_id.setter
    def portfolio_id(self, portfolio_id):
        self._portfolio_id = portfolio_id

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

    @property
    def backtest_data_index_date(self):
        return self._backtest_data_index_date

    @backtest_data_index_date.setter
    def backtest_data_index_date(self, value):
        self._backtest_data_index_date = value

    @property
    def market_data_file(self):
        return self._market_data_file

    @market_data_file.setter
    def market_data_file(self, value):
        self._market_data_file = value

    @property
    def percentage_positive_trades(self):
        return self._percentage_positive_trades

    @percentage_positive_trades.setter
    def percentage_positive_trades(self, value):
        self._percentage_positive_trades = value

    @property
    def percentage_negative_trades(self):
        return self._percentage_negative_trades

    @percentage_negative_trades.setter
    def percentage_negative_trades(self, value):
        self._percentage_negative_trades = value

    @property
    def number_of_trades_closed(self):
        return self._number_of_trades_closed

    @number_of_trades_closed.setter
    def number_of_trades_closed(self, value):
        self._number_of_trades_closed = value

    @property
    def number_of_trades_open(self):
        return self._number_of_trades_open

    @number_of_trades_open.setter
    def number_of_trades_open(self, value):
        self._number_of_trades_open = value

    @property
    def total_cost(self):
        return self._total_cost

    @total_cost.setter
    def total_cost(self, value):
        self._total_cost = value

    @property
    def growth_rate(self):
        return self._growth_rate

    @growth_rate.setter
    def growth_rate(self, value):
        self._growth_rate = value

    @property
    def growth(self):
        return self._growth

    @growth.setter
    def growth(self, value):
        self._growth = value

    @property
    def initial_unallocated(self):
        return self._initial_unallocated

    @initial_unallocated.setter
    def initial_unallocated(self, value):
        self._initial_unallocated = value

    @property
    def trading_symbol(self):
        return self._trading_symbol

    @trading_symbol.setter
    def trading_symbol(self, value):
        self._trading_symbol = value

    @property
    def total_net_gain_percentage(self):
        return self._total_net_gain_percentage

    @total_net_gain_percentage.setter
    def total_net_gain_percentage(self, value):
        self._total_net_gain_percentage = value

    @property
    def total_net_gain(self):
        return self._total_net_gain

    @total_net_gain.setter
    def total_net_gain(self, value):
        self._total_net_gain = value

    @property
    def total_value(self):
        return self._total_value

    @total_value.setter
    def total_value(self, value):
        self._total_value = value

    @property
    def positions(self):
        return self._positions

    @positions.setter
    def positions(self, value):
        self._positions = value

    @property
    def average_trade_duration(self):
        return self._average_trade_duration

    @average_trade_duration.setter
    def average_trade_duration(self, value):
        self._average_trade_duration = value

    @property
    def average_trade_size(self):
        return self._average_trade_size

    @average_trade_size.setter
    def average_trade_size(self, value):
        self._average_trade_size = value

    @property
    def trades(self):
        return self._trades

    @trades.setter
    def trades(self, value):
        self._trades = value

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
            start_date=self.backtest_start_date,
            end_date=self.backtest_end_date,
            backtest_index_date=self.backtest_index_date,
            start_date_data=self.backtest_start_date_data,
            time_unit=self.time_unit,
            interval=self.interval
        )
