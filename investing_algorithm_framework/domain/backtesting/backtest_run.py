import json
import os
from dataclasses import dataclass, field, fields as dc_fields
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)
from investing_algorithm_framework.domain.models.order import (
    Order,
    OrderSide,
    OrderStatus,
)
from investing_algorithm_framework.domain.models.portfolio import (
    PortfolioSnapshot,
)
from investing_algorithm_framework.domain.models.position import Position
from investing_algorithm_framework.domain.models.trade import Trade
from investing_algorithm_framework.domain.models.trade.trade_status import (
    TradeStatus,
)
from investing_algorithm_framework.domain.models.trade.trade_stop_loss import (
    TradeStopLoss,
)
from investing_algorithm_framework.domain.models.trade.trade_take_profit import (
    TradeTakeProfit,
)

from .backtest_date_range import BacktestDateRange
from .backtest_metrics import BacktestMetrics
from .backtest_window import BacktestWindow


logger = getLogger(__name__)


def _ensure_utc_iso(value: Any) -> Any:
    """Return an ISO-8601 UTC string for a datetime, or the value unchanged."""
    if not hasattr(value, "isoformat"):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a datetime from an ISO-8601 string, returning UTC-aware output."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return value
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialise_signals(
    signals: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, List[Any]]]:
    """Flatten pandas Series signal payloads into ISO date lists."""
    out: Dict[str, Dict[str, List[Any]]] = {}
    for symbol, sig_data in signals.items():
        out[symbol] = {}
        for sig_type, series in sig_data.items():
            if hasattr(series, "iloc"):
                out[symbol][sig_type] = [
                    _ensure_utc_iso(ts)
                    for ts, val in zip(series.index, series)
                    if val
                ]
            else:
                out[symbol][sig_type] = series
    return out


