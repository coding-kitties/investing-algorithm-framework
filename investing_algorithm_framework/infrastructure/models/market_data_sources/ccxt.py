import logging
import os
import csv
from datetime import datetime, timedelta
from investing_algorithm_framework.infrastructure.services import \
    CCXTMarketService
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    BACKTEST_DATA_DIRECTORY_NAME, DATETIME_FORMAT_BACKTESTING, \
    OperationalException, DATETIME_FORMAT, OHLCVMarketDataSource, \
    BacktestMarketDataSource, OrderBookMarketDataSource, \
    TickerMarketDataSource

logger = logging.getLogger(__name__)


class CCXTOHLCVBacktestMarketDataSource(
    OHLCVMarketDataSource, BacktestMarketDataSource
):
    backtest_data_directory = None
    backtest_data_index_date = None
    backtest_data_start_date = None
    backtest_data_end_date = None
    total_minutes_timeframe = None

    def __init__(
        self,
        identifier,
        market,
        symbol,
        timeframe,
        start_date,
        start_date_func=None,
        end_date_func=None,
        end_date=None
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            start_date_func=start_date_func,
            end_date=end_date,
            end_date_func=end_date_func
        )

    def prepare_data(self, config, backtest_start_date, backtest_end_date):
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
                minutes=self.total_minutes_timeframe
            )
        self.backtest_data_start_date = backtest_data_start_date
        self.backtest_data_index_date = backtest_data_start_date
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
                with open(file_path, 'w') as file:
                    pass
            except Exception as e:
                logger.error(e)
                raise OperationalException(
                    f"Could not create backtest data file {file_path}"
                )

        # Get the OHLCV data from the ccxt market service
        market_service = CCXTMarketService()
        market_service.market = self.market
        ohlcv = market_service.get_ohlcv(
            symbol=self.symbol,
            time_frame=self.timeframe,
            from_timestamp=backtest_data_start_date,
            to_timestamp=backtest_end_date
        )
        self.write_ohlcv_to_file(file_path, ohlcv)

    def write_ohlcv_to_file(self, data_file, data):

        with open(data_file, "w") as file:
            column_headers = [
                "Datetime", "Open", "High", "Low", "Close", "Volume"
            ]
            writer = csv.writer(file)
            writer.writerow(column_headers)
            rows = data
            writer.writerows(rows)

    def _create_file_path(self):
        symbol_string = self.symbol.replace("/", "-")
        time_frame_string = self.timeframe.replace("_", "")
        return os.path.join(
            self.backtest_data_directory,
            os.path.join(
                f"OHLCV_"
                f"{symbol_string}_"
                f"{time_frame_string}_"
                f"{self.backtest_data_start_date.strftime(DATETIME_FORMAT_BACKTESTING)}_"
                f"{self.backtest_data_end_date.strftime(DATETIME_FORMAT_BACKTESTING)}.csv"
            )
        )

    def get_data(self, backtest_index_date, **kwargs):
        file_path = self._create_file_path()
        to_timestamp = backtest_index_date
        from_timestamp = backtest_index_date - timedelta(
            minutes=self.total_minutes_timeframe
        )

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

        matching_rows = []

        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row

            for row in reader:
                row_date = datetime.strptime(row[0], DATETIME_FORMAT)

                if from_timestamp <= row_date <= to_timestamp:
                    data = [
                        row_date,
                        float(row[1]),
                        float(row[2]),
                        float(row[3]),
                        float(row[4]),
                        float(row[5]),
                    ]
                    matching_rows.append(data)

        return matching_rows

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # Ignore this method for now
        pass


