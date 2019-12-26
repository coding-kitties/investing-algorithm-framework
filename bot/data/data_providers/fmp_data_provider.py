import logging
import requests

from pandas import DataFrame

from bot.data.data_providers.data_provider import DataProvider
from bot.events.observer import Observer

TICKER_LIST = 'https://financialmodelingprep.com/api/v3/company/stock/list'
PROFILE_ENDPOINT = 'https://financialmodelingprep.com/api/v3/company/profile/{}'

logger = logging.getLogger(__name__)


class FMPDataProvider(DataProvider):

    def start(self):
        super().start()
        self.notify_observers()

    def add_observer(self, observer: Observer) -> None:
        super().add_observer(observer)

    def remove_observer(self, observer: Observer) -> None:
        super().remove_observer(observer)

    @staticmethod
    def provide_data() -> DataFrame:
        symbols_info = requests.get(TICKER_LIST).json()
        df = DataFrame(symbols_info)
        return df


