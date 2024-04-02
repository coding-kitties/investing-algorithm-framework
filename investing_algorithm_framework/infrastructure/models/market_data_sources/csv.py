from datetime import datetime
import polars
import logging

from dateutil.parser import parse

from investing_algorithm_framework.domain import OHLCVMarketDataSource, \
    BacktestMarketDataSource, OperationalException, TickerMarketDataSource, \
    DATETIME_FORMAT

logger = logging.getLogger(__name__)


class CSVOHLCVMarketDataSource(OHLCVMarketDataSource):

    def empty(self):
        data = self.get_data(
            from_time_stamp=self.start_date,
            to_time_stamp=self.end_date
        )
        return len(data) == 0

    def __init__(
        self,
        csv_file_path,
        identifier=None,
        market=None,
        symbol=None,
        timeframe=None,
        start_date=None,
        start_date_func=None,
        end_date=None,
        end_date_func=None,
        window_size=None,
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
        self._start_date = parse(first_row["Datetime"][0])
        self._end_date = parse(last_row["Datetime"][0])

    @property
    def csv_file_path(self):
        return self._csv_file_path

    def get_data(
        self,
        from_timestamp=None,
        to_timestamp=None,
        **kwargs
    ):

        if from_timestamp is None:
            from_timestamp = self.start_date

        if to_timestamp is None:
            to_timestamp = self.end_date

        df = polars.read_csv(
            self.csv_file_path, columns=self._columns, separator=","
        )
        df = df.filter(
            (df['Datetime'] >= from_timestamp.strftime(DATETIME_FORMAT))
            & (df['Datetime'] <= to_timestamp.strftime(DATETIME_FORMAT))
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

    @property
    def csv_file_path(self):
        return self._csv_file_path

    def get_data(self, index_datetime=None, **kwargs):

        if index_datetime is None:
            index_datetime = datetime.utcnow()

        # Filter the data based on the backtest index date and the end date
        df = polars.read_csv(self._csv_file_path)
        df = df.filter(
            (df['Datetime'] >= index_datetime
             .strftime(DATETIME_FORMAT))
        )

        # Check if the dataframe is empty
        if df.shape[0] == 0:
            raise OperationalException(
                f"No ticker data found for {self.symbol} "
                f"at {index_datetime}"
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
