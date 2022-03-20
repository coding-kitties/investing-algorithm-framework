import logging
from datetime import datetime
from time import sleep
import ccxt

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.market_services.market_service \
    import MarketService
from investing_algorithm_framework.core.models import AssetPrice, OHLCV

logger = logging.getLogger(__name__)


class CCXTMarketService(MarketService):
    exchange = None
    config = None
    market = None
    api_key = None,
    secret_key = None
    exchange_class = None
    msec = 1000
    minute = 60 * msec

    def __init__(
        self, market, config=None, api_key: str = None, secret_key: str = None
    ):
        super().__init__()

        self.market = market.lower()

        if api_key is not None:
            self.binance_api_key = api_key

        if secret_key is not None:
            self.binance_secret_key = secret_key

        self.config = config

    def initialize(self, api_key=None, secret_key=None):
        self.api_key = api_key
        self.secret_key = secret_key

        if not hasattr(ccxt, self.market):
            raise OperationalException(
                f"No market service found for market id {self.market}"
            )

        self.exchange_class = getattr(ccxt, self.market)

        if self.exchange_class is None:
            raise OperationalException(
                f"No market service found for market id {self.market}"
            )

        if self.api_key is not None or self.secret_key is not None:
            self.exchange = self.exchange_class({
                'apiKey': self.api_key,
                'secret': self.secret_key,
            })
        else:
            self.exchange = self.exchange_class({})

    def pair_exists(self, target_symbol: str, trading_symbol: str):

        if not self.exchange.has['fetchTicker']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality pair_exists"
            )

        try:
            data = self.get_ticker(f"{target_symbol}/{trading_symbol}")
            return "symbol" in data
        except OperationalException:
            return False

    def get_ticker(self, symbol):

        if not self.exchange.has['fetchTicker']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_ticker"
            )

        try:
            return self.exchange.fetchTicker(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                f"Could not retrieve ticker for symbol {symbol}"
            )

    def get_tickers(self, symbols):

        if not self.exchange.has['fetchTickers']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_tickers"
            )

        try:
            return self.exchange.fetchTickers(symbols)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                "Could not retrieve selection of tickers"
            )

    def get_order_book(self, symbol):

        if not self.exchange.has['fetchOrderBook']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_order_book"
            )

        try:
            return self.exchange.fetchOrderBook(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order book")

    def get_order(self, order_id):

        if not self.exchange.has['fetchOrder']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_order"
            )

        try:
            return self.exchange.fetchOrder(order_id)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order")

    def get_orders(self, symbol: str, since: datetime = None):

        if not self.exchange.has['fetchOrders']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_orders"
            )

        if since is not None:
            since = self.exchange.parse8601(
                since.strftime(":%Y-%m-%d %H:%M:%S")
            )

            try:
                return self.exchange.fetchOrders(symbol, since=since)
            except Exception as e:
                logger.exception(e)
                raise OperationalException("Could not retrieve orders")
        else:
            try:
                return self.exchange.fetchOrders(symbol)
            except Exception as e:
                logger.exception(e)
                raise OperationalException("Could not retrieve orders")

    def get_balance(self):

        if not self.exchange.has['fetchBalance']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_balance"
            )

        try:
            return self.exchange.fetchBalance()
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve balance")

    def create_limit_buy_order(
            self,
            target_symbol: str,
            trading_symbol: str,
            amount: float,
            price: float
    ):

        if not self.exchange.has['createLimitBuyOrder']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality create_limit_buy_order"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.createLimitBuyOrder(
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

        if not self.exchange.has['createLimitSellOrder']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality create_limit_sell_order"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.createLimitSellOrder(
                symbol, amount, price
            )
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create limit sell order")

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):

        if not self.exchange.has['createMarketSellOrder']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality create_market_sell_order"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            self.exchange.createMarketSellOrder(symbol, amount)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create market sell order")

    def cancel_order(self, order):

        if not self.exchange.has['cancelOrder']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality cancel_order"
            )

        self.exchange.cancelOrder(
            order.get_order_reference(),
            f"{order.get_target_symbol()}/{order.get_trading_symbol()}")

    def get_open_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):

        if not self.exchange.has['fetchOpenOrders']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_open_orders"
            )

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

        if not self.exchange.has['fetchClosedOrders']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_closed_orders"
            )

        try:
            if target_symbol is None or trading_symbol is None:
                return self.exchange.fetchClosedOrders()

            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            return self.exchange.fetchClosedOrders(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve closed orders")

    def get_prices(self, symbols):
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

    def get_ohclv(self, symbol, time_unit, since):

        if not self.exchange.has['fetchOHLCV']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_ohclvs"
            )

        from_timestamp = self.exchange.parse8601(
            since.strftime(":%Y-%m-%d %H:%M:%S")
        )

        now = self.exchange.milliseconds()
        data = []

        while from_timestamp < now:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol, time_unit, from_timestamp
            )

            sleep(self.exchange.rateLimit / 1000)
            from_timestamp = \
                ohlcv[-1][0] + self.exchange.parse_timeframe(time_unit) * 1000
            data += ohlcv

        return OHLCV.from_dict({"symbol": symbol, "data": data})

    def get_ohclvs(self, symbols, time_unit, since):

        if not self.exchange.has['fetchOHLCV']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_ohclvs"
            )

        from_timestamp = self.exchange.parse8601(
            since.strftime(":%Y-%m-%d %H:%M:%S")
        )

        now = self.exchange.milliseconds()
        ohlcvs = []

        for symbol in symbols:
            data = []

            while from_timestamp < now:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol, time_unit, from_timestamp
                )
                sleep(self.exchange.rateLimit / 1000)
                from_timestamp = \
                    ohlcv[-1][0] + \
                    self.exchange.parse_timeframe(time_unit) * 1000
                data += ohlcv

            ohlcvs.append(OHLCV.from_dict({"symbol": symbol, "data": data}))

        return ohlcvs
