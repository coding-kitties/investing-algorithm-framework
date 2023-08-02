from investing_algorithm_framework.domain.models.base_model import BaseModel


class Portfolio(BaseModel):

    def __init__(
        self,
        identifier,
        trading_symbol,
        net_size,
        unallocated,
        realized=0,
        total_revenue=0,
        total_cost=0,
        total_net_gain=0,
    ):
        self.identifier = identifier
        self.updated_at = None
        self.trading_symbol = trading_symbol.upper()
        self.net_size = net_size
        self.unallocated = unallocated
        self.realized = realized
        self.total_revenue = total_revenue
        self.total_cost = total_cost
        self.total_net_gain = total_net_gain

    def __repr__(self):
        return self.repr(
            identifier=self.identifier,
            trading_symbol=self.trading_symbol,
            net_size=self.net_size,
            unallocated=self.unallocated,
            realized=self.realized,
            total_revenue=self.total_revenue,
            total_cost=self.total_cost
        )
