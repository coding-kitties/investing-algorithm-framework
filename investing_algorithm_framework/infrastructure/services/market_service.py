import logging
from datetime import datetime
from time import sleep
import pandas as pd
from dateutil.parser import parse
import ccxt

from investing_algorithm_framework.domain import OperationalException, \
    OHLCV, AssetPrice, Order

logger = logging.getLogger("investing_algorithm_framework")


class MarketService:
    exchange = None
    _market = None
    api_key = None,
    secret_key = None
    exchange_class = None
    msec = 1000
    minute = 60 * msec

    @property
    def market(self):
        return self._market

    @market.setter
    def market(self, value):

        if not isinstance(value, str):
            raise OperationalException("Market must be a string")

        self._market = value.lower()

        if not hasattr(ccxt, self._market):
            raise OperationalException(
                f"No market service found for market id {self._market}"
            )

        self.exchange_class = getattr(ccxt, self._market)
        self.exchange = self.exchange_class()

    def initialize(self, portfolio_configuration):
        self.api_key = portfolio_configuration.api_key
        self.secret_key = portfolio_configuration.secret_key
        self._market = portfolio_configuration.market

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

    def get_order_books(self, symbols):
        data = {}

        for symbol in symbols:
            try:
                entry = self.get_order_book(symbol)
                del entry['symbol']
                data[symbol] = entry
            except Exception as e:
                logger.exception(e)

        return data

    def get_order(self, order):
        symbol = f"{order.target_symbol.upper()}/" \
                 f"{order.trading_symbol.upper()}"

        if not self.exchange.has['fetchOrder']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_order"
            )

        try:
            order = self.exchange.fetchOrder(order.external_id, symbol)
            return Order.from_ccxt_order(order)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order")

    def get_orders(self, symbol, since: datetime = None):

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
                ccxt_orders = self.exchange.fetchOrders(symbol, since=since)
                return [Order.from_ccxt_order(order) for order in ccxt_orders]
            except Exception as e:
                logger.exception(e)
                raise OperationalException("Could not retrieve orders")
        else:
            try:
                ccxt_orders = self.exchange.fetchOrders(symbol)
                return [Order.from_ccxt_order(order) for order in ccxt_orders]
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
            order = self.exchange.createLimitBuyOrder(
                symbol, amount, price
            )
            return Order.from_ccxt_order(order)
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
            order = self.exchange.createLimitSellOrder(
                symbol, amount, price
            )
            return Order.from_ccxt_order(order)
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
            order = self.exchange.createMarketSellOrder(symbol, amount)
            return Order.from_ccxt_order(order)
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
            ccxt_orders = self.exchange.fetchOpenOrders(symbol)
            return [Order.from_ccxt_order(order) for order in ccxt_orders]
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
            ccxt_orders = self.exchange.fetchClosedOrders(symbol)
            return [Order.from_ccxt_order(order) for order in ccxt_orders]
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

    def get_ohclv(self, symbol, time_frame, from_timestamp):

        if not self.exchange.has['fetchOHLCV']:
            raise OperationalException(
                f"Market service {self.market} does not support "
                f"functionality get_ohclvs"
            )

        time_stamp = self.exchange.parse8601(
            from_timestamp.strftime(":%Y-%m-%d %H:%M:%S")
        )
        now = self.exchange.milliseconds()
        data = []

        while time_stamp < now:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol, time_frame.to_ccxt_string(), time_stamp
            )

            if len(ohlcv) > 0:
                time_stamp = \
                    ohlcv[-1][0] + \
                    self.exchange.parse_timeframe(
                        time_frame.to_ccxt_string()
                    ) * 1000
            else:
                time_stamp = now

            ohlcv = [[self.exchange.iso8601(candle[0])]
                     + candle[1:] for candle in ohlcv]
            data += ohlcv
            sleep(self.exchange.rateLimit / 1000)

        return OHLCV.from_dict({"symbol": symbol, "data": data})

    def get_ohclvs(self, symbols, time_frame, from_timestamp):
        ohlcvs = {}

        for symbol in symbols:

            try:
                ohlcvs[symbol] = self.get_ohclv(
                    symbol, time_frame, from_timestamp
                )
            except Exception as e:
                logger.exception(e)
                logger.error(f"Could not retrieve ohclv data for {symbol}")

        return ohlcvs
