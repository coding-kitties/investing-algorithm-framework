from time import sleep
import logging
from datetime import datetime, timedelta, timezone

import ccxt
import polars as pl
from dateutil import parser

from investing_algorithm_framework.domain import OperationalException, \
    DATETIME_FORMAT, DataProvider, TradingDataType, convert_polars_to_pandas, \
    NetworkError, TimeFrame

logger = logging.getLogger("investing_algorithm_framework")


class CCXTDataProvider(DataProvider):
    """
    """
    backtest_data_directory = None
    backtest_data_end_date = None
    total_minutes_time_frame = None
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        data_type: str = None,
        market=None,
        symbol=None,
        time_frame=None,
        window_size=None,
        priority=1
    ):
        super().__init__(
            data_type=data_type,
            symbol=symbol,
            time_frame=time_frame,
            window_size=window_size,
            priority=priority
        )

        self.market = market
        self.data = None
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.backtest_end_index = self.window_size
        self.backtest_start_index = 0
        self.window_cache = {}

    def initialize_exchange(self, market, market_credential):
        """
        Initializes the exchange for the given market.

        Args:
            market (str): The market to initialize the exchange for.
            market_credential (MarketCredential): MarketCredential - the market

        Returns:
            Instance of the exchange class.
        """

        market = market.lower()
        if not hasattr(ccxt, market):
            raise OperationalException(
                f"No exchange found for market id {market}"
            )

        exchange_class = getattr(ccxt, market)

        if exchange_class is None:
            raise OperationalException(
                f"No exchange found for market id {market}"
            )

        if market_credential is not None:
            exchange = exchange_class({
                'apiKey': market_credential.api_key,
                'secret': market_credential.secret_key,
            })
        else:
            exchange = exchange_class({})

        return exchange

    def pre_pare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        window_size=None
    ) -> None:
        pass

    def get_backtest_data(
        self,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        window_size=None,
        pandas=False
    ) -> None:
        pass

    def has_data(
        self,
        data_type: str = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        window_size=None,
    ) -> bool:

        if TradingDataType.CUSTOM.equals(data_type):
            raise OperationalException(
                "Custom data type is not supported for CCXTOHLCVDataProvider"
            )

        if market is None:
            market = "binance"

        # Check if ccxt has an exchange for the given market
        try:
            market = market.lower()
            exchange_class = getattr(ccxt, market)
            exchange = exchange_class()
            symbols = exchange.load_markets()
            symbols = list(symbols.keys())
            return symbol in symbols

        except ccxt.NetworkError:
            raise NetworkError(
                "Network error occurred, make sure you have "
                "an active internet connection"
            )

        except Exception:
            return False

    def get_data(
        self,
        data_type: str = None,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        storage_path=None,
        window_size=None,
        pandas=False,
    ):

        if market is None:
            market = self.market

        if market is None:
            raise OperationalException(
                "Market is not set. Please set the market "
                "before calling get_data."
            )

        if symbol is None:
            symbol = self.symbol

        if symbol is None:
            raise OperationalException(
                "Symbol is not set. Please set the symbol "
                "before calling get_data."
            )

        if data_type is None:
            data_type = self.data_type

        if TradingDataType.OHLCV.equals(data_type):

            if time_frame is None:
                time_frame = self.time_frame

            if time_frame is None:
                raise OperationalException(
                    "Time frame is not set. Please set the time frame "
                    "before requesting ohlcv data."
                )

            if end_date is None and window_size is None:
                raise OperationalException(
                    "A window size is required or a start and end date "
                    "to retrieve ohlcv data."
                )

            if end_date is None:
                end_date = datetime.now(tz=timezone.utc)

            if start_date is None:

                if date is not None:
                    start_date = date
                else:
                    start_date = self.create_start_date(
                        end_date=end_date,
                        time_frame=time_frame,
                        window_size=window_size
                    )

            data = self.get_ohlcv(
                symbol=symbol,
                time_frame=time_frame,
                from_timestamp=start_date,
                market=market,
                to_timestamp=end_date
            )

            if pandas:
                data = convert_polars_to_pandas(data)

            return data

        raise OperationalException(
            f"Data type {data_type} is not supported for CCXTDataProvider"
        )

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

        market_credential = self.get_credential(market)
        exchange = self.initialize_exchange(market, market_credential)

        if from_timestamp > to_timestamp:
            raise OperationalException(
                "OHLCV data start date must be before end date"
            )

        if self.config is not None and "DATETIME_FORMAT" in self.config:
            datetime_format = self.config["DATETIME_FORMAT"]
        else:
            datetime_format = DATETIME_FORMAT

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
                    datetime_stamp = datetime_stamp \
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

    def create_start_date(self, end_date, time_frame, window_size):
        minutes = TimeFrame.from_value(time_frame).amount_of_minutes
        return end_date - timedelta(minutes=window_size * minutes)
