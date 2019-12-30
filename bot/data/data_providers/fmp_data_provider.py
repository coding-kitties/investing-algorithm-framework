import logging
import requests
from pandas import DataFrame

from bot.data.data_providers.data_provider import DataProvider

TICKER_LIST = 'https://financialmodelingprep.com/api/v3/company/stock/list'
PROFILE_ENDPOINT = 'https://financialmodelingprep.com/api/v3/company/profile/{}'

logger = logging.getLogger(__name__)


class FMPDataProvider(DataProvider):
    def __init__(self):
        super(FMPDataProvider, self).__init__()
        self._id = "FINANCIAL_MODELING_PREP_PROVIDER"

    def get_id(self) -> str:
        return self._id

    def provide_data(self) -> DataFrame:
        symbols_info = requests.get(TICKER_LIST).json()
        df = DataFrame(symbols_info)
        return df


