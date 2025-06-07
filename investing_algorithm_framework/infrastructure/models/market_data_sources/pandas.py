from datetime import datetime, timedelta, timezone

from dateutil import parser
from pandas import DataFrame
import polars as pl

from investing_algorithm_framework.domain import OHLCVMarketDataSource, \
    BacktestMarketDataSource, OperationalException, TimeFrame, sync_timezones


class PandasOHLCVBacktestMarketDataSource(
    OHLCVMarketDataSource, BacktestMarketDataSource
):
    """
    PandasOHLCVBacktestMarketDataSource implementation
    of a OHLCVMarketDataSource. This implementation uses a pandas
    dataframe to provide data to the strategy.
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
        dataframe=None,
        window_size=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            time_frame=time_frame,
            window_size=window_size,
        )
        self.dataframe = dataframe
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.backtest_end_index = self.window_size
        self.backtest_start_index = 0
        self.window_cache = {}

    def prepare_data(
        self,
        config,
        backtest_start_date,
        backtest_end_date,
    ):
        """
        Prepare data implementation of ccxt based ohlcv backtest market
        data source

        This implementation will check if the data source already exists before
        pulling all the data. This optimization will prevent downloading
        of unnecessary resources.

        When downloading the data it will use the ccxt library.

        Args:
            config (dict): the configuration of the data source
            backtest_start_date (datetime): the start date of the backtest
            backtest_end_date (datetime): the end date of the backtest
            time_frame (string): the time frame of the data
            window_size (int): the total amount of candle sticks that need to
            be returned

        Returns:
            None
        """

        if config is None:
            config = self.config

        # Calculating the backtest data start date
        backtest_data_start_date = \
            backtest_start_date - timedelta(
                minutes=(
                        (self.window_size + 1) *
                        TimeFrame.from_value(self.time_frame).amount_of_minutes
                )
            )

        self.backtest_data_start_date = backtest_data_start_date \
            .replace(microsecond=0)
        self.backtest_data_end_date = backtest_end_date.replace(microsecond=0)

        if not isinstance(self.dataframe, DataFrame):
            raise OperationalException(
                "Provided dataframe is not a pandas dataframe"
            )

        if not set(self.column_names).issubset(self.dataframe.columns):
            raise OperationalException(
                "Provided dataframe does not have all required columns. "
                "Your pandas dataframe should have the following columns: "
                "Datetime, Open, High, Low, Close, Volume"
            )

        # Get first and last row and check if backtest start and end dates
        # are within the dataframe
        first_row = self.dataframe.head(1)
        last_row = self.dataframe.tail(1)

        if backtest_end_date > last_row["Datetime"].iloc[0]:
            raise OperationalException(
                f"Backtest end date {backtest_end_date} is "
                f"after the end date of the data source "
                f"{last_row['Datetime'].iloc[0]}"
            )

        if backtest_data_start_date < first_row["Datetime"].iloc[0]:
            raise OperationalException(
                f"Backtest start date {backtest_data_start_date} is "
                f"before the start date of the data source "
                f"{first_row['Datetime'][0]}"
            )

        self._precompute_sliding_windows()  # Precompute sliding windows!

    def _precompute_sliding_windows(self):
        """
        Precompute all sliding windows for fast retrieval.

        A sliding window is calculated as a subset of the data. It will
        take for each timestamp in the data a window of size `window_size`
        and stores it in a cache with the last timestamp of the window.
        """
        self.window_cache = {}
        timestamps = self.dataframe["Datetime"].to_list()

        for i in range(len(timestamps) - self.window_size + 1):
            # Use last timestamp as key
            end_time = timestamps[i + self.window_size - 1]

            # Convert end_time datetime object to UTC
            if isinstance(end_time, str):
                end_time = parser.parse(end_time)
            elif isinstance(end_time, datetime):
                end_time = end_time

            self.window_cache[end_time] = \
                self.dataframe.iloc[i:i + self.window_size]

    def get_data(
        self,
        date,
        config=None,
    ):
        """
        Get data implementation of ccxt based ohlcv backtest market data
        source. This implementation will use polars to load and filter the
        data.
        """

        data = self.window_cache.get(date)

        if data is not None:
            data = pl.from_pandas(data)
            return data

        # Find closest previous timestamp
        sorted_timestamps = sorted(self.window_cache.keys())

        closest_date = None
        for ts in reversed(sorted_timestamps):
            date = sync_timezones(ts, date)

            if ts <= date:
                closest_date = ts
                break

        data = self.window_cache.get(closest_date) if closest_date else None

        if data is not None:
            data = pl.from_pandas(data)

        return data

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # Ignore this method for now
        pass

    def empty(self):
        return False


class PandasOHLCVMarketDataSource(OHLCVMarketDataSource):
    """
    PandasOHLCVMarketDataSource implementation of a OHLCVMarketDataSource
    using a pandas dataframe to provide data to the strategy.

    """

    """
        PandasOHLCVBacktestMarketDataSource implementation
        of a OHLCVMarketDataSource. This implementation uses a pandas
        dataframe to provide data to the strategy.
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
            dataframe=None,
            window_size=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            time_frame=time_frame,
            window_size=window_size,
        )
        self.dataframe = dataframe
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.backtest_end_index = self.window_size
        self.backtest_start_index = 0

    def get_data(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        config=None,
    ):
        """
        Implementation of get_data for CCXTOHLCVMarketDataSource.
        This implementation uses the CCXTMarketService to get the OHLCV data.

        Args:
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

        # Calculate the start and end dates
        if start_date is None or end_date is None:

            if start_date is None:

                if end_date is None:
                    end_date = datetime.now(tz=timezone.utc)

                if self.window_size is None:
                    raise OperationalException(
                        "Window_size should be defined before the " +
                        "get_data method can be called. Make sure to set " +
                        "the window_size attribute on your " +
                        "CCXTOHLCVMarketDataSource or provide a start_date " +
                        "and end_date to the get_data method."
                    )

                start_date = self.create_start_date(
                    end_date=end_date,
                    time_frame=self.time_frame,
                    window_size=self.window_size
                )
            else:
                end_date = self.create_end_date(
                    start_date=start_date,
                    time_frame=self.time_frame,
                    window_size=self.window_size
                )
        # Return the dataframe sliced by the start and end date
        start_date = sync_timezones(
            self.dataframe["Datetime"].dt.tz, start_date
        )
        end_date = sync_timezones(
            self.dataframe["Datetime"].dt.tz, end_date
        )
        data = self.dataframe[
            (self.dataframe["Datetime"] >= start_date) &
            (self.dataframe["Datetime"] <= end_date)
        ]

        if data is not None:
            data = pl.from_pandas(data)

        return data

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        return PandasOHLCVBacktestMarketDataSource(
            identifier=self.identifier,
            market=self.market,
            symbol=self.symbol,
            time_frame=self.time_frame,
            dataframe=self.dataframe,
            window_size=self.window_size
        )

    def empty(self):
        return False
