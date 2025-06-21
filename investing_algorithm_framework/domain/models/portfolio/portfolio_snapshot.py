from datetime import datetime
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
        id=None,
    ):
        self.id = id
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
        self.created_at = created_at

        if position_snapshots is None:
            position_snapshots = []

        self.position_snapshots = position_snapshots

    @property
    def created_at(self):

        if isinstance(self._created_at, str):
            # Convert string to datetime if necessary
            self._created_at = datetime.strptime(
                self._created_at, "%Y-%m-%d %H:%M:%S"
            )
        return self._created_at

    @created_at.setter
    def created_at(self, value):
        if isinstance(value, str):
            # Convert string to datetime
            self._created_at = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        else:
            self._created_at = value

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
        created_at = None

        if self.created_at is not None:

            if isinstance(self.created_at, str):
                created_at = self.created_at
            else:
                created_at = self.created_at.strftime("%Y-%m-%d %H:%M:%S")

        return self.repr(
            portfolio_id=self.portfolio_id,
            created_at=created_at,
            trading_symbol=self.trading_symbol,
            net_size=self.net_size,
            unallocated=self.unallocated,
            pending_value=self.pending_value,
            total_value=self.total_value,
            total_net_gain=self.total_net_gain,
            total_revenue=self.total_revenue,
            total_cost=self.total_cost,
            cash_flow=self.cash_flow,
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

        if datetime_format is not None:
            created_at = self.created_at.strftime(datetime_format) \
                if self.created_at else None

        else:
            created_at = self.created_at

        return {
            "net_size": self.net_size,
            "created_at": created_at,
            "total_value": self.total_value,
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
        return PortfolioSnapshot(
            net_size=data.get("net_size", 0.0),
            created_at=data.get("created_at"),
            total_value=data.get("total_value", 0.0),
        )

    @staticmethod
    def get_column_names():
        """
        Get the column names for the portfolio snapshot.

        Returns:
            list: A list of column names.
        """
        return [
            "id",
            "portfolio_id",
            "trading_symbol",
            "pending_value",
            "unallocated",
            "net_size",
            "total_net_gain",
            "total_revenue",
            "total_cost",
            "total_value",
            "cash_flow",
            "created_at"
        ]