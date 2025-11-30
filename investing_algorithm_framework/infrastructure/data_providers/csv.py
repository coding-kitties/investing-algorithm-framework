from typing import List, Union
from datetime import datetime, timezone, timedelta

import polars as pl

from investing_algorithm_framework.domain import DataProvider, \
    OperationalException, DataSource, DataType, TimeFrame, \
    convert_polars_to_pandas


class CSVOHLCVDataProvider(DataProvider):
    """
    Implementation of Data Provider for OHLCV data. OHLCV data
    will be loaded from a CSV file. The CSV file should contain
    the following columns: Datetime, Open, High, Low, Close, Volume.
    The Datetime column should be in UTC timezone and in milliseconds.
    The data will be loaded into a Polars DataFrame and will be kept in memory.

    Attributes:
        data_type (DataType): The type of data provided by this provider,
            which is OHLCV.
        data_provider_identifier (str): Identifier for the CSV OHLCV data
            provider.
        _start_date_data_source (datetime): The start date of the data
            source, determined from the first row of the data.
        _end_date_data_source (datetime): The end date of the data
            source, determined from the last row of the data.
        data (polars.DataFrame): The OHLCV data loaded from the CSV file.
    """
    data_type = DataType.OHLCV
    data_provider_identifier = "csv_ohlcv_data_provider"

    def __init__(
        self,
        storage_path: str,
        symbol: str,
        time_frame: str,
        market: str,
        window_size=None,
        data_provider_identifier: str = None,
        pandas: bool = False,
    ):
        """
        Initialize the CSV Data Provider.

        Args:
            storage_path (str): Path to the CSV file.
            symbol (str): The symbol for which the data is provided.
            time_frame (str): The time frame for the data.
            market (str, optional): The market for the data. Defaults to None.
            window_size (int, optional): The window size for the data.
                Defaults to None.
        """
        if data_provider_identifier is None:
            data_provider_identifier = self.data_provider_identifier
        super().__init__(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            window_size=window_size,
            storage_path=storage_path,
            data_provider_identifier=data_provider_identifier,
            data_type=DataType.OHLCV.value
        )
        self._start_date_data_source = None
        self._end_date_data_source = None
        self._columns = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        self.window_cache = {}
        self._load_data(self.storage_path)
        self.pandas = pandas
        self.number_of_missing_data_points = 0
        self.missing_data_point_dates: List[datetime] = []

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> bool:
        """
        Implementation of the has_data method to check if
        the data provider has data for the given data source.

        Args:
            data_source (DataSource): The data source to check.
            start_date (datetime, optional): The start date for the data.
                Defaults to None.
            end_date (datetime, optional): The end date for the data.
                Defaults to None.

        Returns:
            bool: True if the data provider has data for the given data source,
                False otherwise.
        """
        if start_date is None and end_date is None:
            return False

        if DataType.OHLCV.equals(data_source.data_type) and \
                data_source.symbol == self.symbol and \
                data_source.time_frame.equals(self.time_frame) and \
                data_source.market == self.market:

            if end_date > self._end_date_data_source:
                return False

            if data_source.window_size is not None:
                minutes = TimeFrame.from_value(
                    data_source.time_frame
                ).amount_of_minutes * data_source.window_size
                required_start_date = end_date - timedelta(
                    minutes=minutes
                )

                if required_start_date < self._start_date_data_source:
                    return False
            else:
                required_start_date = start_date
                if required_start_date < self._start_date_data_source:
                    return False

            return True

        return False

    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False,
    ):
        """
        Fetches OHLCV data for a given symbol and date range.
        If no date range is provided, it returns the entire dataset.

        Args:
            date (datetime, optional): A specific date to fetch data for.
                Defaults to None.
            start_date (datetime, optional): The start date for the data.
                Defaults to None.
            end_date (datetime, optional): The end date for the data.
                Defaults to None.
            save (bool, optional): Whether to save the data to a file.

        Returns:
            polars.DataFrame: A DataFrame containing the OHLCV data for the
                specified symbol and date range.
        """
        windows_size = self.window_size

        if start_date is None and end_date is None:
            end_date = datetime.now(tz=timezone.utc)
            time_frame = TimeFrame.from_value(self.time_frame)
            start_date = end_date - timedelta(
                minutes=time_frame.amount_of_minutes() * windows_size
            )
        elif start_date is None and end_date is not None:
            start_date = end_date - timedelta(
                minutes=TimeFrame.from_value(
                    self.time_frame
                ).amount_of_minutes * windows_size
            )
            df = self.data
            df = df.filter(
                (df['Datetime'] >= start_date) & (df['Datetime'] <= end_date)
            )
            return df

        if start_date is not None:
            end_date = start_date + timedelta(
                minutes=TimeFrame.from_value(self.time_frame)
                .amount_of_minutes * windows_size
            )

            if start_date < self._start_date_data_source:
                return pl.DataFrame()

            if start_date > self._end_date_data_source:
                return pl.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] >= start_date) & (df['Datetime'] <= end_date)
            )
            return df

        if end_date is not None:
            start_date = end_date - timedelta(
                minutes=TimeFrame.from_value(
                    self.time_frame
                ).amount_of_minutes * windows_size
            )

            if end_date < self._start_date_data_source:
                return pl.DataFrame()

            if end_date > self._end_date_data_source:
                return pl.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] >= start_date) & (df['Datetime'] <= end_date)
            )
            return df

        return self.data

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date
    ) -> None:
        """
        Prepares backtest data for a given symbol and date range.

        Args:
            backtest_start_date (datetime): The start date for the
                backtest data.
            backtest_end_date (datetime): The end date for the
                backtest data.

        Raises:
            OperationalException: If the backtest start date is before the
                start date of the data source or if the backtest end date is
                after the end date of the data source.

        Returns:
            None
        """

        if backtest_start_date < self._start_date_data_source:
            raise OperationalException(
                f"Backtest start date {backtest_start_date} is before the "
                f"start date {self._start_date_data_source}"
            )

        if backtest_end_date > self._end_date_data_source:
            raise OperationalException(
                f"Backtest end date {backtest_end_date} is after the "
                f"end date {self._end_date_data_source}"
            )

        # There must be at least backtest_start_date - window_size * time_frame
        # data available to create a sliding window.
        required_start_date = backtest_start_date - \
            timedelta(
                minutes=TimeFrame.from_value(self.time_frame)
                .amount_of_minutes * self.window_size
            )

        # Create cache with sliding windows
        self._precompute_sliding_windows(
            window_size=self.window_size,
            start_date=backtest_start_date,
            end_date=backtest_end_date
        )

        if required_start_date < self._start_date_data_source:
            self.number_of_missing_data_points = (
                self._start_date_data_source - required_start_date
            ).total_seconds() / (
                TimeFrame.from_value(self.time_frame).amount_of_minutes * 60
            )

        n_min = TimeFrame.from_value(self.time_frame).amount_of_minutes

        # Assume self.data is a Polars DataFrame with a "Datetime" column
        expected_dates = pl.datetime_range(
            start=required_start_date,
            end=backtest_end_date,
            interval=f"{n_min}m",
            eager=True
        ).to_list()

        actual_dates = self.data["Datetime"].to_list()

        # Find missing dates
        self.missing_data_point_dates = sorted(
            set(expected_dates) - set(actual_dates)
        )

    def get_backtest_data(
        self,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        data_source: DataSource = None
    ) -> None:
        """
        Fetches backtest data for a given datasource

        Args:
            backtest_index_date (datetime): The date for which to fetch
               backtest data.
            backtest_start_date (datetime): The start date for the
               backtest data.
            backtest_end_date (datetime): The end date for the
               backtest data.
            data_source (Optional[DataSource]): The data source specification
               that matches a data provider.

        Raises:
            OperationalException: If the requested backtest date range
                is outside the available data range.

        Returns:
           pl.DataFrame: The backtest data for the given datasource.
        """
        if backtest_start_date is not None and \
                backtest_end_date is not None:

            if backtest_start_date < self._start_date_data_source:

                if data_source is not None:
                    raise OperationalException(
                        f"Request data date {backtest_end_date} "
                        f"is after the range of "
                        f"the available data "
                        f"{self._start_date_data_source} "
                        f"- {self._end_date_data_source}."
                        f" for data source {data_source.identifier}."
                    )

                raise OperationalException(
                    f"Request data date {backtest_start_date} "
                    f"is before the range of "
                    f"the available data "
                    f"{self._start_date_data_source} "
                    f"- {self._end_date_data_source}."
                )

            if backtest_end_date > self._end_date_data_source:

                if data_source is not None:
                    raise OperationalException(
                        f"Request data date {backtest_end_date} "
                        f"is after the range of "
                        f"the available data "
                        f"{self._start_date_data_source} "
                        f"- {self._end_date_data_source}."
                        f" for data source {data_source.identifier}."
                    )

                raise OperationalException(
                    f"Request data date {backtest_end_date} "
                    f"is after the range of "
                    f"the available data "
                    f"{self._start_date_data_source} "
                    f"- {self._end_date_data_source}."
                )

            data = self.data.filter(
                (pl.col("Datetime") >= backtest_start_date) &
                (pl.col("Datetime") <= backtest_end_date)
            )
        else:
            try:
                data = self.window_cache[backtest_index_date]
            except KeyError:

                try:
                    # Return the key in the cache that is closest to the
                    # backtest_index_date but not after it.
                    closest_key = min(
                        [k for k in self.window_cache.keys()
                         if k >= backtest_index_date]
                    )
                    data = self.window_cache[closest_key]
                except ValueError:

                    if data_source is not None:
                        raise OperationalException(
                            "No data available for the "
                            f"date: {backtest_index_date} "
                            "within the prepared backtest data "
                            f"for data source {data_source.identifier}."
                        )

                    raise OperationalException(
                        "No data available for the "
                        f"date: {backtest_index_date} "
                        "within the prepared backtest data."
                    )

        if self.pandas:
            data = convert_polars_to_pandas(data)

        return data

    def _load_data(self, storage_path):
        """
        Load OHLCV data from a CSV file into a Polars DataFrame.
        The CSV file should contain the following columns:

        Datetime, Open, High, Low, Close, Volume.

        The Datetime column should be in UTC timezone and in milliseconds.

        Args:
            storage_path (str): The path to the CSV file containing OHLCV data.

        Raises:
            OperationalException: If the CSV file does not contain all
                required OHLCV columns.

        Returns:
            None
        """
        df = pl.read_csv(storage_path)

        # Check if all column names are in the csv file
        if not all(column in df.columns for column in self._columns):
            # Identify missing columns
            missing_columns = [column for column in self._columns if
                               column not in df.columns]
            raise OperationalException(
                f"Csv file {storage_path} does not contain "
                f"all required ohlcv columns. "
                f"Missing columns: {missing_columns}"
            )

        self.data = pl.read_csv(
            storage_path,
            schema_overrides={"Datetime": pl.Datetime},
            low_memory=True
        ).with_columns(
            pl.col("Datetime").cast(
                pl.Datetime(time_unit="ms", time_zone="UTC")
            )
        )

        first_row = self.data.head(1)
        last_row = self.data.tail(1)
        self._start_date_data_source = first_row["Datetime"][0]
        self._end_date_data_source = last_row["Datetime"][0]

    def _precompute_sliding_windows(
        self,
        window_size: int,
        start_date: datetime,
        end_date: datetime
    ) -> None:
        """
        Precompute all sliding windows for fast retrieval in backtest mode.

        A sliding window is calculated as a subset of the data. It will
        take for each timestamp in the data a window of size `window_size`
        and stores it in a cache with the last timestamp of the window.

        So if the window size is 200, the first window will be
        the first 200 rows of the data, the second window will be
        the rows 1 to 200, the third window will be the rows
        2 to 201, and so on until the last window which will be
        the last 200 rows of the data.

        Args:
            window_size (int): The size of the sliding window to precompute.
            start_date (datetime, optional): The start date for the sliding
                windows.
            end_date (datetime, optional): The end date for the sliding
                windows.

        Returns:
            None
        """
        self.window_cache = {}
        timestamps = self.data["Datetime"].to_list()

        # Only select the entries after the start date
        timestamps = [
            ts for ts in timestamps
            if start_date <= ts <= end_date
        ]

        # Create sliding windows of size <window_size> for each timestamp
        # in the data with the given the time frame and window size
        for timestamp in timestamps:
            # Use timestamp as key
            self.window_cache[timestamp] = self.data.filter(
                (self.data["Datetime"] <= timestamp) &
                (self.data["Datetime"] >= timestamp - timedelta(
                    minutes=self.time_frame.amount_of_minutes * window_size
                ))
            )

    def copy(self, data_source: DataSource) -> "DataProvider":
        """
        Create a copy of the data provider with the given data source.

        Args:
            data_source (DataSource): The data source to copy.

        Returns:
            DataProvider: A new instance of the data provider with the
                specified data source.
        """

        storage_path = data_source.storage_path

        if storage_path is None:
            storage_path = self.storage_path

        return CSVOHLCVDataProvider(
            storage_path=storage_path,
            symbol=data_source.symbol,
            time_frame=data_source.time_frame,
            market=data_source.market,
            window_size=data_source.window_size,
            data_provider_identifier=self.data_provider_identifier,
            pandas=data_source.pandas
        )

    def get_number_of_data_points(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> int:

        """
        Returns the number of data points available between the given
        start and end dates.

        Args:
            start_date (datetime): The start date for checking missing data.
            end_date (datetime): The end date for checking missing data.

        Returns:
            int: The number of available data points between the given
                start and end dates.
        """
        available_dates = [
            date for date in self.data["Datetime"].to_list()
            if start_date <= date <= end_date
        ]
        return len(available_dates)

    def get_missing_data_dates(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[datetime]:
        """
        Returns a list of dates for which data is missing between the
        given start and end dates.

        Args:
            start_date (datetime): The start date for checking missing data.
            end_date (datetime): The end date for checking missing data.

        Returns:
            List[datetime]: A list of dates for which data is missing
                between the given start and end dates.
        """
        missing_dates = [
            date for date in self.missing_data_point_dates
            if start_date <= date <= end_date
        ]
        return missing_dates

    def get_data_source_file_path(self) -> Union[str, None]:
        """
        Get the file path of the data source if stored in local storage.

        Returns:
            Union[str, None]: The file path of the data source if stored
                locally, otherwise None.
        """
        return self.storage_path
