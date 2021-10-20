import ccxt
import logging
from investing_algorithm_framework.exchanges.exchange import ExchangeClient
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.mixins import \
    ApiSecretKeySpecifierMixin

BINANCE_CCXT_ID = "binance"
logger = logging.getLogger(__name__)


class BinanceExchangeClient(ExchangeClient, ApiSecretKeySpecifierMixin):
    exchange = None

    def __init__(self, api_key: str = None, secret_key: str = None):

        if api_key is not None:
            self.api_key = api_key

        if secret_key is not None:
            self.secret_key = secret_key

    def initialize_exchange(self):
        exchange_class = getattr(ccxt, BINANCE_CCXT_ID)
        self.exchange = exchange_class({
            'apiKey': self.get_api_key(),
            'secret': self.get_secret_key(),
        })

    def get_ticker(self, target_symbol: str, trading_symbol: str):

        try:
            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchTicker(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve ticker data")

    def get_order_book(self, target_symbol: str, trading_symbol: str):

        try:
            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchOrderBook(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order book data")

    def get_balance(self, symbol: str = None):

        try:
            balances = self.exchange.fetch_balance()["info"]["balances"]
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve balance data")

        if symbol is not None:

            for balance in balances:

                if balance["asset"] == symbol.upper():
                    return balance['free']

            return None
        else:
            return balances

    def create_limit_buy_order(
            self,
            target_symbol: str,
            trading_symbol: str,
            amount: float,
            price: float
    ):
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
        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.create_market_buy_order(symbol, amount)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create market sell order")

    def cancel_order(self, order_id):
        pass

    def get_orders(self, target_symbol: str, trading_symbol: str):

        try:
            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchOrders(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve orders")

    def get_order(self, order_id, target_symbol: str, trading_symbol: str):

        try:
            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchOrder(order_id, symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order")

    def get_open_orders(
            self, target_symbol: str = None, trading_symbol: str = None
    ):
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

        try:
            if target_symbol is None or trading_symbol is None:
                return self.exchange.fetchClosedOrders()

            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchClosedOrders(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve closed orders")
