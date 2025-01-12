from dateutil.parser import parse

from investing_algorithm_framework.domain.exceptions import \
    ImproperlyConfigured
from investing_algorithm_framework.domain.models.base_model import BaseModel


class PortfolioConfiguration(BaseModel):
    """
    This class represents a portfolio configuration. It is used to
    configure the portfolio that the user wants to create.

    The portfolio configuration will have the following attributes:
    - market: The market where the portfolio will be created
    - trading_symbol: The trading symbol of the portfolio
    - track_from: The date from which the portfolio will be tracked
    - identifier: The identifier of the portfolio
    - initial_balance: The initial balance of the portfolio

    For backtesting, a portfolio configuration is used to create a
    portfolio that will be used to simulate the trading of the algorithm. if
    the user does not provide an initial balance, the portfolio will be created
    with a balance of according to the initial balanace of
        the PortfolioConfiguration class.
    """

    def __init__(
        self,
        market,
        trading_symbol,
        track_from=None,
        identifier=None,
        initial_balance=None,
    ):
        self._market = market
        self._track_from = None
        self._trading_symbol = trading_symbol.upper()
        self._identifier = identifier
        self._initial_balance = initial_balance

        if self.identifier is None:
            self._identifier = market.upper()
        else:
            self._identifier = identifier.upper()

        if track_from:
            self._track_from = parse(track_from)

        if self.trading_symbol is None:
            raise ImproperlyConfigured(
                "Portfolio configuration requires a trading symbol"
            )

    @property
    def market(self):

        if hasattr(self._market, "upper"):
            return self._market.upper()

        return self._market

    @property
    def track_from(self):
        return self._track_from

    @property
    def identifier(self):
        return self._identifier

    @property
    def trading_symbol(self):
        return self._trading_symbol

    @property
    def initial_balance(self):
        return self._initial_balance

    @property
    def has_initial_balance(self):
        return self._initial_balance is not None

    def __repr__(self):
        return self.repr(
            market=self.market,
            trading_symbol=self.trading_symbol,
            identifier=self.identifier,
            track_from=self.track_from,
            initial_balance=self.initial_balance
        )
