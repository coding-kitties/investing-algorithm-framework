import datetime
import logging
import os
from datetime import timedelta
from dateutil.parser import parse
import polars
from dateutil import parser

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
    total_minutes_time_frame = None
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        identifier,
        market,
        symbol,
        time_frame,
        window_size=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            time_frame=time_frame,
            window_size=window_size,
        )
        self.data = None
        self._start_date_data_source = None
        self._end_date_data_source = None

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

        Parameters:
            config: dict - the configuration of the data source
            backtest_start_date: datetime - the start date of the backtest
            backtest_end_date: datetime - the end date of the backtest
            time_frame: string - the time frame of the data
            window_size: int - the total amount of candle sticks that need to
            be returned
        
        Returns:
            None
        """
        # Calculating the backtest data start date
        backtest_data_start_date = \
            backtest_start_date - timedelta(
                minutes=(
                    (self.window_size + 1) *
                    TimeFrame.from_value(self.time_frame).amount_of_minutes
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
            market_service = CCXTMarketService(
                market_credential_service=self.market_credential_service,
            )
            market_service.config = config
            ohlcv = market_service.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=backtest_data_start_date,
                to_timestamp=backtest_end_date,
                market=self.market
            )
            self.write_data_to_file_path(file_path, ohlcv)

        self.load_data()

    def load_data(self):
        file_path = self._create_file_path()
        self.data = polars.read_csv(file_path)
        first_row = self.data.head(1)
        last_row = self.data.tail(1)
        self._start_date_data_source = parse(first_row["Datetime"][0])
        self._end_date_data_source = parse(last_row["Datetime"][0])

    def _create_file_path(self):
        """
        Function to create a filename in the following format:
        OHLCV_{symbol}_{market}_{time_frame}_{start_date}_{end_date}.csv
        """
        symbol_string = self.symbol.replace("/", "-")
        time_frame_string = self.time_frame.replace("_", "")
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

    def get_data(self, **kwargs):
        """
        Get data implementation of ccxt based ohlcv backtest market data
        source. This implementation will use polars to load and filter the
        data.
        """
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        backtest_index_date = kwargs.get("backtest_index_date")

        if self.data is None:
            self.load_data()

        if start_date is None \
                and end_date is None \
                and backtest_index_date is None:
            return self.data

        if backtest_index_date is not None:
            end_date = backtest_index_date
            start_date = self.create_start_date(
                end_date, self.time_frame, self.window_size
            )
        else:
            if start_date is None:
                start_date = self.create_start_date(
                    end_date, self.time_frame, self.window_size
                )

            if end_date is None:
                end_date = self.create_end_date(
                    start_date, self.time_frame, self.window_size
                )

        if start_date < self._start_date_data_source:
            raise OperationalException(
                f"Start date {start_date} is before the start date "
                f"of the data source {self._start_date_data_source}"
            )

        if end_date > self._end_date_data_source:
            raise OperationalException(
                f"End date {end_date} is after the end date "
                f"of the data source {self._end_date_data_source}"
            )
        
        time_frame = TimeFrame.from_string(self.time_frame)
        start_date = start_date - timedelta(minutes=time_frame.amount_of_minutes)
        selection = self.data.filter(
            (self.data['Datetime'] >= start_date.strftime(DATETIME_FORMAT))
            & (self.data['Datetime'] <= end_date.strftime(DATETIME_FORMAT))
        )

        return selection

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # Ignore this method for now
        pass

    def empty(self):
        return False

    @property
    def file_name(self):
        return self._create_file_path().split("/")[-1]

    def write_data_to_file_path(self, data_file, data: polars.DataFrame):
        data.write_csv(data_file)


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
    01-01-2024 - amount of minutes of the provided time_frame)

    To achieve this, a backtest_data_start_date attribute is used. This
    attribute is indexed on this calculated date.
    """
    backtest_data_directory = None
    backtest_data_start_date = None
    backtest_data_end_date = None
    time_frame = None
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        identifier,
        market,
        symbol=None,
        time_frame=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )

        if time_frame is not None:
            self.time_frame = time_frame

        if self.time_frame is None:
            raise OperationalException(
                "time_frame should be set for "
                "CCXTTickerBacktestMarketDataSource"
            )

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
        total_minutes = TimeFrame.from_string(self.time_frame)\
            .amount_of_minutes
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
            market_service = CCXTMarketService(
                market_credential_service=self.market_credential_service
            )
            market_service.config = config
            ohlcv = market_service.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
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
        backtest_index_date = kwargs["backtest_index_date"]

        # Filter the data based on the backtest index date and the end date
        df = polars.read_csv(file_path)
        filtered_df = df.filter(
            (df['Datetime'] >= backtest_index_date.strftime(DATETIME_FORMAT))
        )

        # If nothing is found, get all dates before the index date
        if len(filtered_df) == 0:
            filtered_df = df.filter(
                (df['Datetime'] <= backtest_index_date.strftime(
                    DATETIME_FORMAT))
            )
            first_row = filtered_df.tail(1)[0]
        else:
            first_row = filtered_df.head(1)[0]

        first_row_datetime = parser.parse(first_row["Datetime"][0])

        # Calculate the bid and ask price based on the high and low price
        return {
            "symbol": self.symbol,
            "bid": float((first_row["Low"][0])
                         + float(first_row["High"][0]))/2,
            "ask": float((first_row["Low"][0])
                         + float(first_row["High"][0]))/2,
            "datetime": first_row_datetime,
        }

    def write_data_to_file_path(self, data_file, data: polars.DataFrame):
        data.write_csv(data_file)


