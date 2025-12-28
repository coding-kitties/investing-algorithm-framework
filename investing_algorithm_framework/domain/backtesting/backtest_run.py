import json
import os
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from logging import getLogger
from typing import Union, List, Optional, Dict

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
from investing_algorithm_framework.domain.models.trade.trade_stop_loss import \
    TradeStopLoss
from investing_algorithm_framework.domain.models.trade.trade_take_profit \
    import TradeTakeProfit


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
    initial_unallocated: float = 0.0
    number_of_runs: int = 0
    portfolio_snapshots: List[PortfolioSnapshot] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    orders: List[Order] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    created_at: datetime = None,
    symbols: List[str] = field(default_factory=list)
    number_of_days: int = 0
    number_of_trades: int = 0
    number_of_trades_closed: int = 0
    number_of_trades_open: int = 0
    number_of_orders: int = 0
    number_of_positions: int = 0
    backtest_metrics: BacktestMetrics = None
    backtest_date_range_name: str = None
    data_sources: List[Dict] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """
        Convert the Backtest instance to a dictionary with all
        date/datetime fields as ISO strings (always UTC).
        """
        def ensure_iso(value):
            if hasattr(value, "isoformat"):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
            return value

        backtest_metrics = self.backtest_metrics.to_dict() \
            if self.backtest_metrics else None
        return {
            "backtest_metrics": backtest_metrics,
            "backtest_start_date": ensure_iso(self.backtest_start_date),
            "backtest_date_range_name": self.backtest_date_range_name,
            "backtest_end_date": ensure_iso(self.backtest_end_date),
            "trading_symbol": self.trading_symbol,
            "initial_unallocated": self.initial_unallocated,
            "number_of_runs": self.number_of_runs,
            "portfolio_snapshots": [
                ps.to_dict() for ps in self.portfolio_snapshots
            ],
            "trades": [trade.to_dict() for trade in self.trades],
            "orders": [order.to_dict() for order in self.orders],
            "positions": [position.to_dict() for position in self.positions],
            "created_at": ensure_iso(self.created_at),
            "symbols": self.symbols,
            "number_of_days": self.number_of_days,
            "number_of_trades": self.number_of_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "number_of_trades_open": self.number_of_trades_open,
            "number_of_orders": self.number_of_orders,
            "number_of_positions": self.number_of_positions,
            "metadata": self.metadata,
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
            with open(run_file, 'r') as f:
                data = json.load(f)
        else:
            raise OperationalException(
                f"The run file {run_file} does not exist."
            )

        # Validate and set defaults for required fields
        required_fields = {
            "backtest_start_date": "2020-01-01 00:00:00",
            "backtest_end_date": "2020-01-02 00:00:00",
            "created_at": "2020-01-01 00:00:00",
            "trading_symbol": "USD",
            "initial_unallocated": 1000.0,
            "number_of_runs": 1
        }

        for field_name, default_value in required_fields.items():
            if field_name not in data:
                logger.warning(f"Missing required field '{field_name}' in "
                               f"backtest data, using "
                               f"default: {default_value}")
                data[field_name] = default_value

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
        # Convert all to utc timezone
        data["backtest_start_date"] = data[
            "backtest_start_date"].replace(tzinfo=timezone.utc)
        data["backtest_end_date"] = data[
            "backtest_end_date"].replace(tzinfo=timezone.utc)
        data["created_at"] = data["created_at"].replace(tzinfo=timezone.utc)

        # Parse orders with error handling
        orders = []
        for order_data in data.get("orders", []):
            try:
                order = Order.from_dict(order_data)
                orders.append(order)
            except KeyError as e:
                logger.error(f"Failed to parse order "
                             f"data, missing field {e}: {order_data}")
                continue
            except Exception as e:
                logger.error(f"Failed to parse order data: {e}")
                continue
        data["orders"] = orders

        # Parse positions with error handling
        positions = []
        for position_data in data.get("positions", []):
            try:
                position = Position.from_dict(position_data)
                positions.append(position)
            except KeyError as e:
                logger.error(f"Failed to parse position data, "
                             f"missing field {e}: {position_data}")
                continue
            except Exception as e:
                logger.error(f"Failed to parse position data: {e}")
                continue
        data["positions"] = positions

        # Parse trades with error handling
        trades = []
        for trade_data in data.get("trades", []):
            try:
                trade = Trade.from_dict(trade_data)
                trades.append(trade)
            except KeyError as e:
                logger.error(f"Failed to parse trade data, "
                             f"missing field {e}: {trade_data}")
                # Skip this trade and continue with the next one
                continue
            except Exception as e:
                logger.error(f"Failed to parse trade data: {e}")
                continue
        data["trades"] = trades

        # Parse portfolio snapshots with error handling
        portfolio_snapshots = []
        for ps_data in data.get("portfolio_snapshots", []):
            try:
                ps = PortfolioSnapshot.from_dict(ps_data)
                portfolio_snapshots.append(ps)
            except KeyError as e:
                logger.error(f"Failed to parse portfolio snapshot data, "
                             f"missing field {e}: {ps_data}")
                continue
            except Exception as e:
                logger.error(f"Failed to parse portfolio snapshot data: {e}")
                continue
        data["portfolio_snapshots"] = portfolio_snapshots

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

            # Ensure datetime objects are in UTC before formatting
            backtest_start_date = self.backtest_start_date

            if backtest_start_date.tzinfo is None:
                # Naive datetime - treat as UTC
                backtest_start_date = backtest_start_date.replace(
                    tzinfo=timezone.utc
                )
            else:
                # Timezone-aware - convert to UTC
                backtest_start_date = backtest_start_date.astimezone(
                    timezone.utc
                )

            backtest_end_date = self.backtest_end_date
            if backtest_end_date.tzinfo is None:
                backtest_end_date = backtest_end_date.replace(
                    tzinfo=timezone.utc
                )
            else:
                backtest_end_date = backtest_end_date.astimezone(timezone.utc)

            created_at = self.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)

            data["backtest_start_date"] = backtest_start_date.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            data["backtest_end_date"] = backtest_end_date.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            data["created_at"] = created_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            json.dump(data, f, default=str)

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """
        Get a trade by its ID from the backtest report

        Args:
            trade_id (str): The trade ID

        Returns:
            Trade: The trade with the given ID, or None if not found
        """
        for trade in self.trades:
            if trade.trade_id == trade_id:
                return trade

        return None

    def get_trades(
        self,
        target_symbol: str = None,
        trade_status: Union[TradeStatus, str] = None,
        opened_at: datetime = None,
        opened_at_lt: datetime = None,
        opened_at_lte: datetime = None,
        opened_at_gt: datetime = None,
        opened_at_gte: datetime = None,
        order_id: str = None
    ) -> List[Trade]:
        """
        Get the trades of a backtest report

        Args:
            target_symbol (str): The target_symbol
            trade_status (Union[TradeStatus, str]): The trade status
            opened_at (datetime): The created_at date to filter the trades
            opened_at_lt (datetime): The created_at date to filter the trades
            opened_at_lte (datetime): The created_at date to filter the trades
            opened_at_gt (datetime): The created_at date to filter the trades
            opened_at_gte (datetime): The created_at date to filter the trades
            order_id (str): The order ID to filter the trades

        Returns:
            list: The trades of the backtest report
        """
        selection = self.trades

        if target_symbol is not None:
            selection = [
                trade for trade in selection
                if trade.target_symbol.lower() == target_symbol.lower()
            ]

        if trade_status is not None:
            trade_status = TradeStatus.from_value(trade_status)
            selection = [
                trade for trade in selection
                if trade.status == trade_status.value
            ]

        if opened_at is not None:
            selection = [
                trade for trade in selection
                if trade.opened_at == opened_at
            ]

        if opened_at_lt is not None:
            selection = [
                trade for trade in selection
                if trade.opened_at < opened_at_lt
            ]

        if opened_at_lte is not None:
            selection = [
                trade for trade in selection
                if trade.opened_at <= opened_at_lte
            ]

        if opened_at_gt is not None:
            selection = [
                trade for trade in selection
                if trade.opened_at > opened_at_gt
            ]

        if opened_at_gte is not None:
            selection = [
                trade for trade in selection
                if trade.opened_at >= opened_at_gte
            ]

        if order_id is not None:
            new_selection = []
            for trade in selection:

                for order in trade.orders:
                    if order.order_id == order_id:
                        new_selection.append(trade)
                        break

            selection = new_selection

        return selection

    def get_stop_losses(
        self,
        trade_id: str = None,
        triggered: bool = None
    ) -> List[TradeStopLoss]:
        """
        Get the stop losses of the backtest report

        Args:
            trade_id (str): The trade ID to filter the stop losses
            triggered (bool): Whether to filter by triggered stop losses

        Returns:
            list: The stop losses of the backtest report
        """
        stop_losses = []

        for trade in self.trades:
            if trade_id is not None and trade.id != trade_id:
                continue

            for sl in trade.stop_losses:
                if isinstance(sl, TradeStopLoss):
                    if triggered is not None:
                        if sl.triggered == triggered:
                            stop_losses.append(sl)
                    else:
                        stop_losses.append(sl)

        return stop_losses

    def get_take_profits(
        self,
        trade_id: str = None,
        triggered: bool = None
    ) -> List[TradeStopLoss]:
        """
        Get the take profits of the backtest report

        Args:
            trade_id (str): The trade ID to filter the take profits
            triggered (bool): Whether to filter by triggered take profits

        Returns:
            list: The take profits of the backtest report
        """
        take_profits = []

        for trade in self.trades:
            if trade_id is not None and trade.id != trade_id:
                continue

            for tp in trade.take_profits:
                if isinstance(tp, TradeTakeProfit):
                    if triggered is not None:
                        if tp.triggered == triggered:
                            take_profits.append(tp)
                    else:
                        take_profits.append(tp)

        return take_profits

    def get_portfolio_snapshots(
        self,
        created_at_lt: Optional[datetime] = None,
        created_at_lte: Optional[datetime] = None,
        created_at_gt: Optional[datetime] = None,
        created_at_gte: Optional[datetime] = None
    ) -> List[PortfolioSnapshot]:
        """
        Get the portfolio snapshots of the backtest report

        Args:
            created_at_lt (datetime): The created_at date to filter
                the snapshots
            created_at_lte (datetime): The created_at date to filter
                the snapshots
            created_at_gt (datetime): The created_at date to filter
                the snapshots
            created_at_gte (datetime): The created_at date to filter
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

        if created_at_lte is not None:
            selection = [
                snapshot for snapshot in selection
                if snapshot.created_at <= created_at_lte
            ]

        if created_at_gt is not None:
            selection = [
                snapshot for snapshot in selection
                if snapshot.created_at > created_at_gt
            ]

        if created_at_gte is not None:
            selection = [
                snapshot for snapshot in selection
                if snapshot.created_at >= created_at_gte
            ]

        return selection

    def get_orders(
        self,
        target_symbol: str = None,
        order_side: str = None,
        order_status: Union[OrderStatus, str] = None,
        created_at: datetime = None,
        created_at_lt: datetime = None,
        created_at_lte: datetime = None,
        created_at_gt: datetime = None,
        created_at_gte: datetime = None
    ) -> List[Order]:
        """
        Get the orders of a backtest report

        Args:
            target_symbol (str): The target_symbol
            order_side (str): The order side
            order_status (Union[OrderStatus, str]): The order status
            created_at (datetime): The created_at date to filter the orders
            created_at_lt (datetime): The created_at date to filter the orders
            created_at_lte (datetime): The created_at date to filter the orders
            created_at_gt (datetime): The created_at date to filter the orders
            created_at_gte (datetime): The created_at date to filter the orders

        Returns:
            list: The orders of the backtest report
        """
        selection = self.orders

        if created_at is not None:
            selection = [
                order for order in selection
                if order.created_at == created_at
            ]

        if created_at_lt is not None:
            selection = [
                order for order in selection
                if order.created_at < created_at_lt
            ]

        if created_at_lte is not None:
            selection = [
                order for order in selection
                if order.created_at <= created_at_lte
            ]

        if created_at_gt is not None:
            selection = [
                order for order in selection
                if order.created_at > created_at_gt
            ]

        if created_at_gte is not None:
            selection = [
                order for order in selection
                if order.created_at >= created_at_gte
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
