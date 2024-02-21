import logging
import os
from datetime import timedelta

import polars

from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    BACKTEST_DATA_DIRECTORY_NAME, DATETIME_FORMAT_BACKTESTING, \
    OperationalException, DATETIME_FORMAT, OHLCVMarketDataSource, \
    BacktestMarketDataSource, OrderBookMarketDataSource, \
    TickerMarketDataSource, TimeFrame
from investing_algorithm_framework.infrastructure.services import \
    CCXTMarketService

logger = logging.getLogger(__name__)


class CCXTOHLCVBacktestMarketDataSource(
    OHLCVMarketDataSource, BacktestMarketDataSource
):
    """
    CCXTOHLCVBacktestMarketDataSource implementation using ccxt to download
    all data sources.

    This class will determine the start and end date of the data range by
    taking the backtest start date (e.g. 01-01-2024) and the backtest
    end date (e.g. 31-12-2024) in combination with the difference between
    start and end date. The reason for this is that the data source needs
    to have data on the first run (e.g. an algorithm starting on
    01-01-2024 that requires 2h data for the last 17 days will
    need to have pulled data from 15-12-2023)

    To achieve this, a backtest_data_start_date attribute is used. This
    attribute is indexed on this calculated date.
    """
    backtest_data_directory = None
    backtest_data_end_date = None
    total_minutes_timeframe = None
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        identifier,
        market,
        symbol,
        timeframe,
        start_date=None,
        window_size=None,
        start_date_func=None,
        end_date_func=None,
        end_date=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            start_date_func=start_date_func,
            end_date=end_date,
            end_date_func=end_date_func,
            window_size=window_size
        )

    def prepare_data(
        self,
        config,
        backtest_start_date,
        backtest_end_date,
        **kwargs
    ):
        """
        Prepare data implementation of ccxt based ohlcv backtest market
        data source

        This implementation will check if the data source already exists before
        pulling all the data. This optimization will prevent downloading
        of unnecessary resources.

        When downloading the data it will use the ccxt library.
        """
        # Calculating the backtest data start date

        difference = self.end_date - self.start_date
        total_minutes = 0

        if difference.days > 0:
            total_minutes += difference.days * 24 * 60

        if difference.seconds > 0:
            total_minutes += difference.seconds / 60

        self.total_minutes_timeframe = total_minutes
        backtest_data_start_date = \
            backtest_start_date - timedelta(
                minutes=(
                        self.window_size *
                        TimeFrame.from_string(self.timeframe).amount_of_minutes
                )
            )
        self.backtest_data_start_date = backtest_data_start_date\
            .replace(microsecond=0)
        self.backtest_data_index_date = backtest_data_start_date\
            .replace(microsecond=0)
        self.backtest_data_end_date = backtest_end_date.replace(microsecond=0)

        # Creating the backtest data directory and file
        self.backtest_data_directory = os.path.join(
            config.get(RESOURCE_DIRECTORY),
            config.get(BACKTEST_DATA_DIRECTORY_NAME)
        )

        if not os.path.isdir(self.backtest_data_directory):
            os.mkdir(self.backtest_data_directory)

        file_path = self._create_file_path()

        if not self._data_source_exists(file_path):
            if not os.path.isfile(file_path):
                try:
                    with open(file_path, 'w') as _:
                        pass
                except Exception as e:
                    logger.error(e)
                    raise OperationalException(
                        f"Could not create backtest data file {file_path}"
                    )

            # Get the OHLCV data from the ccxt market service
            market_service = CCXTMarketService(self.market_credential_service)
            ohlcv = market_service.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.timeframe,
                from_timestamp=backtest_data_start_date,
                to_timestamp=backtest_end_date,
                market=self.market
            )
            self.write_data_to_file_path(file_path, ohlcv)

    def _create_file_path(self):
        """
        Function to create a filename in the following format:
        OHLCV_{symbol}_{market}_{timeframe}_{start_date}_{end_date}.csv
        """
        symbol_string = self.symbol.replace("/", "-")
        time_frame_string = self.timeframe.replace("_", "")
        backtest_data_start_date = \
            self.backtest_data_start_date.strftime(DATETIME_FORMAT_BACKTESTING)
        backtest_data_end_date = \
            self.backtest_data_end_date.strftime(DATETIME_FORMAT_BACKTESTING)
        return os.path.join(
            self.backtest_data_directory,
            os.path.join(
                f"OHLCV_"
                f"{symbol_string}_"
                f"{self.market}_"
                f"{time_frame_string}_"
                f"{backtest_data_start_date}_"
                f"{backtest_data_end_date}.csv"
            )
        )

    def get_data(self, backtest_index_date, **kwargs):
        """
        Get data implementation of ccxt based ohlcv backtest market data
        source. This implementation will use polars to load and filter the
        data.
        """
        file_path = self._create_file_path()
        to_timestamp = backtest_index_date
        from_timestamp = backtest_index_date - timedelta(
            minutes=self.total_minutes_timeframe
        )
        self.backtest_data_index_date = backtest_index_date\
            .replace(microsecond=0)
        from_timestamp = from_timestamp.replace(microsecond=0)

        if from_timestamp < self.backtest_data_start_date:
            raise OperationalException(
                f"Cannot get data from {from_timestamp} as the "
                f"backtest data starts at {self.start_date}"
            )

        if to_timestamp > self.backtest_data_end_date:
            raise OperationalException(
                f"Cannot get data to {to_timestamp} as the "
                f"backtest data ends at {self.end_date}"
            )

        # Load the csv file and filter out the dates that are not in the
        # backtest index date range
        df = polars.read_csv(
            file_path, columns=self.column_names, separator=","
        )
        df = df.filter(
            (df['Datetime'] >= from_timestamp.strftime(DATETIME_FORMAT))
            & (df['Datetime'] <= to_timestamp.strftime(DATETIME_FORMAT))
        )
        return df

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # Ignore this method for now
        pass

    def empty(self):
        return False

    @property
    def file_name(self):
        return self._create_file_path().split("/")[-1]


