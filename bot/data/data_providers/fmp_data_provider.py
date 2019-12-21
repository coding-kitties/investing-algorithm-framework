import logging
import json
import requests
from typing import Dict, Any

from urllib.request import urlopen
from urllib import error

from pandas import DataFrame

from bot.data.data_providers.data_provider import DataProvider, DataProviderException

TICKER_LIST = 'https://financialmodelingprep.com/api/v3/company/stock/list'
PROFILE_ENDPOINT = 'https://financialmodelingprep.com/api/v3/company/profile/{}'

logger = logging.getLogger(__name__)


class FMPDataProvider(DataProvider):

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def refresh(self):
        pass

    def scrape_data(self, ticker: str = None) -> DataFrame:

        if ticker is None:
            tickers = requests.get(TICKER_LIST).json()

            for ticker in tickers:
                logger.info(ticker)

        return

    def evaluate_ticker(self, ticker: str) -> bool:
        try:
            url = PROFILE_ENDPOINT.format(ticker)
            response = urlopen(url)
            data = response.read().decode("utf-8")
            data = json.loads(data)
            return data['symbol'] == ticker
        except error.HTTPError:
            return False
        except Exception:
            return False

    def get_profile(self, ticker: str) -> Dict:
        url = PROFILE_ENDPOINT.format(ticker)
        response = urlopen(url)
        data = response.read().decode("utf-8")
        return json.loads(data)



