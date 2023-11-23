from investing_algorithm_framework.domain.models.base_model import BaseModel


class Portfolio(BaseModel):

    def __init__(
        self,
        identifier,
        trading_symbol,
        net_size,
        unallocated,
        market,
        realized=0,
        total_revenue=0,
        total_cost=0,
        total_net_gain=0,
        total_trade_volume=0,
        created_at=None,
        updated_at=None
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
        self.total_trade_volume = total_trade_volume
        self.market = market
        self.created_at = created_at
        self.updated_at = updated_at

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

    def get_unallocated(self):
        return self.unallocated

    def get_net_size(self):
        return self.net_size

    def get_realized(self):
        return self.realized

    def get_total_revenue(self):
        return self.total_revenue

    def get_total_cost(self):
        return self.total_cost

    def get_total_net_gain(self):
        return self.total_net_gain

    def get_total_trade_volume(self):
        return self.total_trade_volume

    def get_created_at(self):
        return self.created_at

    def get_updated_at(self):
        return self.updated_at

    def get_trading_symbol(self):
        return self.trading_symbol