class CCXTTickerBacktestMarketDataSource(
    TickerMarketDataSource, BacktestMarketDataSource
):
    """
    CCXTTickerBacktestMarketDataSource implementation using ccxt to download
    all data sources.

    This class will determine the start and end date of the data range by
    taking the start date of the backtest minus 1 day and the end date of the
    backtest. The reason for this is that the data source needs
    to have data on the first run (e.g. an algorithm starting on
    01-01-2024 that requires ticker data will need to have pulled data from
    01-01-2024 - amount of minutes of the provided timeframe)

    To achieve this, a backtest_data_start_date attribute is used. This
    attribute is indexed on this calculated date.
    """
    backtest_data_directory = None
    backtest_data_start_date = None
    backtest_data_end_date = None
    timeframe = "15m"
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        identifier,
        market,
        symbol=None,
        timeframe="15m",
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        if timeframe is not None:
            self.timeframe = timeframe

    def prepare_data(
        self,
        config,
        backtest_start_date,
        backtest_end_date,
        **kwargs
    ):
        """
        Prepare data implementation of ccxt based ticker backtest market
        data source

        This implementation will check if the data source already exists before
        pulling all the data. This optimization will prevent downloading
        of unnecessary resources.

        When downloading the data it will use the ccxt library.
        """
        total_minutes = TimeFrame.from_string(self.timeframe).amount_of_minutes
        self.backtest_data_start_date = \
            backtest_start_date - timedelta(minutes=total_minutes)
        self.backtest_data_end_date = backtest_end_date

        # Creating the backtest data directory and file
        self.backtest_data_directory = os.path.join(
            config.get(RESOURCE_DIRECTORY),
            config.get(BACKTEST_DATA_DIRECTORY_NAME)
        )

        if not os.path.isdir(self.backtest_data_directory):
            os.mkdir(self.backtest_data_directory)

        file_path = self._create_file_path()

        if not os.path.isfile(file_path):
            try:
                with open(file_path, 'w') as _:
                    pass
            except Exception as e:
                logger.error(e)
                raise OperationalException(
                    f"Could not create backtest data file {file_path}"
                )

        # Check if the data source already exists, if not download the data
        if not self._data_source_exists(file_path):
            if not os.path.isfile(file_path):
                try:
                    with open(file_path, 'w') as _:
                        pass
                except Exception as e:
                    logger.error(e)
                    raise OperationalException(
                        f"Could not create backtest data file {file_path}"
                    )

            # Get the OHLCV data from the ccxt market service
            market_service = CCXTMarketService(self.market_credential_service)
            ohlcv = market_service.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.timeframe,
                from_timestamp=self.backtest_data_start_date,
                to_timestamp=backtest_end_date,
                market=self.market
            )
            self.write_data_to_file_path(file_path, ohlcv)

    def _create_file_path(self):

        if self.symbol is None or self.market is None:
            return None

        symbol_string = self.symbol.replace("/", "-")
        market_string = self.market.replace("/", "-")
        backtest_data_start_date = \
            self.backtest_data_start_date.strftime(DATETIME_FORMAT_BACKTESTING)
        backtest_data_end_date = \
            self.backtest_data_end_date.strftime(DATETIME_FORMAT_BACKTESTING)
        return os.path.join(
            self.backtest_data_directory,
            os.path.join(
                f"TICKER_"
                f"{symbol_string}_"
                f"{market_string}_"
                f"{backtest_data_start_date}_"
                f"{backtest_data_end_date}.csv"
            )
        )

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # Ignore this method for now
        pass

    def empty(self):
        return False

    def get_data(self, **kwargs):
        """
        Get data implementation of ccxt based ticker backtest market data
        source
        """
        if "backtest_index_date" not in kwargs:
            raise OperationalException(
                "backtest_index_date should be passed as a parameter "
                "for CCXTTickerBacktestMarketDataSource"
            )

        file_path = self._create_file_path()
        timeframe_minutes = TimeFrame.from_string(self.timeframe)\
            .amount_of_minutes
        backtest_index_date = kwargs["backtest_index_date"]
        end_date = backtest_index_date + timedelta(minutes=timeframe_minutes)

        # Filter the data based on the backtest index date and the end date
        df = polars.read_csv(file_path)
        df = df.filter(
            (df['Datetime'] >= backtest_index_date
             .strftime(DATETIME_FORMAT))
        )

        first_row = df.head(1)[0]

        if first_row["Datetime"][0] > end_date.strftime(DATETIME_FORMAT):
            logger.warn(
                f"No ticker data available for the given backtest "
                f"index date {backtest_index_date} and symbol {self.symbol} "
                f"and market {self.market}"
            )

        # Calculate the bid and ask price based on the high and low price
        return {
            "symbol": self.symbol,
            "bid": float((first_row["Low"][0])
                         + float(first_row["High"][0]))/2,
            "ask": float((first_row["Low"][0])
                         + float(first_row["High"][0]))/2,
            "datetime": first_row["Datetime"][0],
        }


