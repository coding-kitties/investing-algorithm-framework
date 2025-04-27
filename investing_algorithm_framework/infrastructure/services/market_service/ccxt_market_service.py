import logging
from datetime import datetime
from time import sleep
from typing import Dict

import ccxt
import polars as pl
from dateutil import parser

from investing_algorithm_framework.domain import OperationalException, Order, \
    MarketService, DATETIME_FORMAT

logger = logging.getLogger(__name__)


class CCXTMarketService(MarketService):
    """
    Market service implementation using the CCXT library
    """
    msec = 1000
    minute = 60 * msec

    def __init__(self, market_credential_service):
        super(CCXTMarketService, self).__init__(
            market_credential_service=market_credential_service,
        )

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    def initialize_exchange(self, market, market_credential):
        market = market.lower()
        if not hasattr(ccxt, market):
            raise OperationalException(
                f"No market service found for market id {market}"
            )

        exchange_class = getattr(ccxt, market)

        if exchange_class is None:
            raise OperationalException(
                f"No market service found for market id {market}"
            )

        if market_credential is not None:
            exchange = exchange_class({
                'apiKey': market_credential.api_key,
                'secret': market_credential.secret_key,
            })
        else:
            exchange = exchange_class({})

        return exchange

    def pair_exists(self, target_symbol: str, trading_symbol: str, market):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchTicker']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality pair_exists"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
        try:
            data = exchange.fetchTicker(symbol)
            return "symbol" in data
        except OperationalException:
            return False

    def get_ticker(self, symbol, market):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchTicker']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_ticker"
            )

        try:
            return exchange.fetchTicker(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                f"Could not retrieve ticker for symbol {symbol}"
            )

    def get_tickers(self, symbols, market):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchTickers']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_tickers"
            )

        try:
            return exchange.fetchTickers(symbols)
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                "Could not retrieve selection of tickers"
            )

    def get_order_book(self, symbol, market):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchOrderBook']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_order_book"
            )

        try:
            return exchange.fetchOrderBook(symbol)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order book")

    def get_order_books(self, symbols, market):
        data = {}

        for symbol in symbols:
            try:
                entry = self.get_order_book(symbol, market)
                del entry['symbol']
                data[symbol] = entry
            except Exception as e:
                logger.exception(e)

        return data

    def get_order(self, order, market):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)
        symbol = f"{order.target_symbol.upper()}/" \
                 f"{order.trading_symbol.upper()}"

        if not exchange.has['fetchOrder']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_order"
            )

        try:
            order = exchange.fetchOrder(order.external_id, symbol)
            return Order.from_ccxt_order(order)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order")

    def get_orders(self, symbol, market, since: datetime = None):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if self.config is not None and "DATETIME_FORMAT" in self.config:
            datetime_format = self.config["DATETIME_FORMAT"]
        else:
            datetime_format = DATETIME_FORMAT

        if not exchange.has['fetchOrders']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_orders"
            )

        if since is not None:
            since = exchange.parse8601(datetime_format)

            try:
                ccxt_orders = exchange.fetchOrders(symbol, since=since)
                return [Order.from_ccxt_order(order) for order in ccxt_orders]
            except Exception as e:
                logger.exception(e)
                raise OperationalException("Could not retrieve orders")
        else:
            try:
                ccxt_orders = exchange.fetchOrders(symbol)
                return [Order.from_ccxt_order(order) for order in ccxt_orders]
            except Exception as e:
                logger.exception(e)
                raise OperationalException("Could not retrieve orders")

    def get_balance(self, market) -> Dict[str, float]:
        market_credential = self.get_market_credential(market)

        if market_credential is None:
            raise OperationalException(
                f"You don't have a market credential for market {market}"
            )

        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchBalance']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_balance"
            )

        try:
            return exchange.fetchBalance()["free"]
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                f"Please make sure you have "
                f"registered a valid market credential "
                f"object to the app: {str(e)}"
            )

    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float,
        market
    ):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['createLimitBuyOrder']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality create_limit_buy_order"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            order = exchange.createLimitBuyOrder(
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
        price: float,
        market
    ):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['createLimitSellOrder']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality create_limit_sell_order"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            order = exchange.createLimitSellOrder(
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
        market
    ):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['createMarketSellOrder']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality create_market_sell_order"
            )

        symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"

        try:
            order = exchange.createMarketSellOrder(symbol, amount)
            return Order.from_ccxt_order(order)
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create market sell order")

    def cancel_order(self, order, market):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['cancelOrder']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality cancel_order"
            )

        exchange.cancelOrder(
            order.get_order_reference(),
            f"{order.get_target_symbol()}/{order.get_trading_symbol()}")

    def get_open_orders(
        self, market, target_symbol: str = None, trading_symbol: str = None
    ):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchOpenOrders']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_open_orders"
            )

        try:
            if target_symbol is None or trading_symbol is None:
                return exchange.fetchOpenOrders()

            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            ccxt_orders = exchange.fetchOpenOrders(symbol)
            return [Order.from_ccxt_order(order) for order in ccxt_orders]
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve open orders")

    def get_closed_orders(
        self, market, target_symbol: str = None, trading_symbol: str = None
    ):
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchClosedOrders']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_closed_orders"
            )

        try:
            if target_symbol is None or trading_symbol is None:
                return exchange.fetchClosedOrders()

            symbol = f"{target_symbol.upper()}/{trading_symbol.upper()}"
            ccxt_orders = exchange.fetchClosedOrders(symbol)
            return [Order.from_ccxt_order(order) for order in ccxt_orders]
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve closed orders")

    def get_ohlcv(
        self, symbol, time_frame, from_timestamp, market, to_timestamp=None
    ) -> pl.DataFrame:
        """
        Function to retrieve ohlcv data for a symbol, time frame and market

        Args:
            symbol (str): The symbol to retrieve ohlcv data for
            time_frame: The time frame to retrieve ohlcv data for
            from_timestamp: The start date to retrieve ohlcv data from
            market: The market to retrieve ohlcv data from
            to_timestamp: The end date to retrieve ohlcv data to

        Returns:
            DataFrame: The ohlcv data for the symbol, time frame and market
            in polars DataFrame format
        """

        if self.config is not None and "DATETIME_FORMAT" in self.config:
            datetime_format = self.config["DATETIME_FORMAT"]
        else:
            datetime_format = DATETIME_FORMAT

        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['fetchOHLCV']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_ohclvs"
            )

        from_time_stamp = exchange.parse8601(
            from_timestamp.strftime(datetime_format)
        )

        if to_timestamp is None:
            to_timestamp = exchange.milliseconds()
        else:
            to_timestamp = exchange.parse8601(
                to_timestamp.strftime(datetime_format)
            )
        data = []

        while from_time_stamp < to_timestamp:
            ohlcv = exchange.fetch_ohlcv(symbol, time_frame, from_time_stamp)

            if len(ohlcv) > 0:
                from_time_stamp = \
                    ohlcv[-1][0] + exchange.parse_timeframe(time_frame) * 1000
            else:
                from_time_stamp = to_timestamp

            for candle in ohlcv:
                datetime_stamp = parser.parse(exchange.iso8601(candle[0]))

                to_timestamp_datetime = parser.parse(
                    exchange.iso8601(to_timestamp),
                )

                if datetime_stamp <= to_timestamp_datetime:
                    datetime_stamp = datetime_stamp\
                        .strftime(datetime_format)

                    data.append(
                        [datetime_stamp] +
                        [float(value) for value in candle[1:]]
                    )

            sleep(exchange.rateLimit / 1000)

        # Predefined column names
        col_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

        # Combine the Series into a DataFrame with given column names
        df = pl.DataFrame(data, schema=col_names, orient="row")
        return df

    def get_ohlcvs(
        self,
        symbols,
        time_frame,
        from_timestamp,
        market,
        to_timestamp=None
    ) -> Dict[str, pl.DataFrame]:
        ohlcvs = {}

        for symbol in symbols:

            try:
                ohlcvs[symbol] = self.get_ohlcv(
                    symbol=symbol,
                    time_frame=time_frame,
                    from_timestamp=from_timestamp,
                    to_timestamp=to_timestamp,
                    market=market
                )
            except Exception as e:
                logger.exception(e)
                logger.error(f"Could not retrieve ohlcv data for {symbol}")

        return ohlcvs

    def get_symbols(self, market):
        """
        Get all available symbols for a given market
        """
        market_credential = self.get_market_credential(market)
        exchange = self.initialize_exchange(market, market_credential)
        market_information = exchange.load_markets()
        return list(market_information.keys())
