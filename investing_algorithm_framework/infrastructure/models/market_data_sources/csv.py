import logging
from datetime import datetime, timedelta

import polars
from dateutil.parser import parse

from investing_algorithm_framework.domain import OHLCVMarketDataSource, \
    BacktestMarketDataSource, OperationalException, TickerMarketDataSource, \
    DATETIME_FORMAT, TimeFrame

logger = logging.getLogger(__name__)


class CSVOHLCVMarketDataSource(OHLCVMarketDataSource):
    """
    Implementation of a OHLCV data source that reads OHLCV data from a csv file.
    Market data source that reads OHLCV data from a csv file.
    """

    def empty(self, start_date, end_date=None):
        if end_date is None:
            end_date = self.create_end_date(start_date, self.timeframe, self.window_size)
        data = self.get_data(start_date=start_date, end_date=end_date)
        return len(data) == 0

    def __init__(
        self,
        csv_file_path,
        identifier=None,
        market=None,
        symbol=None,
        timeframe=None,
        window_size=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            window_size=window_size,
        )
        self._csv_file_path = csv_file_path
        self._columns = [
            "Datetime", "Open", "High", "Low", "Close", "Volume"
        ]
        df = polars.read_csv(csv_file_path)

        # Check if all column names are in the csv file
        if not all(column in df.columns for column in self._columns):
            # Identify missing columns
            missing_columns = [column for column in self._columns if
                               column not in df.columns]
            raise OperationalException(
                f"Csv file {self._csv_file_path} does not contain "
                f"all required ohlcv columns. "
                f"Missing columns: {missing_columns}"
            )

        first_row = df.head(1)
        last_row = df.tail(1)
        self._start_date_data_source = parse(first_row["Datetime"][0])
        self._end_date_data_source = parse(last_row["Datetime"][0])

    @property
    def csv_file_path(self):
        return self._csv_file_path

    def get_data(self, **kwargs):
        """
        Get the data from the csv file. The data can be filtered by
        the start_date and end_date in the kwargs. backtest_index_date
        can also be provided to filter the data, where this will be used
        as start_date.

        Args:
            **kwargs: Keyword arguments that can contain the following:
                start_date (datetime): The start date to filter the data.
                end_date (datetime): The end date to filter the data.
                backtest_index_date (datetime): The backtest index date to
                    filter the data. This will be used as start_date.

        Returns:
            df (polars.DataFrame): The data from the csv file.
        """
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        backtest_index_date = kwargs.get("backtest_index_date")

        if start_date is None \
                and end_date is None \
                and backtest_index_date is None:
            return polars.read_csv(
                self.csv_file_path, columns=self._columns, separator=","
            )

        if backtest_index_date is not None:
            end_date = backtest_index_date
            start_date = self.create_start_date(
                end_date, self.timeframe, self.window_size
            )
        else:
            if start_date is None:
                start_date = self.create_start_date(
                    end_date, self.timeframe, self.window_size
                )

            if end_date is None:
                end_date = self.create_end_date(
                    start_date, self.timeframe, self.window_size
                )

        # # Check if start or end date are out of range with
        # # the dates of the datasource.
        # if self._start_date_data_source > start_date:
        #     raise OperationalException(
        #         f"Given start date {start_date} is before the start date "
        #         f"of the data source {self._start_date_data_source}"
        #     )
        #
        # if self._end_date_data_source < end_date:
        #     raise OperationalException(
        #         f"End date {end_date} is after the end date "
        #         f"of the data source {self._end_date_data_source}"
        #     )

        df = polars.read_csv(
            self.csv_file_path, columns=self._columns, separator=","
        )
        df = df.filter(
            (df['Datetime'] >= start_date.strftime(DATETIME_FORMAT))
            & (df['Datetime'] <= end_date.strftime(DATETIME_FORMAT))
        )
        return df

    def dataframe_to_list_of_lists(self, dataframe, columns):
        # Extract selected columns from DataFrame and convert
        # to a list of lists
        data_list_of_lists = dataframe[columns].values.tolist()
        return data_list_of_lists

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass


class CSVTickerMarketDataSource(TickerMarketDataSource):

    def __init__(
        self,
        identifier,
        market,
        symbol,
        csv_file_path,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        self._csv_file_path = csv_file_path
        self._columns = [
            "Datetime", "Open", "High", "Low", "Close", "Volume"
        ]
        df = polars.read_csv(self._csv_file_path)

        if not all(column in df.columns for column in self._columns):
            # Identify missing columns
            missing_columns = [column for column in self._columns if
                               column not in df.columns]
            raise OperationalException(
                f"Csv file {self._csv_file_path} does not contain "
                f"all required ohlcv columns. "
                f"Missing columns: {missing_columns}"
            )

        first_row = df.head(1)
        last_row = df.tail(1)
        self._start_date_data_source = parse(first_row["Datetime"][0])
        self._end_date_data_source = parse(last_row["Datetime"][0])

    @property
    def csv_file_path(self):
        return self._csv_file_path

    def get_data(self, **kwargs):
        date = None

        if "index_datetime" in kwargs:
            date = kwargs["index_datetime"]

        if "start_date" in kwargs:
            date = kwargs["start_date"]

        if 'date' in kwargs:
            date = kwargs['date']

        if date is None:
            raise OperationalException("Date is required to get ticker data")

        if not isinstance(date, datetime):

            if isinstance(date, str):
                date = parse(date)
            else:
                raise OperationalException(
                    "Date value should be either a string or datetime object"
                )

        if date < self._start_date_data_source:
            raise OperationalException(
                f"Date {date} is before the start date "
                f"of the data source {self._start_date_data_source}"
            )

        if date > self._end_date_data_source:
            raise OperationalException(
                f"Date {date} is after the end date "
                f"of the data source {self._end_date_data_source}"
            )

        # Filter the data based on the backtest index date and the end date
        df = polars.read_csv(self._csv_file_path)
        df = df.filter(
            (df['Datetime'] >= date.strftime(DATETIME_FORMAT))
        )

        # Check if the dataframe is empty
        if df.shape[0] == 0:
            raise OperationalException(
                f"No ticker data found for {self.symbol} "
                f"at {date.strftime(DATETIME_FORMAT)}"
            )

        first_row = df.head(1)[0]

        # Calculate the bid and ask price based on the high and low price
        return {
            "symbol": self.symbol,
            "bid": float((first_row["Low"][0])
                         + float(first_row["High"][0])) / 2,
            "ask": float((first_row["Low"][0])
                         + float(first_row["High"][0])) / 2,
            "datetime": first_row["Datetime"][0],
        }

    def dataframe_to_list_of_lists(self, dataframe, columns):
        # Extract selected columns from DataFrame and convert
        # to a list of lists
        data_list_of_lists = dataframe[columns].values.tolist()
        return data_list_of_lists

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass
