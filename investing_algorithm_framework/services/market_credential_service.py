from typing import Union, List
from investing_algorithm_framework.domain import MarketCredential


class MarketCredentialService:
    _market_credentials = {}

    def add(self, market_data_credential: MarketCredential):
        self._market_credentials[market_data_credential.market.lower()] \
            = market_data_credential

    def add_all(self, market_data_credentials: List[MarketCredential]):
        for market_data_credential in market_data_credentials:
            self.add(market_data_credential)

    def get(self, market) -> Union[MarketCredential, None]:

        if market.lower() not in self._market_credentials:
            return None

        return self._market_credentials[market]

    def get_all(self) -> List[MarketCredential]:
        return list(self._market_credentials.values())
