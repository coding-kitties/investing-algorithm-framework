import logging
import json
from typing import Dict, Any

from urllib.request import urlopen
from urllib import error

from bot.data.data_providers.data_provider import DataProvider, DataProviderException

PROFILE_ENDPOINT = 'https://financialmodelingprep.com/api/v3/company/profile/{}'

logger = logging.getLogger(__name__)


class FMPDataProvider(DataProvider):

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def refresh(self):
        pass

    def scrape_data(self, ticker: str = None):
        pass

    def get_data(self, ticker: str = None):
        pass

    def evaluate_ticker(self, ticker: str) -> bool:
        try:
            url = PROFILE_ENDPOINT.format(ticker)
            response = urlopen(url)
            data = response.read().decode("utf-8")
            data = json.loads(data)
            return data['symbol'] == ticker
        except error.HTTPError:
            logger.info('Hello')
            return False
        except Exception:
            return False

    def get_profile(self, ticker: str) -> Dict:
        url = PROFILE_ENDPOINT.format(ticker)
        response = urlopen(url)
        data = response.read().decode("utf-8")
        return json.loads(data)



