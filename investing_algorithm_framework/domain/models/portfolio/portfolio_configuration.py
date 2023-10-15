from datetime import datetime
from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.exceptions import \
    ImproperlyConfigured


class PortfolioConfiguration(BaseModel):

    def __init__(
        self,
        market,
        trading_symbol,
        api_key,
        secret_key,
        track_from=None,
        identifier=None,
        max_unallocated=-1,
        backtest=False
    ):
        self._market = market
        self._api_key = api_key
        self._secret_key = secret_key
        self._track_from = None
        self._trading_symbol = trading_symbol.upper()
        self._identifier = identifier
        self._max_unallocated = max_unallocated
        self._backtest = backtest

        if self.identifier is None:
            self._identifier = market.lower()

        if track_from:
            self._track_from = datetime.strptime(track_from, "%d/%m/%Y")

        if self.trading_symbol is None:
            raise ImproperlyConfigured(
                "Portfolio configuration requires a trading symbol"
            )

        if self.api_key is None and not self._backtest:
            raise ImproperlyConfigured(
                "Portfolio configuration requires an api key"
            )

        if self.secret_key is None and not self._backtest:
            raise ImproperlyConfigured(
                "Portfolio configuration requires a secret key"
            )

    @property
    def market(self):

        if hasattr(self._market, "lower"):
            return self._market.lower()

        return self._market

    @property
    def secret_key(self):
        return self._secret_key

    @property
    def api_key(self):
        return self._api_key

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
    def max_unallocated(self):
        return self._max_unallocated

    @property
    def has_unallocated_limit(self):
        return self.max_unallocated != -1

    @property
    def backtest(self):
        return self._backtest

    def __repr__(self):
        return self.repr(
            market=self.market,
            trading_symbol=self.trading_symbol,
            api_key=self.api_key,
            secret_key=self.secret_key,
            identifier=self.identifier,
            track_from=self.track_from,
            max_unallocated=self.max_unallocated,
        )
