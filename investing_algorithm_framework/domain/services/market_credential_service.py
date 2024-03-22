from abc import ABC, abstractmethod
from typing import List, Optional

from investing_algorithm_framework.domain import MarketCredential


class MarketCredentialService(ABC):
    """
    This class is responsible for managing the market credentials of the app.
    """
    @abstractmethod
    def add(self, market_data_credential: MarketCredential):
        """
        Add a market credential in the repository
        """
        raise NotImplementedError()

    @abstractmethod
    def add_all(self, market_data_credentials: List[MarketCredential]):
        """
        Add a list of market credentials in the repository
        """
        raise NotImplementedError()

    @abstractmethod
    def get(self, market) -> Optional[MarketCredential]:
        """
        Get a market credential from the repository
        """
        raise NotImplementedError()

    @abstractmethod
    def get_all(self) -> List[MarketCredential]:
        """
        Get all market credentials from the repository
        """
        raise NotImplementedError()
