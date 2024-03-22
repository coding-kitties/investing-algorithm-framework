from datetime import datetime

import pandas as pd
from dateutil.parser import parse

from investing_algorithm_framework.domain import OHLCVMarketDataSource, \
    BacktestMarketDataSource, OperationalException, TickerMarketDataSource


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
        df = pd.read_csv(self._csv_file_path)

        if not all(column in df.columns for column in self._columns):
            # Identify missing columns
            missing_columns = [column for column in self._columns if
                               column not in df.columns]
            raise OperationalException(
                f"Csv file {self._csv_file_path} does not contain "
                f"all required ohlcv columns. "
                f"Missing columns: {missing_columns}"
            )

        first_row = df.iloc[0]
        last_row = df.iloc[-1]
        self._start_date = parse(first_row[0])
        self._end_date = parse(last_row[0])

    @property
    def csv_file_path(self):
        return self._csv_file_path

    def get_data(
        self,
        from_time_stamp=None,
        to_time_stamp=None,
        **kwargs
    ):

        if from_time_stamp is None:
            from_time_stamp = self.start_date

        if to_time_stamp is None:
            to_time_stamp = self.end_date

        df = pd.read_csv(self._csv_file_path)

        # Convert the 'Datetime' column to datetime type if
        # it's not already
        if 'Datetime' in df.columns and pd.api.types.is_string_dtype(
                df['Datetime']):
            df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True)

        # Filter rows based on the start and end dates
        filtered_df = df[
            (df['Datetime'] >= from_time_stamp)
            & (df['Datetime'] <= to_time_stamp)
        ]

        # Specify the columns you want in the inner lists
        selected_columns = ["Datetime", "Open", "High", "Low", "Close",
                            "Volume"]

        # Convert DataFrame to a list of lists with selected columns
        filtered_list_of_lists = \
            self.dataframe_to_list_of_lists(filtered_df, selected_columns)

        return filtered_list_of_lists

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
        df = pd.read_csv(self._csv_file_path)

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

        index_datetime = pd.to_datetime(index_datetime, utc=True)
        df = pd.read_csv(self._csv_file_path)

        # Convert the 'Datetime' column to datetime type if
        # it's not already
        if 'Datetime' in df.columns and pd.api.types.is_string_dtype(
                df['Datetime']):
            df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True)

        # Filter rows based on the start and end dates
        filtered_df = df[(df['Datetime'] <= index_datetime)]

        if len(filtered_df) == 0:
            return None

        last_row = filtered_df.iloc[-1]
        return {
            "symbol": self.symbol,
            "bid": (float(last_row[3]) + float(last_row[2])) / 2,
            "ask": (float(last_row[3]) + float(last_row[2])) / 2,
            "datetime": last_row[0],
        }

    def dataframe_to_list_of_lists(self, dataframe, columns):
        # Extract selected columns from DataFrame and convert
        # to a list of lists
        data_list_of_lists = dataframe[columns].values.tolist()
        return data_list_of_lists

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass
