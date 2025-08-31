import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from logging import getLogger
from typing import Union, List, Optional

from investing_algorithm_framework.domain.exceptions \
    import OperationalException
from investing_algorithm_framework.domain.models.order import Order, \
    OrderSide, OrderStatus
from investing_algorithm_framework.domain.models.position import Position
from investing_algorithm_framework.domain.models.trade import Trade
from investing_algorithm_framework.domain.models.portfolio import \
    PortfolioSnapshot
from investing_algorithm_framework.domain.models.trade.trade_status import \
    TradeStatus


from .backtest_metrics import BacktestMetrics


logger = getLogger(__name__)


@dataclass
class BacktestRun:
    """
    Represents a backtest of an algorithm. It contains the backtest metrics,
    backtest results, and paths to strategy and data files.

    Attributes:
        backtest_metrics (Optional[List[BacktestMetrics]]): A list of
            backtest metrics objects, each representing the performance
            metrics of a single backtest run.
        backtest_start_date (datetime): The start date of the backtest.
        backtest_end_date (datetime): The end date of the backtest.
        backtest_date_range_name (str): The name of the date range used for
            the backtest.
        trading_symbol (str): The trading symbol used in the backtest.
        initial_unallocated (float): The initial unallocated amount in the
            backtest.
        number_of_runs (int): The number of runs in the backtest.
        portfolio_snapshots (List[PortfolioSnapshot]): A list of portfolio
            snapshots taken during the backtest.
        trades (List[Trade]): A list of trades executed during the backtest.
        orders (List[Order]): A list of orders placed during the backtest.
        positions (List[Position]): A list of positions held during the
            backtest.
        created_at (datetime): The date and time when the backtest was created.
        symbols (List[str]): A list of trading symbols involved in
            the backtest.
        number_of_days (int): The total number of days the backtest ran.
        number_of_trades (int): The total number of trades executed during
            the backtest.
        number_of_trades_closed (int): The total number of trades that were
            closed during the backtest.
        number_of_trades_open (int): The total number of trades that are
            still open at the end of the backtest.
        number_of_orders (int): The total number of orders placed during
            the backtest.
        number_of_positions (int): The total number of positions held
            during the backtest.
    """
    backtest_start_date: datetime
    backtest_end_date: datetime
    trading_symbol: str
    initial_unallocated: float
    number_of_runs: int
    portfolio_snapshots: List[PortfolioSnapshot]
    trades: List[Trade]
    orders: List[Order]
    positions: List[Position]
    created_at: datetime
    symbols: List[str] = field(default_factory=list)
    number_of_days: int = 0
    number_of_trades: int = 0
    number_of_trades_closed: int = 0
    number_of_trades_open: int = 0
    number_of_orders: int = 0
    number_of_positions: int = 0
    backtest_metrics: BacktestMetrics = None
    backtest_date_range_name: str = None

    def to_dict(self) -> dict:
        """
        Convert the Backtest instance to a dictionary.

        Returns:
            dict: A dictionary representation of the Backtest instance.
        """
        backtest_metrics = self.backtest_metrics.to_dict() \
            if self.backtest_metrics else None
        return {
            "backtest_metrics": backtest_metrics,
            "backtest_start_date": self.backtest_start_date,
            "backtest_date_range_name": self.backtest_date_range_name,
            "backtest_end_date": self.backtest_end_date,
            "trading_symbol": self.trading_symbol,
            "initial_unallocated": self.initial_unallocated,
            "number_of_runs": self.number_of_runs,
            "portfolio_snapshots": [
                ps.to_dict() for ps in self.portfolio_snapshots
            ],
            "trades": [trade.to_dict() for trade in self.trades],
            "orders": [order.to_dict() for order in self.orders],
            "positions": [position.to_dict() for position in self.positions],
            "created_at": self.created_at,
            "symbols": self.symbols,
            "number_of_days": self.number_of_days,
            "number_of_trades": self.number_of_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "number_of_trades_open": self.number_of_trades_open,
            "number_of_orders": self.number_of_orders,
            "number_of_positions": self.number_of_positions
        }

    @staticmethod
    def open(directory_path: Union[str, Path]) -> 'BacktestRun':
        """
        Open a backtest report from a directory and return a Backtest instance.

        Args:
            directory_path (str): The path to the directory containing the
                backtest report files.

        Returns:
            Backtest: An instance of Backtest with the loaded metrics
                and results.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error loading the files.
        """
        backtest_metrics = None

        if not os.path.exists(directory_path):
            raise OperationalException(
                f"The directory {directory_path} does not exist."
            )

        # Load combined backtest metrics
        metrics_file = os.path.join(directory_path, "metrics.json")

        if os.path.isfile(metrics_file):
            backtest_metrics = BacktestMetrics.open(metrics_file)

        # Load backtest results
        run_file = os.path.join(directory_path, "run.json")

        if os.path.isfile(run_file):
            data = json.load(open(run_file, 'r'))

        # Parse datetime fields
        data["backtest_start_date"] = datetime.strptime(
            data["backtest_start_date"], "%Y-%m-%d %H:%M:%S"
        )
        data["backtest_end_date"] = datetime.strptime(
            data["backtest_end_date"], "%Y-%m-%d %H:%M:%S"
        )
        data["created_at"] = datetime.strptime(
            data["created_at"], "%Y-%m-%d %H:%M:%S"
        )

        # Parse orders
        data["orders"] = [
            Order.from_dict(order) for order in data.get("orders", [])
        ]

        # Parse positions
        data["positions"] = [
            Position.from_dict(position)
            for position in data.get("positions", [])
        ]

        # Parse trades
        data["trades"] = [
            Trade.from_dict(trade) for trade in data.get("trades", [])
        ]

        # Parse portfolio snapshots
        data["portfolio_snapshots"] = [
            PortfolioSnapshot.from_dict(ps)
            for ps in data.get("portfolio_snapshots", [])
        ]

        return BacktestRun(
            backtest_metrics=backtest_metrics,
            **data
        )

    def create_directory_name(self) -> str:
        """
        Create a directory name for the backtest run based on its attributes.

        Returns:
            str: A string representing the directory name.
        """
        start_str = self.backtest_start_date.strftime("%Y%m%d")
        end_str = self.backtest_end_date.strftime("%Y%m%d")
        dir_name = f"backtest_{self.trading_symbol}_{start_str}_{end_str}"
        return dir_name

    def save(self, directory_path: Union[str, Path]) -> None:
        """
        Save the backtest run to a directory.

        Args:
            directory_path (str): The directory where the metrics
            file will be saved.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error saving the files.

        Returns:
            None: This method does not return anything, it saves the
            metrics to a file.
        """

        metrics_path = os.path.join(directory_path, "metrics.json")
        run_path = os.path.join(directory_path, "run.json")

        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        # Call the save method of BacktestMetrics
        if self.backtest_metrics:
            self.backtest_metrics.save(metrics_path)

        # Save the run data
        with open(run_path, 'w') as f:
            # string format datetime objects
            data = self.to_dict()

            # Remove backtest_metrics to avoid redundancy
            data.pop("backtest_metrics", None)

            data["backtest_start_date"] = self.backtest_start_date.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            data["backtest_end_date"] = self.backtest_end_date.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            data["created_at"] = self.created_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            json.dump(data, f, default=str)

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
            order_status (str): The order status
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

    def __repr__(self):
        """
        Return a string representation of the Backtest instance.

        Returns:
            str: A string representation of the Backtest instance.
        """
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
