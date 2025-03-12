from pandas import DataFrame

from investing_algorithm_framework.domain import OHLCVMarketDataSource, \
    BacktestMarketDataSource, OperationalException


class PandasOHLCVBacktestMarketDataSource(
    OHLCVMarketDataSource, BacktestMarketDataSource
):

    def __init__(
        self,
        identifier,
        market,
        symbol,
        dataframe,
        backtest_data_start_date=None,
        backtest_data_index_date=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            backtest_data_start_date=backtest_data_start_date,
            backtest_data_index_date=backtest_data_index_date
        )
        self.dataframe = dataframe
        self._validate_dataframe_with_ohlcv_structure()

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass

    def prepare_data(self, config, backtest_start_date, backtest_end_date,
                     **kwargs):
        """
        Implementation of get_data for PandasOHLCVBacktestMarketDataSource.
        This implementation uses the dataframe provided in the constructor.
        """

    def empty(self):
        pass

    def get_data(self, config, date):
        pass

    def _validate_dataframe_with_ohlcv_structure(self):
        """
        Function to check if the provided pandas dataframe is not null or
        empty. It also checks if all required columns are present in the
        dataframe.
        """
        if not isinstance(self.dataframe, DataFrame):
            raise OperationalException(
                "Provided dataframe is not a pandas dataframe"
            )

        if not self.dataframe.columns == \
                ["Datetime", "Open", "High", "Low", "Close", "Volume"]:
            raise OperationalException(
                "Provided dataframe does not have all required columns. "
                "Your pandas dataframe should have the following columns: "
                "Datetime, Open, High, Low, Close, Volume"
            )


class PandasOHLCVMarketDataSource(OHLCVMarketDataSource):
    """
    PandasOHLCVMarketDataSource implementation of a OHLCVMarketDataSource
    using a pandas dataframe to provide data to the strategy.

    """

    def __init__(
        self,
        dataframe,
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
            window_size=window_size
        )
        self.dataframe = dataframe
        self._validate_dataframe_with_ohlcv_structure()

    def get_data(self, config, date):
        """
        Implementation of get_data for PandasOHLCVMarketDataSource.
        This implementation uses the dataframe provided in the constructor.

        In the kwargs, the start_date should be set as a datetime object.

        Params (kwargs):
            window_size (optional): the size of the batch of OHLCV items that
            need to be returned.
            start_date (optional): datetime object defining the start date
            of the set of OHLCV items that need to be returned.
            end_date (optional): datetime object defining the end date
            of the set of OHLCV items that need to be returned.

        returns:
            Polars Dataframe: a polars.DataFrame with the OHLCV data
        """
        end_date = self.create_end_date(
            date, self.time_frame, self.window_size
        )

        # Slice the pandas dataframe object
        return self.dataframe["Datetime" >= date & "Datetime" <= end_date]

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        # return CCXTOHLCVBacktestMarketDataSource(
        #     identifier=self.identifier,
        #     market=self.market,
        #     symbol=self.symbol,
        #     time_frame=self.time_frame,
        #     window_size=self.window_size
        # )
        return None

    def _validate_dataframe_with_ohlcv_structure(self):
        """
        Function to check if the provided pandas dataframe is not null or
        empty. It also checks if all required columns are present in the
        dataframe.
        """
        if not isinstance(self.dataframe, DataFrame):
            raise OperationalException(
                "Provided dataframe is not a pandas dataframe"
            )

        if not self.dataframe.columns == \
                ["Datetime", "Open", "High", "Low", "Close", "Volume"]:
            raise OperationalException(
                "Provided dataframe does not have all required columns. "
                "Your pandas dataframe should have the following columns: "
                "Datetime, Open, High, Low, Close, Volume"
            )
