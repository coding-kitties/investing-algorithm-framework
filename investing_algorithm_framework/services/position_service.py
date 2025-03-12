from investing_algorithm_framework.domain import MarketService
from investing_algorithm_framework.services.repository_service import \
    RepositoryService


class PositionService(RepositoryService):

    def __init__(
        self,
        repository,
        market_service: MarketService,
        market_credential_service
    ):
        super().__init__(repository)
        self._market_service: MarketService = market_service
        self._market_credentials_service = market_credential_service

    def close_position(self, position_id, portfolio):
        self._market_service.market_data_credentials = \
            self._market_credentials_service.get_all()
        position = self.get(position_id)

        if position.amount > 0:
            self._market_service.create_market_sell_order(
                position.symbol,
                portfolio.get_trading_symbol(),
                position.amount,
                market=portfolio.get_market(),
            )
