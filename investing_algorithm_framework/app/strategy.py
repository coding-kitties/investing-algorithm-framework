from investing_algorithm_framework.domain import OperationalException
from investing_algorithm_framework.domain import \
    TimeUnit, StrategyProfile, Trade
from .algorithm import Algorithm
import pandas as pd


class TradingStrategy:
    time_unit: str = None
    interval: int = None
    worker_id: str = None
    strategy_id: str = None
    decorated = None
    market_data_sources = None
    traces = None

    def __init__(
        self,
        strategy_id=None,
        time_unit=None,
        interval=None,
        market_data_sources=None,
        worker_id=None,
        decorated=None
    ):

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if interval is not None:
            self.interval = interval

        if time_unit is not None:
            self.time_unit = TimeUnit.from_value(time_unit)

        if market_data_sources is not None:
            self.market_data_sources = market_data_sources

        if decorated is not None:
            self.decorated = decorated

        if worker_id is not None:
            self.worker_id = worker_id
        elif self.decorated:
            self.worker_id = decorated.__name__
        else:
            self.worker_id = self.__class__.__name__

        if strategy_id is not None:
            self.strategy_id = strategy_id
        else:
            self.strategy_id = self.worker_id

        # Check if time_unit is None
        if self.time_unit is None:
            raise OperationalException(
                f"Time unit not set for strategy instance {self.strategy_id}"
            )

        # Check if interval is None
        if self.interval is None:
            raise OperationalException(
                f"Interval not set for strategy instance {self.strategy_id}"
            )

        # context initialization
        self._context = None

    def run_strategy(self, algorithm, market_data):
        # Check pending orders before running the strategy
        algorithm.check_pending_orders()

        # Run user defined strategy
        self.apply_strategy(algorithm=algorithm, market_data=market_data)

    def apply_strategy(self, algorithm, market_data):
        if self.decorated:
            self.decorated(algorithm=algorithm, market_data=market_data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")

    @property
    def strategy_profile(self):
        return StrategyProfile(
            strategy_id=self.worker_id,
            interval=self.interval,
            time_unit=self.time_unit,
            market_data_sources=self.market_data_sources
        )

    def on_trade_closed(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_created(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_opened(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_stop_loss_triggered(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_triggered(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_triggered(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_stop_loss_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_updated(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_updated(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_stop_loss_created(self, algorithm: Algorithm, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_created(
        self, algorithm: Algorithm, trade: Trade
    ):
        pass

    def on_trade_take_profit_created(self, algorithm: Algorithm, trade: Trade):
        pass

    @property
    def strategy_identifier(self):

        if self.strategy_id is not None:
            return self.strategy_id

        return self.worker_id

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, context):
        self._context = context

    def add_trace(
        self,
        symbol: str,
        data,
        drop_duplicates=True
    ) -> None:
        """
        Add data to the straces object for a given symbol

        Args:
            symbol (str): The symbol
            data (pd.DataFrame): The data to add to the tracing
            drop_duplicates (bool): Drop duplicates

        Returns:
            None
        """

        # Check if data is a DataFrame
        if not isinstance(data, pd.DataFrame):
            raise ValueError(
                "Currently only pandas DataFrames are "
                "supported as tracing data objects."
            )

        data: pd.DataFrame = data

        # Check if index is a datetime object
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Dataframe Index must be a datetime object.")

        if self.traces is None:
            self.traces = {}

        # Check if the key is already in the context dictionary
        if symbol in self.traces:
            # If the key is already in the context dictionary,
            # append the new data to the existing data
            combined = pd.concat([self.traces[symbol], data])
        else:
            # If the key is not in the context dictionary,
            # add the new data to the context dictionary
            combined = data

        if drop_duplicates:
            # Drop duplicates and sort the data by the index
            combined = combined[~combined.index.duplicated(keep='first')]

        # Set the datetime column as the index
        combined.set_index(pd.DatetimeIndex(combined.index), inplace=True)
        self.traces[symbol] = combined

    def get_traces(self) -> dict:
        """
        Get the traces object

        Returns:
            dict: The traces object
        """
        return self.traces
