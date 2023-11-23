from investing_algorithm_framework.domain.models.base_model import BaseModel


class PortfolioSnapshot(BaseModel):

    def __init__(
        self,
        portfolio_id,
        trading_symbol,
        pending_value,
        unallocated,
        total_net_gain,
        total_revenue,
        total_cost,
        cash_flow,
        created_at,
        position_snapshots=None
    ):
        self.portfolio_id = portfolio_id
        self.trading_symbol = trading_symbol
        self.pending_value = pending_value
        self.unallocated = unallocated
        self.total_net_gain = total_net_gain
        self.total_revenue = total_revenue
        self.total_cost = total_cost
        self.cash_flow = cash_flow
        self.created_at = created_at

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
            unallocated=self.unallocated,
            pending_value=self.pending_value,
            total_net_gain=self.total_net_gain,
            total_revenue=self.total_revenue,
            total_cost=self.total_cost,
            cash_flow=self.cash_flow,
        )
