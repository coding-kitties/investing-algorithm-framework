from datetime import datetime
from logging import getLogger

from pandas import DataFrame

from investing_algorithm_framework.domain.constants import DATETIME_FORMAT
from investing_algorithm_framework.domain.metrics import \
    get_price_efficiency_ratio
from investing_algorithm_framework.domain.models \
    .backtesting.backtest_date_range import BacktestDateRange
from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.time_unit import TimeUnit

logger = getLogger(__name__)


class BacktestReport(BaseModel):
    """
    Class that represents a backtest report. The backtest report
    contains information about the backtest.
    """

    def __init__(
        self,
        backtest_date_range: BacktestDateRange,
        name=None,
        time_unit=None,
        interval=0,
        strategy_identifiers=None,
        initial_unallocated=0.0,
        number_of_runs=0,
        trading_time_frame=None,
        trading_time_frame_start_date=None,
        symbols=None,
        market=None,
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
        total_net_gain=0.0,
        growth_rate=0.0,
        growth=0.0,
        total_value=0.0,
        positions=None,
        average_trade_duration=0,
        average_trade_size=0.0,
        trades=None,
        orders=None,
        created_at: datetime = None,
        context=None,
    ):
        self._traces = {}
        self.metrics = {}
        self._name = name
        self._strategy_identifiers = strategy_identifiers
        self.backtest_date_range = backtest_date_range
        self._number_of_runs = number_of_runs
        self._trading_time_frame = trading_time_frame
        self._trading_time_frame_start_date = trading_time_frame_start_date
        self._market = market
        self._number_of_orders = number_of_orders
        self._number_of_positions = number_of_positions
        self._market_data_file = market_data_file
        self._percentage_positive_trades = percentage_positive_trades
        self._percentage_negative_trades = percentage_negative_trades
        self._number_of_trades_closed = number_of_trades_closed
        self._number_of_trades_open = number_of_trades_open
        self._total_cost = total_cost
        self._growth_rate = growth_rate
        self._growth = growth
        self._initial_unallocated = initial_unallocated
        self._trading_symbol = trading_symbol
        self._total_net_gain_percentage = total_net_gain_percentage
        self._total_net_gain = total_net_gain
        self._total_value = total_value
        self._positions = positions
        self._orders = orders
        self._average_trade_duration = average_trade_duration
        self._average_trade_size = average_trade_size
        self._trades = trades
        self._created_at: datetime = created_at
        self._interval = interval
        self._time_unit = time_unit
        self._context = context

        self._symbols = symbols

        if self._symbols is None:
            self._symbols = []

        self._number_of_days = \
            (self.backtest_date_range.end_date
             - self.backtest_date_range.start_date).days

    @property
    def name(self):
        return self._name

    @property
    def strategy_identifiers(self):
        return self._strategy_identifiers

    @property
    def created_at(self):
        return self._created_at

    @property
    def portfolio_id(self):
        return self._portfolio_id

    @portfolio_id.setter
    def portfolio_id(self, portfolio_id):
        self._portfolio_id = portfolio_id

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

    @property
    def number_of_days(self):
        return self._number_of_days

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

    @trading_time_frame_start_date.setter
    def trading_time_frame_start_date(self, value):
        self._trading_time_frame_start_date = value

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
        return float(self._percentage_positive_trades)

    @percentage_positive_trades.setter
    def percentage_positive_trades(self, value):
        self._percentage_positive_trades = value

    @property
    def percentage_negative_trades(self):
        return float(self._percentage_negative_trades)

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
    def orders(self):
        return self._orders

    @orders.setter
    def orders(self, value):
        self._orders = value

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

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, value):
        self._interval = value

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        self._context = value

    @property
    def time_unit(self):
        return self._time_unit

    @time_unit.setter
    def time_unit(self, value):
        self._time_unit = value

    def get_runs_per_day(self):

        if self.time_unit is None:
            return 0
        elif TimeUnit.SECOND.equals(self.time_unit):
            return 86400 / self.interval
        elif TimeUnit.MINUTE.equals(self.time_unit):
            return 1440 / self.interval
        else:
            return 24 / self.interval

    @property
    def backtest_start_date(self):
        return self.backtest_date_range.start_date

    @property
    def backtest_end_date(self):
        return self.backtest_date_range.end_date

    def __repr__(self):
        return self.repr(
            name=self.name,
            backtest_date_range=self.backtest_date_range,
            profit=self.get_profit(),
            profit_percentage=self.get_profit_percentage(),
            growth=self.get_growth(),
            growth_percentage=self.get_growth_percentage(),
        )

    def to_dict(self):
        """
        Convert the backtest report to a dictionary. So it can be
        saved to a file.
        """

        # Convert context to a dictionary
        if self.context is not None:

            for key, value in self.context.items():
                if isinstance(value, datetime):
                    self.context[key] = value.strftime(DATETIME_FORMAT)

                if isinstance(value, DataFrame):
                    self.context[key] = value.to_json()

        return {
            "name": self.name,
            "context": self.context if self.context is not None else {},
            "strategy_identifiers": self.strategy_identifiers,
            "backtest_date_range_identifier": self.backtest_date_range.name,
            "backtest_start_date": self.backtest_date_range.start_date
            .strftime(DATETIME_FORMAT),
            "backtest_end_date": self.backtest_date_range.end_date
            .strftime(DATETIME_FORMAT),
            "number_of_runs": self.number_of_runs,
            "symbols": self.symbols,
            "market": self.market,
            "number_of_days": self.number_of_days,
            "number_of_orders": self.number_of_orders,
            "number_of_positions": self.number_of_positions,
            "market_data_file": self.market_data_file,
            "percentage_positive_trades": self.percentage_positive_trades,
            "percentage_negative_trades": self.percentage_negative_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "number_of_trades_open": self.number_of_trades_open,
            "total_cost": self.total_cost,
            "growth_rate": self.growth_rate,
            "growth": self.growth,
            "initial_unallocated": self.initial_unallocated,
            "trading_symbol": self.trading_symbol,
            "total_net_gain_percentage": self.total_net_gain_percentage,
            "total_net_gain": self.total_net_gain,
            "total_value": self.total_value,
            "average_trade_duration": self.average_trade_duration,
            "average_trade_size": self.average_trade_size,
            "positions": [position.to_dict() for position in self.positions],
            "trades": [trade.to_dict() for trade in self.trades],
            "orders": [
                order.to_dict(datetime_format=DATETIME_FORMAT)
                for order in self.orders
            ],
            "created_at": self.created_at.strftime(DATETIME_FORMAT),
        }

    @staticmethod
    def from_dict(data):
        """
        Factory method to create a backtest report from a dictionary.
        """

        backtest_date_range = BacktestDateRange(
            start_date=datetime.strptime(
                data["backtest_start_date"], DATETIME_FORMAT),
            end_date=datetime.strptime(
                data["backtest_end_date"], DATETIME_FORMAT)
        )

        return BacktestReport(
            name=data["name"],
            strategy_identifiers=data["strategy_identifiers"],
            number_of_runs=data["number_of_runs"],
            backtest_date_range=backtest_date_range,
            symbols=data["symbols"],
            market=data["market"],
            number_of_orders=data["number_of_orders"],
            number_of_positions=data["number_of_positions"],
            market_data_file=data["market_data_file"],
            percentage_positive_trades=data["percentage_positive_trades"],
            percentage_negative_trades=data["percentage_negative_trades"],
            number_of_trades_closed=data["number_of_trades_closed"],
            number_of_trades_open=data["number_of_trades_open"],
            total_cost=float(data["total_cost"]),
            growth_rate=float(data["growth_rate"]),
            growth=float(data["growth"]),
            initial_unallocated=float(data["initial_unallocated"]),
            trading_symbol=data["trading_symbol"],
            total_net_gain_percentage=float(data["total_net_gain_percentage"]),
            total_net_gain=float(data["total_net_gain"]),
            total_value=float(data["total_value"]),
            average_trade_duration=data["average_trade_duration"],
            average_trade_size=float(data["average_trade_size"]),
        )

    def get_trades(self, symbol=None):
        """
        Function to get trades. If a symbol is provided, it will
        return the trades for that symbol. If no symbol is provided,
        it will return all the trades.
        """
        if symbol is None:
            return self.trades

        return [trade for trade in self.trades if trade.symbol == symbol]

    def get_profit(self) -> float:
        return self._total_net_gain

    def get_profit_percentage(self) -> float:
        return self._total_net_gain_percentage

    def get_growth(self) -> float:
        return self._growth

    def get_growth_percentage(self) -> float:
        return self._growth_rate

    def get_trading_symbol(self) -> str:
        return self.trading_symbol

    def add_symbol(self, symbol):

        if symbol not in self.symbols:
            self.symbols.append(symbol)

    def calculate_metrics(self):
        """
        Parent method to calculate all metrics.

        returns:
            None
        """
        if self.traces is not None:
            self.metrics['efficiency_ratio'] = {}

            for strategy_id in self.traces:
                entries = self.traces[strategy_id]

                if entries is None:
                    continue

                for symbol in entries:

                    self.metrics['efficiency_ratio'][symbol] = \
                        get_price_efficiency_ratio(
                            self.traces[strategy_id][symbol]
                        )

    @property
    def traces(self):
        """
        Get the traces of the backtest report.
        """
        return self._traces

    @traces.setter
    def traces(self, value):
        """
        Set the traces of the backtest report.

        Args:
            value (dict): The traces of the backtest report.

        returns:
            None
        """
        self._traces = value

    def get_trace(self, symbol, strategy_id=None):
        """
        Get the trace for a given symbol. If a strategy_id is provided,
        it will return the trace for that strategy.

        Args:
            symbol (str): The symbol
            strategy_id (str): The
        """

        if strategy_id is None:

            for strategy_id, trace in self.traces.items():

                if symbol in trace:
                    return trace[symbol]

        else:
            if strategy_id in self.traces:
                return self.traces[strategy_id][symbol]

            else:
                raise ValueError(
                    f"Trace {symbol} for strategy {strategy_id} not found"
                )

        return None
