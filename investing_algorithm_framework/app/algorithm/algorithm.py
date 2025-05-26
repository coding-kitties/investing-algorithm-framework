import logging
import re
from typing import List
import inspect

from investing_algorithm_framework.domain import OperationalException, \
    random_string, MarketDataSource
from .strategy import TradingStrategy

logger = logging.getLogger("investing_algorithm_framework")


class Algorithm:
    """
    Class to represent an algorithm. An algorithm is a collection of
    strategies that are executed in a specific order.

    Args:
        name (str): (Optional) The name of the algorithm
        description (str): The description of the algorithm
        context (dict): The context of the algorithm, for backtest
          references
    """
    def __init__(
        self,
        name: str = None,
        description: str = None,
        strategy = None,
        strategies = None,
        tasks: List = None,
        data_sources: List[MarketDataSource] = None,
    ):
        self._name = name
        self._context = {}

        if name is None:
            self._name = f"algorithm_{random_string(10)}"

        self._description = None

        if description is not None:
            self._description = description

        self._strategies = []
        self._tasks = []
        self._data_sources = []

        if data_sources is not None:
            self._data_sources = data_sources

        if strategies is not None:
            self.strategies = strategies

        if tasks is not None:
            self.tasks = tasks

        if strategy is not None:
            self.add_strategy(strategy, throw_exception=True)

    @staticmethod
    def _validate_name(name):
        """
        Function to validate the name of the algorithm. This function
        will check if the name of the algorithm is a string and raise
        an exception if it is not.

        Name can only contain letters, numbers

        Parameters:
            name: The name of the algorithm

        Returns:
            None
        """
        if not isinstance(name, str):
            raise OperationalException(
                "The name of the algorithm must be a string"
            )

        pattern = re.compile(r"^[a-zA-Z0-9]*$")

        if not pattern.match(name):
            raise OperationalException(
                "The name of the algorithm can only contain" +
                " letters and numbers"
            )

        illegal_chars = r"[\/:*?\"<>|]"

        if re.search(illegal_chars, name):
            raise OperationalException(
                f"Illegal characters detected in algorithm: {name}. "
                f"Illegal characters: / \\ : * ? \" < > |"
            )

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        Algorithm._validate_name(name)
        self._name = name

    @property
    def data_sources(self):
        return self._data_sources

    @data_sources.setter
    def data_sources(self, data_sources):
        self._data_sources = data_sources

    @property
    def description(self):
        """
        Function to get the description of the algorithm
        """
        return self._description

    @property
    def strategies(self):
        return self._strategies

    @strategies.setter
    def strategies(self, strategies):

        for strategy in strategies:
            self.add_strategy(strategy)

    @property
    def tasks(self):
        return self._tasks

    @tasks.setter
    def tasks(self, tasks):

        for task in tasks:
            self.add_task(task)

    def get_strategy(self, strategy_id):
        for strategy in self._strategies:
            if strategy.worker_id == strategy_id:
                return strategy

        return None

    def get_strategies(self):

        if self._strategies is None:
            raise OperationalException(
                "No strategies have been added to the algorithm"
            )
        return self._strategies

    def add_strategy(self, strategy, throw_exception=True) -> None:
        """
        Function to add a strategy to the algorithm. The strategy should be an
        instance of TradingStrategy or a subclass based on the TradingStrategy
        class.

        Args:
            strategy: Instance of TradingStrategy
            throw_exception: Flag to allow for throwing an exception when
                the provided strategy is not inline with what the application
                expects.

        Returns:
            None
        """

        if inspect.isclass(strategy):

            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            strategy = strategy()

        if not isinstance(strategy, TradingStrategy):

            if throw_exception:
                raise OperationalException(
                    "Strategy should be an instance of TradingStrategy"
                )
            else:
                return

        has_duplicates = False

        for i in range(len(self._strategies)):
            for j in range(i + 1, len(self._strategies)):
                if self._strategies[i].worker_id == strategy.worker_id:
                    has_duplicates = True
                    break

        if has_duplicates:
            raise OperationalException(
                "Can't add strategy, there already exists a strategy "
                "with the same id in the algorithm"
            )

        if strategy.market_data_sources is not None:
            self.add_data_sources(strategy.market_data_sources)

        self._strategies.append(strategy)

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        self._tasks.append(task)

    def add_data_source(self, data_source) -> None:
        """
        Function to add a data source to the app. The data source should
        be an instance of DataSource.

        Args:
            data_source: Instance of DataSource

        Returns:
            None
        """
        if inspect.isclass(data_source):
            if not issubclass(data_source, MarketDataSource):
                raise OperationalException(
                    "Data source should be an instance of MarketDataSource"
                )

            data_source = data_source()

        self.data_sources.append(data_source)

    def add_data_sources(self, data_sources) -> None:
        """
        Function to add a list of data sources to the app. The data sources
        should be instances of DataSource.

        Args:
            data_sources: List of DataSource

        Returns:
            None
        """
        for data_source in data_sources:
            self.add_data_source(data_source)