class CCXTOHLCVMarketDataSource(OHLCVMarketDataSource):

    def get_data(self, **kwargs):
        market_service = CCXTMarketService(self.market_credential_service)

        if self.start_date is None:
            raise OperationalException(
                "Either start_date or start_date_func should be set "
                "for OHLCVMarketDataSource"
            )

        return market_service.get_ohlcv(
            symbol=self.symbol,
            time_frame=self.timeframe,
            from_timestamp=self.start_date,
            to_timestamp=self.end_date,
            market=self.market
        )

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        return CCXTOHLCVBacktestMarketDataSource(
            identifier=self.identifier,
            market=self.market,
            symbol=self.symbol,
            start_date=self.start_date,
            start_date_func=self.start_date_func,
            end_date=self.end_date,
            end_date_func=self.end_date_func,
            timeframe=self.timeframe,
        )


class CCXTOrderBookMarketDataSource(OrderBookMarketDataSource):

    def get_data(self, **kwargs):
        market_service = CCXTMarketService(self.market_credential_service)
        return market_service.get_order_book(
            symbol=self.symbol, market=self.market
        )

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass


class CCXTTickerMarketDataSource(TickerMarketDataSource):

    def __init__(
        self,
        identifier,
        market,
        symbol=None,
        backtest_timeframe=None
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        self._backtest_timeframe = backtest_timeframe

    def get_data(self, **kwargs):
        market_service = CCXTMarketService(self.market_credential_service)

        if self.market is None:

            if "market" not in kwargs:
                raise OperationalException(
                    "Either market or market should be "
                    "passed as a parameter"
                )
            else:
                market = kwargs["market"]
        else:
            market = self.market

        market_service.market = market

        if self.symbol is None:

            if "symbol" not in kwargs:
                raise OperationalException(
                    "Either symbol or symbol should be passed as a parameter"
                )
            else:
                symbol = kwargs["symbol"]
        else:
            symbol = self.symbol

        return market_service.get_ticker(symbol=symbol, market=market)

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        return CCXTTickerBacktestMarketDataSource(
            identifier=self.identifier,
            market=self.market,
            symbol=self.symbol,
            timeframe=self._backtest_timeframe,
        )