def _serialise_signal_events(
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for evt in events:
        entry = dict(evt)
        if "date" in entry:
            entry["date"] = _ensure_utc_iso(entry["date"])
        out.append(entry)
    return out


def _serialise_recorded_values(
    recorded: Dict[str, List],
) -> Dict[str, List[Dict[str, Any]]]:
    return {
        key: [
            {"datetime": _ensure_utc_iso(dt), "value": val}
            for dt, val in entries
        ]
        for key, entries in recorded.items()
    }


def _deserialise_signal_events(
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for evt in events:
        entry = dict(evt)
        raw = entry.get("date")
        if isinstance(raw, str):
            entry["date"] = _parse_datetime(raw)
        out.append(entry)
    return out


def _deserialise_recorded_values(
    raw: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List]:
    out: Dict[str, List] = {}
    for key, entries in raw.items():
        parsed = []
        for entry in entries:
            dt = entry.get("datetime")
            if isinstance(dt, str):
                dt = _parse_datetime(dt)
            parsed.append((dt, entry.get("value")))
        out[key] = parsed
    return out


def _rehydrate_backtest_window(raw: Any) -> BacktestWindow:
    """Reconstruct a :class:`BacktestWindow` from a ``to_dict`` payload."""
    if isinstance(raw, BacktestWindow):
        return raw
    if not isinstance(raw, dict):
        raise OperationalException(
            "BacktestRun data must include a 'backtest_window' key."
        )

    tr = raw.get("train_range") or {}
    train_range = BacktestDateRange(
        start_date=_parse_datetime(tr.get("start")),
        end_date=_parse_datetime(tr.get("end")),
        name=tr.get("name"),
    )
    te = raw.get("test_range")
    test_range = (
        BacktestDateRange(
            start_date=_parse_datetime(te.get("start")),
            end_date=_parse_datetime(te.get("end")),
            name=te.get("name"),
        )
        if te is not None
        else None
    )
    return BacktestWindow(
        train_range=train_range,
        test_range=test_range,
        warmup_days=raw.get("warmup_days", 0),
        fold_index=raw.get("fold_index"),
        name=raw.get("name"),
    )


@dataclass
class BacktestRun:
    """One execution of an algorithm over a single :class:`BacktestWindow`.

    Mirrors the on-disk shape documented in
    ``docs/architecture/backtest/open_backtest_format.md`` §Run structure.
    The window's *active range* (``test_range`` when present, else
    ``train_range``) drives the derived date fields and
    :pyattr:`window_role`; the full parent window stays accessible on
    :pyattr:`backtest_window` for consumers that need the training
    portion of a walk-forward run.
    """

    backtest_window: BacktestWindow
    initial_unallocated: float = 0.0
    created_at: Optional[datetime] = None
    number_of_runs: int = 1
    number_of_days: int = 0
    number_of_hours: int = 0
    backtest_metrics: Optional[BacktestMetrics] = None
    portfolio_snapshots: List[PortfolioSnapshot] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    orders: List[Order] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    number_of_trades: int = 0
    number_of_trades_closed: int = 0
    number_of_trades_open: int = 0
    number_of_orders: int = 0
    number_of_positions: int = 0
    data_sources: List[Dict] = field(default_factory=list)
    signals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    signal_events: List[Dict[str, Any]] = field(default_factory=list)
    recorded_values: Dict[str, List] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Derived active-range fields
    # ------------------------------------------------------------------

    @property
    def _active_range(self) -> BacktestDateRange:
        window = self.backtest_window
        return (
            window.test_range
            if window.test_range is not None
            else window.train_range
        )

    @property
    def backtest_start_date(self) -> datetime:
        """Start of the active range (``test_range`` if set, else ``train_range``)."""
        return self._active_range.start_date

    @property
    def backtest_end_date(self) -> datetime:
        """End of the active range."""
        return self._active_range.end_date

    @property
    def backtest_date_range_name(self) -> Optional[str]:
        """Name of the active range; the join key back to the study's windows."""
        return self._active_range.name

    @property
    def window_role(self) -> str:
        """``"test"`` for OOS runs, ``"train"`` for in-sample-only fits."""
        return (
            "test"
            if self.backtest_window.test_range is not None
            else "train"
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict matching OBTF §Run structure."""
        return {
            "backtest_window": self.backtest_window.to_dict(),
            "backtest_start_date": _ensure_utc_iso(self.backtest_start_date),
            "backtest_end_date": _ensure_utc_iso(self.backtest_end_date),
            "backtest_date_range_name": self.backtest_date_range_name,
            "window_role": self.window_role,
            "initial_unallocated": self.initial_unallocated,
            "created_at": _ensure_utc_iso(self.created_at),
            "number_of_runs": self.number_of_runs,
            "number_of_days": self.number_of_days,
            "number_of_hours": self.number_of_hours,
            "backtest_metrics": (
                self.backtest_metrics.to_dict()
                if self.backtest_metrics is not None
                else None
            ),
            "portfolio_snapshots": [
                ps.to_dict() for ps in self.portfolio_snapshots
            ],
            "trades": [t.to_dict() for t in self.trades],
            "orders": [o.to_dict() for o in self.orders],
            "positions": [p.to_dict() for p in self.positions],
            "number_of_trades": self.number_of_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "number_of_trades_open": self.number_of_trades_open,
            "number_of_orders": self.number_of_orders,
            "number_of_positions": self.number_of_positions,
            "data_sources": list(self.data_sources),
            "signals": _serialise_signals(self.signals),
            "signal_events": _serialise_signal_events(self.signal_events),
            "recorded_values": _serialise_recorded_values(self.recorded_values),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        backtest_metrics: Optional[BacktestMetrics] = None,
    ) -> "BacktestRun":
        """Reconstruct a :class:`BacktestRun` from a :meth:`to_dict` payload.

        ``backtest_metrics`` may be supplied explicitly (used by the
        directory loader where metrics live in a sibling file); when
        omitted, the nested ``backtest_metrics`` key on ``data`` is used.
        """
        data = dict(data)

        if backtest_metrics is None:
            metrics_dict = data.pop("backtest_metrics", None)
            if metrics_dict is not None:
                backtest_metrics = BacktestMetrics.from_dict(metrics_dict)
        else:
            data.pop("backtest_metrics", None)

        window_data = data.pop("backtest_window", None)
        if window_data is None and data.get("backtest_start_date") is not None:
            start_date = _parse_datetime(data.get("backtest_start_date"))
            end_date = _parse_datetime(data.get("backtest_end_date")) \
                or start_date
            window = BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=start_date,
                    end_date=end_date,
                    name=data.get("backtest_date_range_name"),
                )
            )
        else:
            window = _rehydrate_backtest_window(window_data)

        # Derived fields are recomputed from the window; drop any echoes.
        for key in (
            "backtest_start_date",
            "backtest_end_date",
            "backtest_date_range_name",
            "window_role",
        ):
            data.pop(key, None)

        data["orders"] = [
            Order.from_dict(o) for o in (data.get("orders") or [])
        ]
        data["positions"] = [
            Position.from_dict(p) for p in (data.get("positions") or [])
        ]
        data["trades"] = [
            Trade.from_dict(t) for t in (data.get("trades") or [])
        ]
        data["portfolio_snapshots"] = [
            PortfolioSnapshot.from_dict(ps)
            for ps in (data.get("portfolio_snapshots") or [])
        ]
        data["signals"] = data.get("signals") or {}
        data["signal_events"] = _deserialise_signal_events(
            data.get("signal_events") or []
        )
        data["recorded_values"] = _deserialise_recorded_values(
            data.get("recorded_values") or {}
        )
        data["created_at"] = _parse_datetime(data.get("created_at"))

        valid = {f.name for f in dc_fields(cls)} - {
            "backtest_window",
            "backtest_metrics",
        }
        filtered = {k: v for k, v in data.items() if k in valid}

        return cls(
            backtest_window=window,
            backtest_metrics=backtest_metrics,
            **filtered,
        )

    # ------------------------------------------------------------------
    # Disk IO
    # ------------------------------------------------------------------

    @staticmethod
    def open(directory_path: Union[str, Path]) -> "BacktestRun":
        """Load a :class:`BacktestRun` from a ``metrics.json`` + ``run.json`` pair."""
        directory_path = str(directory_path)
        if not os.path.exists(directory_path):
            raise OperationalException(
                f"The directory {directory_path} does not exist."
            )

        metrics_file = os.path.join(directory_path, "metrics.json")
        backtest_metrics = (
            BacktestMetrics.open(metrics_file)
            if os.path.isfile(metrics_file)
            else None
        )

        run_file = os.path.join(directory_path, "run.json")
        if not os.path.isfile(run_file):
            raise OperationalException(
                f"The run file {run_file} does not exist."
            )
        with open(run_file, "r") as f:
            content = f.read().strip()
        if not content:
            raise OperationalException(
                f"The run file {run_file} is empty."
            )

        return BacktestRun.from_dict(
            json.loads(content), backtest_metrics=backtest_metrics
        )

    def save(self, directory_path: Union[str, Path]) -> None:
        """Persist this run to ``metrics.json`` + ``run.json`` under *directory_path*."""
        directory_path = str(directory_path)
        os.makedirs(directory_path, exist_ok=True)

        if self.backtest_metrics is not None:
            self.backtest_metrics.save(
                os.path.join(directory_path, "metrics.json")
            )

        payload = self.to_dict()
        payload.pop("backtest_metrics", None)

        with open(os.path.join(directory_path, "run.json"), "w") as f:
            json.dump(payload, f, default=str)

    def create_directory_name(self) -> str:
        """Return a filesystem-safe directory name for this run."""
        start = self.backtest_start_date.strftime("%Y%m%d")
        end = self.backtest_end_date.strftime("%Y%m%d")
        return f"backtest_{start}_{end}"

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

    def get_signal_events(
        self,
        symbol: str = None,
        signal: str = None,
        executed: bool = None,
        reason: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the signal event log.

        Args:
            symbol (str): Filter by target symbol (e.g. "BTC").
            signal (str): Filter by signal type ("buy" or "sell").
            executed (bool): Filter by whether the signal was acted on.
            reason (str): Filter by reason string (e.g.
                "already_in_position", "insufficient_capital",
                "executed", "no_position_to_close",
                "sell_priority_on_conflict").

        Returns:
            List[Dict]: Matching signal events, each with keys
                ``date``, ``symbol``, ``signal``, ``executed``,
                ``reason``.
        """
        selection = self.signal_events

        if symbol is not None:
            selection = [
                e for e in selection
                if e["symbol"].lower() == symbol.lower()
            ]

        if signal is not None:
            selection = [
                e for e in selection if e["signal"] == signal
            ]

        if executed is not None:
            selection = [
                e for e in selection if e["executed"] == executed
            ]

        if reason is not None:
            selection = [
                e for e in selection if e["reason"] == reason
            ]

        return selection

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

    def __repr__(self) -> str:
        return (
            f"BacktestRun(range={self.backtest_date_range_name!r}, "
            f"role={self.window_role!r}, "
            f"start={self.backtest_start_date.isoformat()}, "
            f"end={self.backtest_end_date.isoformat()}, "
            f"trades={len(self.trades)}, orders={len(self.orders)})"
        )