class CCXTOHLCVMarketDataSource(OHLCVMarketDataSource):
    """
    CCXTOHLCVMarketDataSource implementation of OHLCVMarketDataSource using
    ccxt to download all ohlcv data sources.
    """

    def get_data(self, **kwargs):
        """
        Implementation of get_data for CCXTOHLCVMarketDataSource.
        This implementation uses the CCXTMarketService to get the OHLCV data.

        Parameters:
            window_size: int (optional) - the total amount of candle
            sticks that need to be returned
            start_date: datetime (optional) - the start date of the data. The
            first candle stick should close to this date.
            end_date: datetime (optional) - the end date of the data. The last
            candle stick should close to this date.
            storage_path: string (optional) - the storage path specifies the
            directory where the data is written to or read from.
                If set the data provider will write all its downloaded data
                to this location. Also, it will check if the
                data already exists at the storage location. If this is the
                case it will return this.

        Returns
            polars.DataFrame with the OHLCV data
        """
        market_service = CCXTMarketService(
            market_credential_service=self.market_credential_service,
        )

        # Add config if present
        if self.config is not None:
            market_service.config = self.config

        if "window_size" in kwargs:
            self.window_size = kwargs["window_size"]

        if "start_date" in kwargs:
            start_date = kwargs["start_date"]

            if not isinstance(start_date, datetime.datetime):
                raise OperationalException(
                    "start_date should be a datetime object"
                )
        else:
            raise OperationalException(
                "start_date should be set for CCXTOHLCVMarketDataSource"
            )

        if "end_date" not in kwargs:

            if self.window_size is None:
                raise OperationalException(
                    "Either end_date or window_size "
                    "should be passed as a "
                    "parameter for CCXTOHLCVMarketDataSource"
                )

            end_date = self.create_end_date(
                start_date, self.time_frame, self.window_size
            )
        else:
            end_date = kwargs["end_date"]

            if not isinstance(end_date, datetime.datetime):
                raise OperationalException(
                    "end_date should be a datetime object"
                )

        if not isinstance(start_date, datetime.datetime):
            raise OperationalException(
                "start_date should be a datetime object"
            )

        if "storage_path" in kwargs:
            storage_path = kwargs["storage_path"]
        else:
            storage_path = self.get_storage_path()

        data = None

        if storage_path is not None:
            # Check if data is already in storage
            data = self._get_data_from_storage(
                storage_path=storage_path,
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=start_date,
                to_timestamp=end_date,
                market=self.market,
            )

        if data is None:
            # Get the OHLCV data from the ccxt market service
            data = market_service.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=start_date,
                to_timestamp=end_date,
                market=self.market
            )

        # if storage path is set, write the data to the storage path
        if storage_path is not None:
            self.write_data_to_storage(
                data=data,
                storage_path=storage_path,
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=start_date,
                to_timestamp=end_date,
                market=self.market,
                data_type="OHLCV"
            )

        return data

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:

        if self.window_size is None:
            raise OperationalException(
                "Window_size should be defined before the " + 
                "CCXTOHLCVMarketDataSource can be converted to " +
                "a backtest market data source. Make sure to set " +
                "the window_size attribute on your CCXTOHLCVMarketDataSource"
            )
        
        return CCXTOHLCVBacktestMarketDataSource(
            identifier=self.identifier,
            market=self.market,
            symbol=self.symbol,
            time_frame=self.time_frame,
            window_size=self.window_size
        )

    def _get_data_from_storage(
        self,
        storage_path,
        symbol,
        time_frame,
        from_timestamp,
        to_timestamp,
        market
    ):
        """
        Function to get data from the storage path:

        Parameters:
            storage_path: string - the storage path where the
            data should be in.

        Return:
            Polars dataframe.
        """

        if not os.path.isdir(storage_path):
            return None

        if not os.path.isdir(storage_path):
            return None

        for filename in os.listdir(storage_path):
            path = os.path.join(storage_path, filename)

            if os.path.isfile(path) or path.split('.')[-1] != ".csv":
                continue

            file_name_symbol = self.get_file_name_symbol(path)
            file_name_market = self.get_file_name_market(path)
            file_name_time_frame = self.get_file_name_time_frame(path)
            file_name_start_date = self.get_file_name_start_date(path)
            file_name_end_date = self.get_file_name_end_date(path)

            if file_name_symbol == symbol \
                    and file_name_market == market \
                    and file_name_time_frame == time_frame \
                    and file_name_start_date >= from_timestamp \
                    and file_name_end_date <= to_timestamp:
                return polars.read_csv(path)

        return None

    def write_data_to_storage(
        self,
        data: polars.DataFrame,
        storage_path,
        symbol,
        time_frame,
        from_timestamp,
        to_timestamp,
        market,
        data_type="OHLCV"
    ):
        """
        Function to write data to the storage path:

        Parameters:
            data: polars.DataFrame - the data that should be written to the
                storage path.
            storage_path: string - the storage path where the data should
                be written to.
            symbol: string - the symbol of the data.
            time_frame: string - the time_frame of the data.
            from_timestamp: datetime - the start date of the data.
            to_timestamp: datetime - the end date of the data.
            market: string - the market of the data.

        Return:
            None
        """

        if not os.path.isdir(storage_path):
            os.mkdir(storage_path)

        file_path = self.create_storage_file_path(
            storage_path=storage_path,
            symbol=symbol,
            time_frame=time_frame,
            start_datetime=from_timestamp,
            end_datetime=to_timestamp,
            market=market,
            data_type=data_type
        )

        if os.path.isfile(file_path):
            return

        else:
            try:
                with open(file_path, 'w') as _:
                    pass
            except Exception as e:
                logger.error(e)
                raise OperationalException(
                    f"Could not create data file {file_path}"
                )

            data.write_csv(file_path)


class CCXTOrderBookMarketDataSource(OrderBookMarketDataSource):

    def get_data(self, **kwargs):
        market_service = CCXTMarketService(
            market_credential_service=self.market_credential_service
        )
        market_service.config = self.config
        return market_service.get_order_book(
            symbol=self.symbol, market=self.market
        )

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass


class CCXTTickerMarketDataSource(TickerMarketDataSource):

    def __init__(
        self,
        market,
        identifier=None,
        symbol=None,
        backtest_time_frame=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        self._backtest_time_frame = backtest_time_frame

    def get_data(self, **kwargs):
        market_service = CCXTMarketService(
            market_credential_service=self.market_credential_service
        )
        market_service.config = self.config

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

        if self._backtest_time_frame is None:
            raise OperationalException(
                "Backtest time frame should be defined before the " +
                "CCXTTickerMarketDataSource can be converted to " +
                "a backtest market data source. Make sure to set " +
                "the backtest_time_frame attribute on your " +
                "CCXTTickerMarketDataSource"
            )
        
        return CCXTTickerBacktestMarketDataSource(
            identifier=self.identifier,
            market=self.market,
            symbol=self.symbol,
            time_frame=self._backtest_time_frame,
        )