class CCXTTickerBacktestMarketDataSource(
    TickerMarketDataSource, BacktestMarketDataSource
):
    backtest_data_directory = None
    backtest_data_start_date = None
    backtest_data_end_date = None
    timeframe = "15m"

    def __init__(
        self,
        identifier,
        market,
        symbol=None,
        timeframe="15m"
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        if timeframe is not None:
            self.timeframe = timeframe

    def prepare_data(self, config, backtest_start_date, backtest_end_date):
        self.backtest_data_start_date = backtest_start_date - timedelta(days=1)
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

        # Get the OHLCV data from the ccxt market service
        market_service = CCXTMarketService()
        market_service.market = self.market
        ohlcv = market_service.get_ohlcv(
            symbol=self.symbol,
            time_frame=self.timeframe,
            from_timestamp=self.backtest_data_start_date,
            to_timestamp=backtest_end_date
        )
        self.write_ohlcv_to_file(file_path, ohlcv)

    def write_ohlcv_to_file(self, data_file, data):

        with open(data_file, "w") as file:
            column_headers = [
                "Datetime", "Open", "High", "Low", "Close", "Volume"
            ]
            writer = csv.writer(file)
            writer.writerow(column_headers)
            rows = data
            writer.writerows(rows)

    def _create_file_path(self):

        if self.symbol is None or self.market is None:
            return None

        symbol_string = self.symbol.replace("/", "-")
        market_string = self.market.replace("/", "-")
        return os.path.join(
            self.backtest_data_directory,
            os.path.join(
                f"TICKER_"
                f"{symbol_string}_"
                f"{market_string}_"
                f"{self.backtest_data_start_date.strftime(DATETIME_FORMAT_BACKTESTING)}_"
                f"{self.backtest_data_end_date.strftime(DATETIME_FORMAT_BACKTESTING)}.csv"
            )
        )

    def get_data(self, backtest_index_date, **kwargs):
        file_path = self._create_file_path()

        if file_path is None:
            return self._get_ticker_from_ccxt(backtest_index_date, **kwargs)
        else:
            return self._get_ticker_from_file(file_path, backtest_index_date)

    def _get_ticker_from_ccxt(self, backtest_index_date, **kwargs):
        market_service = CCXTMarketService()

        if self.market is None:

            if "market" not in kwargs:
                raise OperationalException(
                    "Either market should be set as an attribute "
                    "or market should be passed as a parameter for "
                    "CCXTTickerBacktestMarketDataSource"
                )
            else:
                market = kwargs["market"]
        else:
            market = self.market

        market_service.market = market

        if self.symbol is None:

            if "symbol" not in kwargs:
                raise OperationalException(
                    "Either symbol shoudl be set as an attribute "
                    "or symbol should be passed as a parameter for the "
                    "CCXTTickerBacktestMarketDataSource"
                )
            else:
                symbol = kwargs["symbol"]
        else:
            symbol = self.symbol

        ohlcv = market_service.get_ohlcv(
            symbol=symbol,
            time_frame="15m",
            from_timestamp=backtest_index_date - timedelta(minutes=15),
            to_timestamp=backtest_index_date + timedelta(minutes=15)
        )
        return ohlcv[1]

    def _get_ticker_from_file(self, file_path, backtest_index_date):
        file_path = self._create_file_path()
        to_timestamp = backtest_index_date

        if backtest_index_date < self.backtest_data_start_date:
            raise OperationalException(
                f"Cannot get data from {backtest_index_date} as the "
                f"backtest data starts at {self.backtest_data_start_date}"
            )

        if backtest_index_date > self.backtest_data_end_date:
            raise OperationalException(
                f"Cannot get data to {to_timestamp} as the "
                f"backtest data ends at {self.backtest_data_end_date}"
            )

        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row
            previous_row = None

            for row in reader:
                row_date = datetime.strptime(row[0], DATETIME_FORMAT)

                if backtest_index_date <= row_date:

                    if backtest_index_date == row_date:
                        return {
                            "symbol": self.symbol,
                            "bid": float(row[4]),
                            "ask": float(row[4]),
                            "datetime": row[0],
                        }
                    elif previous_row is not None:
                        return {
                            "symbol": self.symbol,
                            "bid": float(previous_row[4]),
                            "ask": float(previous_row[4]),
                            "datetime": previous_row[0],
                        }
                    else:
                        raise OperationalException(
                            f"Could not find ticker data for date "
                            f"{backtest_index_date}"
                        )
                else:
                    previous_row = row

        if previous_row is not None:
            difference = backtest_index_date - datetime\
                .strptime(previous_row[0], DATETIME_FORMAT)
            difference_in_minutes = difference.days * 24 * 60 + \
                difference.seconds / 60

            # If the difference is more than 4 hours, we can assume
            # that the data is not available
            if difference_in_minutes <= 240:
                return {
                    "symbol": self.symbol,
                    "bid": float(previous_row[3]) + float(previous_row[2]) / 2,
                    "ask": float(previous_row[3]) + float(previous_row[2]) / 2,
                    "datetime": previous_row[0],
                }

        raise OperationalException(
            f"Could not find {self.symbol} ticker data for date "
            f"{backtest_index_date}. Please make sure that the selected "
            f"broker or exchange {self.market} has ticker data"
            f" available for symbol {self.symbol}"
        )

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # Ignore this method for now
        pass


class CCXTOHLCVMarketDataSource(OHLCVMarketDataSource):

    def get_data(self, **kwargs):
        market_service = CCXTMarketService()
        market_service.market = self.market

        if self.start_date is None:
            raise OperationalException(
                "Either start_date or start_date_func should be set "
                "for OHLCVMarketDataSource"
            )

        return market_service.get_ohlcv(
            symbol=self.symbol,
            time_frame=self.timeframe,
            from_timestamp=self.start_date,
            to_timestamp=self.end_date
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
            timeframe=self.timeframe
        )


class CCXTOrderBookMarketDataSource(OrderBookMarketDataSource):

    def get_data(self, **kwargs):
        market_service = CCXTMarketService()
        market_service.market = self.market
        return market_service.get_order_book(
            symbol=self.symbol,
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
        market_service = CCXTMarketService()

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

        return market_service.get_ticker(symbol=symbol)

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        return CCXTTickerBacktestMarketDataSource(
            identifier=self.identifier,
            market=self.market,
            symbol=self.symbol,
            timeframe=self._backtest_timeframe
        )
