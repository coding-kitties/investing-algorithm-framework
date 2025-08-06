import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import getLogger
from typing import List, Optional

from investing_algorithm_framework.domain.constants import \
    DEFAULT_DATETIME_FORMAT
from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.order import Order
from investing_algorithm_framework.domain.models.order import OrderSide, \
    OrderStatus
from investing_algorithm_framework.domain.models.portfolio \
    .portfolio_snapshot import PortfolioSnapshot
from investing_algorithm_framework.domain.models.position import Position
from investing_algorithm_framework.domain.models.trade import Trade, \
    TradeStatus
from .backtest_date_range import BacktestDateRange

logger = getLogger(__name__)


@dataclass
class BacktestResult:
    """
    Class that represents a backtest result. The backtest result
    contains information about the trades, positions, portfolio and
    trades of backtest.

    Attributes:
        backtest_date_range (BacktestDateRange): The date range of
            the backtest.
        trading_symbol (str): The trading symbol of the backtest.
        name (str): The name of the backtest.
        initial_unallocated (float): The initial unallocated amount
            of the backtest.
        symbols (List[str]): The symbols of the backtest.
        number_of_runs (int): The number of strategy runs of the backtest.
        portfolio_snapshots (List[PortfolioSnapshot]): The portfolio
            snapshots of the backtest.
        trades (List[Trade]): All trades of the backtest.
        orders (List[Order]): All orders of the backtest.
        positions (List[Position]): All positions of the backtest.
        created_at (Optional[datetime]): The date and time when the
            backtest was created.
        backtest_start_date (Optional[datetime]): The start date of the
            backtest.
        backtest_end_date (Optional[datetime]): The end date of the
            backtest.
        number_of_days (int): The number of days of the backtest.
        number_of_trades (int): The number of trades of the backtest.
        number_of_trades_closed (int): The number of closed trades
            of the backtest.
        number_of_trades_open (int): The number of open trades
            of the backtest.
        percentage_positive_trades (float): The percentage of positive
            trades of the backtest.
        percentage_negative_trades (float): The percentage of negative
            trades of the backtest.
        growth (float): The growth of the backtest.
        growth_percentage (float): The growth percentage of the backtest.
        total_cost (float): The total cost of the backtest.
        total_value (float): The total value of the backtest.
        average_trade_duration (float): The average trade duration
            of the backtest in hours.
        average_trade_size (float): The average trade size of the
            backtest in the trading symbol.
    """
    backtest_date_range: BacktestDateRange
    trading_symbol: str
    name: str
    initial_unallocated: float
    number_of_runs: int
    portfolio_snapshots: List[PortfolioSnapshot]
    trades: List[Trade]
    orders: List[Order]
    positions: List[Position]
    created_at: Optional[datetime] = field(default=None)
    backtest_start_date: Optional[datetime] = field(default=None)
    backtest_end_date: Optional[datetime] = field(default=None)
    symbols: List[str] = field(default_factory=list)
    number_of_days: int = 0
    number_of_trades: int = 0
    number_of_trades_closed: int = 0
    number_of_trades_open: int = 0
    number_of_orders: int = 0
    number_of_positions: int = 0
    percentage_positive_trades: float = 0.0
    percentage_negative_trades: float = 0.0
    growth: float = 0.0
    growth_percentage: float = 0.0
    total_cost: float = 0.0
    total_value: float = 0.0
    average_trade_duration: float = 0.0
    average_trade_size: float = 0.0

    def __post_init__(self):

        if self.created_at is None:
            self.created_at = datetime.now(tz=timezone.utc)

        self.number_of_days = (
            self.backtest_date_range.end_date
            - self.backtest_date_range.start_date
        ).days
        self.backtest_start_date = self.backtest_date_range.start_date
        self.backtest_end_date = self.backtest_date_range.end_date

        if len(self.portfolio_snapshots) < 2:
            raise OperationalException(
                "Backtest result must have at least 2 portfolio snapshots " +
                "One for the initial state and one for the final state."
            )

        self.growth = self.portfolio_snapshots[-1].total_value \
            - self.portfolio_snapshots[0].total_value
        self.growth_percentage = self.growth / self.initial_unallocated * 100.0
        self.number_of_orders = \
            len(self.orders) if self.orders is not None else 0
        self.number_of_positions = \
            len(self.positions) if self.positions is not None else 0
        last_portfolio_snapshot = \
            self.portfolio_snapshots[-1] if self.portfolio_snapshots else None
        self.total_value = last_portfolio_snapshot.total_value \
            if last_portfolio_snapshot is not None else 0.0

        number_of_negative_trades = 0.0
        number_of_positive_trades = 0.0
        number_of_trades_closed = 0
        number_of_trades_open = 0
        total_duration = 0
        total_trade_size = 0.0

        if self.trades is not None:
            for trade in self.trades:
                self.total_cost += trade.cost
                total_duration += \
                    ((trade.closed_at - trade.opened_at).total_seconds() /
                     3600) if trade.closed_at else 0
                total_trade_size += trade.size
                if trade.status == TradeStatus.CLOSED.value:
                    number_of_trades_closed += 1

                if trade.status == TradeStatus.OPEN.value:
                    number_of_trades_open += 1

                if trade.net_gain > 0:
                    number_of_positive_trades += 1
                elif trade.net_gain < 0:
                    number_of_negative_trades += 1

            self.percentage_positive_trades = \
                (number_of_positive_trades / len(self.trades)) * 100.0 \
                if len(self.trades) > 0 else 0.0
            self.percentage_negative_trades = \
                (number_of_negative_trades / len(self.trades)) * 100.0 \
                if len(self.trades) > 0 else 0.0
            self.number_of_trades_closed = number_of_trades_closed
            self.number_of_trades_open = number_of_trades_open
            self.number_of_trades = len(self.trades)
            self.average_trade_duration = \
                total_duration / self.number_of_trades \
                if self.number_of_trades > 0 else 0.0
            self.average_trade_size = \
                total_trade_size / self.number_of_trades \
                if self.number_of_trades > 0 else 0.0

        # Determine all the symbols that are being traded in the backtest
        if self.symbols is None:
            self.symbols = []

            for order in self.orders:
                if order.target_symbol not in self.symbols:
                    self.symbols.append(order.target_symbol)

    def to_dict(self, datetime_format=DEFAULT_DATETIME_FORMAT):
        """
        Convert the backtest report to a dictionary. So it can be
        saved to a file.

        Returns:
            dict: The backtest report as a dictionary
        """

        return {
            "name": self.name,
            "backtest_date_range_identifier": self.backtest_date_range.name,
            "backtest_start_date": self.backtest_date_range.start_date
            .strftime(datetime_format),
            "backtest_end_date": self.backtest_date_range.end_date
            .strftime(datetime_format),
            "number_of_runs": self.number_of_runs,
            "symbols": self.symbols,
            "number_of_days": self.number_of_days,
            "number_of_orders": self.number_of_orders,
            "number_of_positions": self.number_of_positions,
            "percentage_positive_trades": self.percentage_positive_trades,
            "percentage_negative_trades": self.percentage_negative_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "number_of_trades_open": self.number_of_trades_open,
            "total_cost": self.total_cost,
            "growth_percentage": self.growth_percentage,
            "growth": self.growth,
            "initial_unallocated": self.initial_unallocated,
            "trading_symbol": self.trading_symbol,
            "total_value": self.total_value,
            "average_trade_duration": self.average_trade_duration,
            "average_trade_size": self.average_trade_size,
            # "positions": [position.to_dict() for position in self.positions],
            "trades": [
                trade.to_dict(datetime_format=datetime_format)
                for trade in self.trades
            ],
            "orders": [
                order.to_dict(datetime_format=datetime_format)
                for order in self.orders
            ],
            "portfolio_snapshots": [
                snapshot.to_dict(datetime_format=datetime_format)
                for snapshot in self.portfolio_snapshots
            ],
            "created_at": self.created_at.strftime(datetime_format),
        }

    @staticmethod
    def from_dict(data, datetime_format=DEFAULT_DATETIME_FORMAT):
        """
        Factory method to create a backtest report from a dictionary.
        """
        backtest_date_range = BacktestDateRange(
            start_date=datetime.strptime(
                data["backtest_start_date"], datetime_format
            ),
            end_date=datetime.strptime(
                data["backtest_end_date"], datetime_format
            )
        )
        portfolio_snapshots_data = data.get("portfolio_snapshots", None)

        if portfolio_snapshots_data is None:
            portfolio_snapshots = []
        else:
            portfolio_snapshots = [
                PortfolioSnapshot.from_dict(snapshot)
                for snapshot in portfolio_snapshots_data
            ]

        positions_data = data.get("positions", None)

        if positions_data is not None:
            positions = [
                Position.from_dict(position) for position in positions_data
            ]
        else:
            positions = []

        trades_data = data.get("trades", None)

        if trades_data is not None:
            trades = [Trade.from_dict(trade) for trade in trades_data]
        else:
            trades = []

        orders_data = data.get("orders", None)

        if orders_data is not None:
            orders = [Order.from_dict(order) for order in orders_data]
        else:
            orders = []

        report = BacktestResult(
            name=data["name"],
            number_of_runs=data["number_of_runs"],
            backtest_date_range=backtest_date_range,
            symbols=data["symbols"],
            number_of_orders=data["number_of_orders"],
            number_of_positions=data["number_of_positions"],
            percentage_positive_trades=data["percentage_positive_trades"],
            percentage_negative_trades=data["percentage_negative_trades"],
            number_of_trades_closed=data["number_of_trades_closed"],
            number_of_trades_open=data["number_of_trades_open"],
            total_cost=float(data["total_cost"]),
            growth_percentage=float(data["growth_percentage"]),
            growth=float(data["growth"]),
            initial_unallocated=float(data["initial_unallocated"]),
            trading_symbol=data["trading_symbol"],
            total_value=float(data["total_value"]),
            average_trade_duration=data["average_trade_duration"],
            average_trade_size=float(data["average_trade_size"]),
            created_at=datetime.strptime(
                data["created_at"], datetime_format
            ),
            backtest_start_date=datetime.strptime(
                data["backtest_start_date"], datetime_format
            ),
            backtest_end_date=datetime.strptime(
                data["backtest_end_date"], datetime_format
            ),
            number_of_days=data["number_of_days"],
            portfolio_snapshots=portfolio_snapshots,
            # position_snapshots=position_snapshots,
            trades=trades,
            orders=orders,
            positions=positions,
        )

        return report

    def get_orders(
        self,
        target_symbol=None,
        order_side=None,
        order_status=None,
        created_at_lt=None,
    ) -> List[Order]:
        """
        Get the orders of a backtest report

        Args:
            target_symbol (str): The target_symbol
            order_side (str): The order side
            status (str): The order status
            created_at_lt (datetime): The created_at date to filter the orders

        Returns:
            list: The orders of the backtest report
        """
        selection = self.orders

        if created_at_lt is not None:
            selection = [
                order for order in selection
                if order.created_at < created_at_lt
            ]

        if target_symbol is not None:
            selection = [
                order for order in selection
                if order.target_symbol == target_symbol
            ]

        if order_side is not None:
            order_side = OrderSide.from_value(order_side)
            selection = [
                order for order in selection
                if order.order_side == order_side.value
            ]

        if order_status is not None:
            status = OrderStatus.from_value(order_status)
            selection = [
                order for order in selection
                if order.status == status.value
            ]

        return selection

    def get_trades(self, target_symbol=None, trade_status=None) -> List[Trade]:
        """
        Get the trades of a backtest report

        Args:
            target_symbol (str): The target_symbol
            trade_status: The trade_status

        Returns:
            list: The trades of the backtest report
        """
        selection = self.trades

        if target_symbol is not None:
            selection = [
                trade for trade in selection
                if trade.target_symbol == target_symbol
            ]

        if trade_status is not None:
            trade_status = TradeStatus.from_value(trade_status)
            selection = [
                trade for trade in selection
                if trade.status == trade_status.value
            ]

        return selection

    def get_positions(self, symbol=None) -> List[Position]:
        """
        Get the positions of the backtest report

        Args:
            symbol (str): The symbol

        Returns:
            list: The positions of the backtest report
        """

        # Get the last portfolio snapshot
        last_portfolio_snapshot = \
            self.portfolio_snapshots[-1] if self.portfolio_snapshots else None
        selection = []

        if last_portfolio_snapshot is not None:
            positions = last_portfolio_snapshot.position_snapshots

            if symbol is not None:
                selection = [
                    position for position in positions
                    if position.symbol == symbol
                ]

            return selection

        return selection

    def get_portfolio_snapshots(
        self,
        created_at_lt: Optional[datetime] = None
    ) -> List[PortfolioSnapshot]:
        """
        Get the portfolio snapshots of the backtest report

        Args:
            created_at_lt (datetime): The created_at date to filter
                the snapshots

        Returns:
            list: The portfolio snapshots of the backtest report
        """
        selection = self.portfolio_snapshots

        if created_at_lt is not None:
            selection = [
                snapshot for snapshot in selection
                if snapshot.created_at < created_at_lt
            ]

        return selection

    def save(self, directory_path: str):
        """
        Save the backtest results to a file. When saving the backtest results,
        it will save the following files and directories:

        - results.json: The backtest results in JSON format.
        - metrics.json: The metrics of the backtest report in JSON format.
        - strategy_directory: A directory containing the strategy files
            used in the backtest report.
        - data_files: A directory containing the data files used in the
            backtest report.
        Args:
            path (str): The path to save the backtest report to.
        """

        path = f"{directory_path}/results.json"
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=4, default=str)
            logger.info(f"Backtest results saved to {path}")

    @staticmethod
    def open(file_path: str) -> 'BacktestResult':
        """
        Open a backtest result from a file.

        Args:
            file_path (str): The path to the file to open.

        Raises:
            OperationalException: If the file does not exist or is not a valid
                backtest result file.

        Returns:
            BacktestResult: The backtest result.
        """

        if not file_path.endswith('.json'):
            raise OperationalException(
                f"File {file_path} is not a valid backtest result file. "
                "It must be a JSON file."
            )

        # Check if the file exists
        if not os.path.isfile(file_path):
            raise OperationalException(
                f"The file {file_path} does not exist."
            )

        with open(file_path, 'r') as f:
            data = json.load(f)
            return BacktestResult.from_dict(data)
