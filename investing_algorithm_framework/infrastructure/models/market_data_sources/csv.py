import logging
from datetime import datetime

import polars
from dateutil.parser import parse

from investing_algorithm_framework.domain import OHLCVMarketDataSource, \
    BacktestMarketDataSource, OperationalException, TickerMarketDataSource, \
    DATETIME_FORMAT

logger = logging.getLogger(__name__)


class CSVOHLCVMarketDataSource(OHLCVMarketDataSource):
    """
    Implementation of a OHLCV data source that reads OHLCV data
    from a csv file. Market data source that reads OHLCV data from a csv file.
    """

    def empty(self, end_date):
        data = self.get_data(end_date=end_date, config={})
        return len(data) == 0

    def __init__(
        self,
        csv_file_path,
        market=None,
        symbol=None,
        identifier=None,
        window_size=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            time_frame=None,
            window_size=window_size,
        )
        self._csv_file_path = csv_file_path
        self._columns = [
            "Datetime", "Open", "High", "Low", "Close", "Volume"
        ]

        df = polars.read_csv(self._csv_file_path)

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

        self.data = self._load_data(self.csv_file_path)
        first_row = self.data.head(1)
        last_row = self.data.tail(1)
        self._start_date_data_source = first_row["Datetime"][0]
        self._end_date_data_source = last_row["Datetime"][0]

    @property
    def csv_file_path(self):
        return self._csv_file_path

    def _load_data(self, file_path):
        return polars.read_csv(
            file_path,
            schema_overrides={"Datetime": polars.Datetime},
            low_memory=True
        ).with_columns(
            polars.col("Datetime").cast(
                polars.Datetime(time_unit="ms", time_zone="UTC")
            )
        )

    def get_data(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        config=None,
    ):
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

        if start_date is None and end_date is None:
            return self.data

        if end_date is not None and start_date is not None:

            if end_date < start_date:
                raise OperationalException(
                    f"End date {end_date} is before the start date "
                    f"{start_date}"
                )

            if start_date > self._end_date_data_source:
                return polars.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] >= start_date)
                & (df['Datetime'] <= end_date)
            )
            return df

        if start_date is not None:

            if start_date < self._start_date_data_source:
                return polars.DataFrame()

            if start_date > self._end_date_data_source:
                return polars.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] >= start_date)
            )
            df = df.head(self.window_size)
            return df

        if end_date is not None:

            if end_date < self._start_date_data_source:
                return polars.DataFrame()

            if end_date > self._end_date_data_source:
                return polars.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] <= end_date)
            )
            df = df.tail(self.window_size)
            return df

        return polars.read_csv(
            self.csv_file_path, columns=self._columns, separator=","
        )

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

    def get_data(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        config=None,
    ):

        if end_date is None:
            raise OperationalException("Date is required to get ticker data")

        date = end_date

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
