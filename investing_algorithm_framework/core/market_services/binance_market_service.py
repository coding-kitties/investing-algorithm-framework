import ccxt
import logging
from datetime import datetime
from investing_algorithm_framework.core.market_services.market_service \
    import MarketService
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.mixins import \
    BinanceApiSecretKeySpecifierMixin
from investing_algorithm_framework.configuration.constants import BINANCE, \
    BINANCE_API_KEY, BINANCE_SECRET_KEY
from investing_algorithm_framework.core.models import TimeInterval, AssetPrice


BINANCE_CCXT_ID = "binance"
logger = logging.getLogger(__name__)


class BinanceMarketService(MarketService, BinanceApiSecretKeySpecifierMixin):
    market = BINANCE
    exchange = None
    config = None

    def __init__(
        self, config=None, api_key: str = None, secret_key: str = None
    ):
        super().__init__()

        if api_key is not None:
            self.binance_api_key = api_key

        if secret_key is not None:
            self.binance_secret_key = secret_key

        self.config = config

    def initialize(self, config):
        self.config = config

    def initialize_exchange(self, credentials = False):

        if credentials:
            if self.binance_api_key is None and self.binance_secret_key is None:
                self.binance_api_key = self.config\
                    .get(BINANCE_API_KEY, None)
                self.binance_secret_key = \
                    self.config.get(BINANCE_SECRET_KEY, None)

            exchange_class = getattr(ccxt, BINANCE_CCXT_ID)
            self.exchange = exchange_class({
                'apiKey': self.get_api_key(),
                'secret': self.get_secret_key(),
            })
        else:
            exchange_class = getattr(ccxt, BINANCE_CCXT_ID)
            self.exchange = exchange_class({})

    def pair_exists(self, target_symbol: str, trading_symbol: str):
        self.initialize_exchange()

        try:
            data = self.get_ticker(f"{target_symbol}/{trading_symbol}")
            return "symbol" in data
        except OperationalException:
            return False

    def get_ticker(self, symbol):
        self.initialize_exchange()

        try:
            return self.exchange.fetchTicker(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                f"Could not retrieve ticker for symbol {symbol}"
            )

    def get_tickers(self, symbols):

        try:
            return self.exchange.fetchTickers(symbols)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                "Could not retrieve selection of tickers"
            )

    def get_order_book(self, target_symbol: str, trading_symbol: str):
        self.initialize_exchange()

        try:
            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchOrderBook(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                "Could not retrieve order book"
            )

    def get_order(self, order_id):
        self.initialize_exchange(credentials=True)

        try:
            return self.exchange.fetch_order(order_id)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order")

    def get_orders(self, symbol: str, since: datetime = None):
        self.initialize_exchange(credentials=True)

        if since is not None:
            since = self.exchange.parse8601(since.strftime("YYYY-MM-DD:HH:MM"))

        try:
            return self.exchange.fetch_orders(symbol, since)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve orders")

    def get_balance(self, symbol):
        self.initialize_exchange(credentials=True)

        try:
            balances = self.exchange.fetch_balance()["info"]["balances"]
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve balances")

        for balance in balances:

            if balance["asset"] == symbol.upper():
                return balance

        return None

    def get_balances(self):
        self.initialize_exchange(credentials=True)

        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve balances")

    def create_limit_buy_order(
            self,
            target_symbol: str,
            trading_symbol: str,
            amount: float,
            price: float
    ):
        self.initialize_exchange(credentials=True)

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.create_limit_buy_order(
                symbol, amount, price
            )
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create limit buy order")

    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        self.initialize_exchange(credentials=True)

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.create_limit_sell_order(
                symbol, amount, price
            )
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create limit sell order")

    def create_market_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):
        self.initialize_exchange(credentials=True)

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.create_market_buy_order(symbol, amount)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create market buy order")

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):
        self.initialize_exchange(credentials=True)

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.create_market_buy_order(symbol, amount)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create market sell order")

    def cancel_order(self, order):
        self.exchange.cancelOrder(
            order.get_order_reference(),
            f"{order.get_target_symbol()}/{order.get_trading_symbol()}")

    def get_open_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        self.initialize_exchange(credentials=True)

        try:
            if target_symbol is None or trading_symbol is None:
                return self.exchange.fetchOpenOrders()

            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchOpenOrders(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve open orders")

    def get_closed_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        self.initialize_exchange(credentials=True)

        try:
            if target_symbol is None or trading_symbol is None:
                return self.exchange.fetchClosedOrders()

            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchClosedOrders(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve closed orders")

    def get_prices(self, symbols):
        self.initialize_exchange()
        asset_prices = []

        try:
            tickers = self.exchange.fetchTickers(symbols)
            for ticker in tickers:
                asset_prices.append(
                    AssetPrice(
                        tickers[ticker]["symbol"],
                        tickers[ticker]["ask"],
                        tickers[ticker]["datetime"]
                    )
                )

            return asset_prices
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve prices")
