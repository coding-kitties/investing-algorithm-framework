import ccxt
import logging
from investing_algorithm_framework.core.market_services.market_service \
    import MarketService
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.mixins import \
    BinanceApiSecretKeySpecifierMixin
from investing_algorithm_framework.configuration.constants import BINANCE, \
    BINANCE_API_KEY, BINANCE_SECRET_KEY
from investing_algorithm_framework.core.models import TimeInterval


BINANCE_CCXT_ID = "binance"
logger = logging.getLogger(__name__)


class BinanceMarketService(MarketService, BinanceApiSecretKeySpecifierMixin):
    market = BINANCE
    exchange = None

    def __init__(self, api_key: str = None, secret_key: str = None):
        super().__init__()

        if api_key is not None:
            self.binance_api_key = api_key

        if secret_key is not None:
            self.binance_secret_key = secret_key

    def initialize(self, algorithm_context):

        if self.binance_api_key is None and self.binance_secret_key is None:
            self.binance_api_key = algorithm_context.config\
                .get(BINANCE_API_KEY, None)
            self.binance_secret_key = \
                algorithm_context.config.get(BINANCE_SECRET_KEY, None)

        self.initialize_exchange()

    def initialize_exchange(self):
        exchange_class = getattr(ccxt, BINANCE_CCXT_ID)
        self.exchange = exchange_class({
            'apiKey': self.get_api_key(),
            'secret': self.get_secret_key(),
        })

    def pair_exists(self, target_symbol: str, trading_symbol: str):
        try:
            data = self.get_ticker(target_symbol, trading_symbol)
            return "symbol" in data
        except OperationalException:
            return False

    def get_ticker(self, target_symbol: str, trading_symbol: str):

        try:
            symbol = f"{target_symbol.upper()}{trading_symbol.upper()}"
            return self.exchange.fetchTicker(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                f"Could not retrieve ticker"
                f"{target_symbol.upper()}{trading_symbol.upper()}"
            )

    def get_order_book(self, target_symbol: str, trading_symbol: str):

        try:
            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchOrderBook(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                "Could not retrieve order book"
            )

    def get_balance(self, symbol: str = None):

        try:
            balances = self.exchange.fetch_balance()["info"]["balances"]
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                "Could not retrieve balance"
            )

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

    def get_prices(
        self,
        target_symbol: str,
        trading_symbol: str,
        time_interval: TimeInterval
    ):
        pass
