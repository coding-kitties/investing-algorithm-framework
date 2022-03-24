from investing_algorithm_framework.core.mixins import CCXTPortfolioManagerMixin
from investing_algorithm_framework.core.portfolio_managers\
    .portfolio_manager import PortfolioManager
from investing_algorithm_framework.core.portfolio_managers\
    .sqllite_portfolio_manager import SQLLitePortfolioManager


class CCXTPortfolioManager(CCXTPortfolioManagerMixin, PortfolioManager):

    def __init__(
        self,
        identifier,
        market,
        trading_symbol,
        api_key,
        secret_key,
        track_from
    ):
        super(CCXTPortfolioManager, self).__init__(
            identifier=identifier,
            track_from=track_from,
            trading_symbol=trading_symbol
        )
        self.market = market.lower()
        self.api_key = api_key
        self.secret_key = secret_key


class CCXTSQLitePortfolioManager(
    CCXTPortfolioManagerMixin, SQLLitePortfolioManager
):

    def __init__(
        self,
        identifier,
        market,
        trading_symbol,
        api_key,
        secret_key,
        track_from
    ):
        super(CCXTSQLitePortfolioManager, self).__init__(
            identifier=identifier,
            track_from=track_from,
            trading_symbol=trading_symbol
        )
        self.market = market.lower()
        self.api_key = api_key
        self.secret_key = secret_key
