from dateutil.parser import parse

from investing_algorithm_framework.domain.exceptions import \
    ImproperlyConfigured
from investing_algorithm_framework.domain.models.base_model import BaseModel


class PortfolioConfiguration(BaseModel):

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
            self._identifier = market.lower()

        if track_from:
            self._track_from = parse(track_from)

        if self.trading_symbol is None:
            raise ImproperlyConfigured(
                "Portfolio configuration requires a trading symbol"
            )

    @property
    def market(self):

        if hasattr(self._market, "lower"):
            return self._market.lower()

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
