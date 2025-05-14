import polars
from datetime import datetime
from investing_algorithm_framework.domain import DataProvider, \
    TradingDataType, OperationalException


class CSVOHLCVDataProvider(DataProvider):
    """
    Implementation of Data Provider for OHLCV data.
    """
    def __init__(
        self,
        file_path: str,
        symbol: str,
        time_frame: str,
        market: str = None,
        priority: int = 0,
        window_size=None,
        storage_path=None,
    ):
        """
        Initialize the CSV Data Provider.

        Args:
            file_path (str): Path to the CSV file.
        """

        super().__init__(
            data_type=TradingDataType.OHLCV.value,
            symbol=symbol,
            market=market,
            markets=[],
            priority=priority,
            time_frame=time_frame,
            window_size=window_size,
            storage_path=storage_path,
        )
        self.file_path = file_path
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.data = None

    def has_data(
        self,
        data_type: str = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        window_size=None
    ) -> bool:

        if symbol == self.symbol and market == self.market and \
                data_type == self.data_type and time_frame == self.time_frame:
            return True

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
        pandas=False
    ):

        if self.data is None:
            self._load_data(self.file_path)

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

        return self.data

    def pre_pare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        window_size=None
    ) -> None:

        if symbol is not None:
            return

        if self.data is None:
            self._load_data(self.file_path)

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

        if self.data is None:
            self._load_data(self.file_path)

        if backtest_start_date is None and backtest_end_date is None:
            return self.data

        if backtest_start_date is not None and backtest_end_date is not None:

            if backtest_end_date < backtest_start_date:
                raise OperationalException(
                    f"Backtest end date {backtest_end_date} is before the "
                    f"start date {backtest_start_date}"
                )

            if backtest_start_date > self._end_date_data_source:
                return polars.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] >= backtest_start_date)
                & (df['Datetime'] <= backtest_end_date)
            )
            return df

        if backtest_start_date is not None:

            if backtest_start_date < self._start_date_data_source:
                return polars.DataFrame()

            if backtest_start_date > self._end_date_data_source:
                return polars.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] >= backtest_start_date)
            )
            df = df.head(self.window_size)
            return df

        if backtest_end_date is not None:

            if backtest_end_date < self._start_date_data_source:
                return polars.DataFrame()

            if backtest_end_date > self._end_date_data_source:
                return polars.DataFrame()

            df = self.data
            df = df.filter(
                (df['Datetime'] <= backtest_end_date)
            )
            df = df.tail(self.window_size)
            return df

        return self.data

    def _load_data(self, storage_path):
        self._columns = [
            "Datetime", "Open", "High", "Low", "Close", "Volume"
        ]

        df = polars.read_csv(storage_path)

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

        self.data = polars.read_csv(
            storage_path,
            schema_overrides={"Datetime": polars.Datetime},
            low_memory=True
        ).with_columns(
            polars.col("Datetime").cast(
                polars.Datetime(time_unit="ms", time_zone="UTC")
            )
        )

        first_row = self.data.head(1)
        last_row = self.data.tail(1)
        self._start_date_data_source = first_row["Datetime"][0]
        self._end_date_data_source = last_row["Datetime"][0]
