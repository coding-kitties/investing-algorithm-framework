from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.decimal_parsing import \
    parse_string_to_decimal, parse_decimal_to_string


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
    ):
        self.identifier = identifier
        self.updated_at = None
        self.trading_symbol = trading_symbol.upper()
        self.net_size = parse_decimal_to_string(net_size)
        self.unallocated = parse_decimal_to_string(unallocated)
        self.realized = parse_decimal_to_string(realized)
        self.total_revenue = parse_decimal_to_string(total_revenue)
        self.total_cost = parse_decimal_to_string(total_cost)
        self.total_net_gain = parse_decimal_to_string(total_net_gain)
        self.total_trade_volume = parse_decimal_to_string(total_trade_volume)
        self.market = market

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
        return parse_string_to_decimal(self.unallocated)

    def get_net_size(self):
        return parse_string_to_decimal(self.net_size)

    def get_realized(self):
        return parse_string_to_decimal(self.realized)

    def get_total_revenue(self):
        return parse_string_to_decimal(self.total_revenue)

    def get_total_cost(self):
        return parse_string_to_decimal(self.total_cost)

    def get_total_net_gain(self):
        return parse_string_to_decimal(self.total_net_gain)

    def get_total_trade_volume(self):
        return parse_string_to_decimal(self.total_trade_volume)
