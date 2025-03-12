from investing_algorithm_framework.domain.models.base_model import BaseModel


class Portfolio(BaseModel):
    """
    Portfolio base class.

    A portfolio is a collection of positions that are managed by an algorithm.

    Attributes:
    * identifier: str, unique identifier of the portfolio
    * trading_symbol: str, trading symbol of the portfolio
    * unallocated: float, the size of the trading symbol that is not
      allocated. For example, if the trading symbol is USDT and the unallocated
      is 1000, it means that the portfolio has 1000 USDT that is not
        allocated to any position.
    * net_size: float, net size of the portfolio is the initial balance of the
        portfolio plus the all the net gains of the trades. The
    * realized: float, the realized gain of the portfolio is the sum of all the
        realized gains of the trades.
    * total_revenue: float, the total revenue of the portfolio is the sum
        of all the orders (price * size)
    * total_cost: float, the total cost of the portfolio is the sum of all the
        costs of the trades (price * size (for buy orders)
        or -price * size (for sell orders))
    * total_net_gain: float, the total net gain of the portfolio is the sum of
        all the net gains of the trades
    * total_trade_volume: float, the total trade volume of the
        portfolio is the sum of all the sizes of the trades
    * market: str, the market of the portfolio (e.g. BITVAVO, BINANCE)
    * created_at: datetime, the datetime when the portfolio was created
    * updated_at: datetime, the datetime when the portfolio was last updated
    * initialized: bool, whether the portfolio is initialized or not
    * initial_balance: float, the initial balance of the portfolio
    """

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
        updated_at=None,
        initialized=False,
        initial_balance=None
    ):
        self.identifier = identifier
        self.updated_at = None
        self.trading_symbol = trading_symbol.upper()
        self.net_size = net_size
        self.unallocated = unallocated
        self.initial_balance = initial_balance
        self.realized = realized
        self.total_revenue = total_revenue
        self.total_cost = total_cost
        self.total_net_gain = total_net_gain
        self.total_trade_volume = total_trade_volume
        self.market = market.upper()
        self.created_at = created_at
        self.updated_at = updated_at
        self.initialized = initialized

    def __repr__(self):
        return self.repr(
            identifier=self.identifier,
            trading_symbol=self.trading_symbol,
            net_size=self.net_size,
            unallocated=self.unallocated,
            realized=self.realized,
            total_revenue=self.total_revenue,
            total_cost=self.total_cost,
            market=self.market,
            initial_balance=self.initial_balance
        )

    def get_identifier(self):
        return self.identifier

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

    def get_market(self):
        return self.market

    def get_initial_balance(self):
        return self.initial_balance

    @staticmethod
    def from_portfolio_configuration(portfolio_configuration):
        """
        Function to create a portfolio from a portfolio configuration

        We assume that a portfolio that is created from a configuration
        is always un initialized.

        Args:
            portfolio_configuration: PortfolioConfiguration

        Returns:
            Portfolio
        """
        return Portfolio(
            identifier=portfolio_configuration.identifier,
            trading_symbol=portfolio_configuration.trading_symbol,
            unallocated=portfolio_configuration.initial_balance,
            net_size=portfolio_configuration.initial_balance,
            market=portfolio_configuration.market,
            initial_balance=portfolio_configuration.initial_balance,
            initialized=False
        )

    def to_dict(self):
        return {
            "trading_symbol": self.trading_symbol,
            "market": self.market,
            "unallocated": self.unallocated,
            "identifier": self.identifier,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "initialized": self.initialized,
            "initial_balance": self.initial_balance,
        }
