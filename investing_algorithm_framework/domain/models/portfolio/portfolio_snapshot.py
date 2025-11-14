from datetime import timezone

from dateutil import parser

from investing_algorithm_framework.domain.models.base_model import BaseModel


class PortfolioSnapshot(BaseModel):

    def __init__(
        self,
        portfolio_id=None,
        trading_symbol=None,
        pending_value=None,
        unallocated=None,
        net_size=None,
        total_net_gain=None,
        total_revenue=None,
        total_cost=None,
        total_value=None,
        cash_flow=None,
        created_at=None,
        position_snapshots=None,
        metadata=None,
    ):
        self.portfolio_id = portfolio_id
        self.trading_symbol = trading_symbol
        self.pending_value = pending_value
        self.unallocated = unallocated
        self.total_net_gain = total_net_gain
        self.total_revenue = total_revenue
        self.total_value = total_value if total_value is not None else 0.0
        self.net_size = net_size
        self.total_cost = total_cost
        self.cash_flow = cash_flow
        self.metadata = metadata if metadata is not None else {}

        if created_at is not None and isinstance(created_at, str):
            self.created_at = parser.parse(created_at)
        else:
            self.created_at = created_at

        # Make sure that created_at is a timezone aware datetime object
        self.created_at = self.created_at.replace(tzinfo=timezone.utc)

        if position_snapshots is None:
            position_snapshots = []

        self.position_snapshots = position_snapshots

    def get_portfolio_id(self):
        return self.portfolio_id

    def set_portfolio_id(self, portfolio_id):
        self.portfolio_id = portfolio_id

    def get_trading_symbol(self):
        return self.trading_symbol

    def set_trading_symbol(self, trading_symbol):
        self.trading_symbol = trading_symbol.upper()

    def get_pending_value(self):
        return self.pending_value

    def set_pending_value(self, pending_value):
        self.pending_value = pending_value

    def get_unallocated(self):
        return self.unallocated

    def set_unallocated(self, unallocated):
        self.unallocated = unallocated

    def get_total_net_gain(self):
        return self.total_net_gain

    def set_total_net_gain(self, total_net_gain):
        self.total_net_gain = total_net_gain

    def get_total_revenue(self):
        return self.total_revenue

    def set_total_revenue(self, total_revenue):
        self.total_revenue = total_revenue

    def get_total_value(self):
        return self.total_value

    def set_total_value(self, total_value):
        self.total_value = total_value

    def get_total_cost(self):
        return self.total_cost

    def set_total_cost(self, total_cost):
        self.total_cost = total_cost

    def get_cash_flow(self):
        return self.cash_flow

    def set_cash_flow(self, cash_flow):
        self.cash_flow = cash_flow

    def get_created_at(self):
        return self.created_at

    def set_created_at(self, created_at):
        self.created_at = created_at

    def get_portfolio_snapshot_id(self):
        return self.portfolio_snapshot_id

    def set_position_snapshots(self, position_snapshots):
        self.position_snapshots = position_snapshots

    def get_position_snapshots(self):
        return self.position_snapshots

    def set_portfolio_snapshot_id(self, portfolio_snapshot_id):
        self.portfolio_snapshot_id = portfolio_snapshot_id

    def __repr__(self):
        return self.repr(
            portfolio_id=self.portfolio_id,
            created_at=self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            trading_symbol=self.trading_symbol,
            net_size=self.net_size,
            unallocated=self.unallocated,
            pending_value=self.pending_value,
            total_net_gain=self.total_net_gain,
            total_revenue=self.total_revenue,
            total_cost=self.total_cost,
            cash_flow=self.cash_flow,
            metadata=self.metadata,
        )

    def to_dict(self, datetime_format=None):
        """
        Convert the portfolio snapshot object to a dictionary

        Args:
            datetime_format (str): The format to use for the datetime fields.
                If None, the datetime fields will be returned as is.
                Defaults to None.

        Returns:
            dict: A dictionary representation of the portfolio snapshot object.
        """
        def ensure_iso(value):
            if hasattr(value, "isoformat"):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
            return value

        created_at = ensure_iso(self.created_at) if self.created_at else None

        return {
            "metadata": self.metadata if self.metadata else {},
            "portfolio_id": self.portfolio_id if self.portfolio_id else "",
            "trading_symbol": self.trading_symbol
            if self.trading_symbol else "",
            "pending_value": self.pending_value if self.pending_value else 0.0,
            "unallocated": self.unallocated if self.unallocated else 0.0,
            "total_net_gain": self.total_net_gain
            if self.total_net_gain else 0.0,
            "total_revenue": self.total_revenue if self.total_revenue else 0.0,
            "total_cost": self.total_cost if self.total_cost else 0.0,
            "cash_flow": self.cash_flow if self.cash_flow else 0.0,
            "net_size": self.net_size if self.net_size else 0.0,
            "created_at": created_at if created_at else "",
            "total_value": self.total_value if self.total_value else 0.0,
        }

    @staticmethod
    def from_dict(data):
        """
        Create a PortfolioSnapshot object from a dictionary.

        Args:
            data (dict): A dictionary containing the portfolio snapshot data.

        Returns:
            PortfolioSnapshot: An instance of PortfolioSnapshot.
        """
        created_at_str = data.get("created_at")
        created_at = parser.parse(created_at_str)

        # Ensure created_at is timezone aware
        created_at = created_at.replace(tzinfo=timezone.utc)

        return PortfolioSnapshot(
            net_size=data.get("net_size", 0.0),
            created_at=created_at,
            total_value=data.get("total_value", 0.0),
            trading_symbol=data.get(
                "trading_symbol", None
            ),
            portfolio_id=data.get("portfolio_id", None),
            pending_value=data.get("pending_value", 0.0),
            unallocated=data.get("unallocated", 0.0),
            total_net_gain=data.get("total_net_gain", 0.0),
            total_revenue=data.get("total_revenue", 0.0),
            total_cost=data.get("total_cost", 0.0),
            cash_flow=data.get("cash_flow", 0.0),
            metadata=data.get("metadata", {})
        )
