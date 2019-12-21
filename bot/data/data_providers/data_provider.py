import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any
from pandas import DataFrame

logger = logging.getLogger(__name__)


class DataProviderException(Exception):
    """
    Should be raised with a data_provider-formatted message in an _data_provider_* method
    if ticker is wrong, i.e.:
    raise DataProviderException('*Status:* `ticker is not valid`')
    """
    def __init__(self, message: str) -> None:
        super().__init__(self)
        self.message = message

    def __str__(self):
        return self.message

    def __json__(self):
        return {
            'msg': self.message
        }


class DataProvider(ABC):

    def __init__(self, config: Dict[str, Any]):
        self.__config = config
        self.data: DataFrame = None

    @abstractmethod
    def refresh(self):
        pass

    @abstractmethod
    def scrape_data(self, ticker: str = None):
        pass

    @abstractmethod
    def evaluate_ticker(self, ticker: str) -> bool:
        pass

    @abstractmethod
    def get_profile(self, ticker: str) -> Dict:
        pass

