from typing import Union, List

from investing_algorithm_framework.domain import MarketCredential


class MarketCredentialService:
    """
    Service to manage market credentials.

    This service is responsible for adding, retrieving, and
    initializing market credentials.
    """
    def __init__(self):
        self._market_credentials = {}

    def add(self, market_data_credential: MarketCredential):
        self._market_credentials[market_data_credential.market.upper()] \
            = market_data_credential

    def add_all(self, market_data_credentials: List[MarketCredential]):
        for market_data_credential in market_data_credentials:
            self.add(market_data_credential)

    def get(self, market) -> Union[MarketCredential, None]:

        if market.upper() not in self._market_credentials:
            return None

        return self._market_credentials[market.upper()]

    def get_all(self) -> List[MarketCredential]:
        return list(self._market_credentials.values())

    def initialize(self):
        """
        Initialize all market credentials.
        """

        for market_credential in self.get_all():
            market_credential.initialize()
