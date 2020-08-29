import json
from urllib.request import urlopen
from typing import List, Dict
from investing_algorithm_framework.core.exceptions import OperationalException

PRICE_URL = 'https://api.binance.com/api/v1/ticker/price?symbol={}'
PRICES_URL = 'https://api.binance.com/api/v1/ticker/price'
BOOK_TICKER_URL = 'https://api.binance.com/api/v3/ticker/bookTicker?symbol={}'
BOOK_TICKERS_URL = 'https://api.binance.com/api/v3/ticker/bookTicker'


class BinanceDataProviderMixin:
    secret_key = None
    api_token = None

    def configure(self, secret_key, api_token) -> None:
        self.secret_key = secret_key
        self.api_token = api_token

    @staticmethod
    def get_price(symbol) -> Dict:

        if not symbol:
            raise OperationalException("No symbol provided")

        url = PRICE_URL.format(symbol)
        response = urlopen(url)

        data = response.read().decode("utf-8")
        data = json.loads(data)
        return data

    @staticmethod
    def get_prices(symbols: List[str] = None) -> List[Dict]:
        response = urlopen(PRICES_URL)
        data = response.read().decode("utf-8")
        data = json.loads(data)

        if symbols is not None:
            data = [price for price in data if price["symbol"] in symbols]

        return data

    @staticmethod
    def get_book_ticker(symbol: str) -> Dict:
        if not symbol:
            raise OperationalException("No symbol provided")

        url = BOOK_TICKER_URL.format(symbol)
        response = urlopen(url)
        data = response.read().decode("utf-8")
        data = json.loads(data)
        return data

    @staticmethod
    def get_book_tickers(symbols: List[str] = None) -> List[Dict]:
        url = BOOK_TICKERS_URL
        response = urlopen(url)

        data = response.read().decode("utf-8")
        data = json.loads(data)

        if symbols is not None:
            data = [
                book_ticker for book_ticker in data
                if book_ticker["symbol"] in symbols
            ]

        return data