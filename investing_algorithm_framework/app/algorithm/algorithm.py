import inspect
import logging
from typing import List

from investing_algorithm_framework.app.app_hook import AppHook
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.domain import OperationalException, \
    DataSource

logger = logging.getLogger("investing_algorithm_framework")


class Algorithm:
    """
    Class to represent an algorithm. An algorithm is a collection of
    strategies that are executed in a specific order.

    Attributes:
        algorithm_id: The unique identifier of the algorithm. This id
            should be a string and also will be used for all the
            registered strategies within the algorithm.
        _description: The description of the algorithm. It should be a string.
        _strategies: A list of strategies that are part of the algorithm.
        _tasks: A list of tasks that are part of the algorithm.
        _data_sources: A list of data sources that are part of the algorithm.
        _on_strategy_run_hooks: A list of hooks that will be called when a
    """
    def __init__(
        self,
        algorithm_id: str = None,
        description: str = None,
        strategy=None,
        strategies=None,
        tasks: List = None,
        data_sources: List[DataSource] = None,
        on_strategy_run_hooks=None,
        metadata=None
    ):
        self.algorithm_id = algorithm_id
        self._context = {}
        self._description = None

        if description is not None:
            self._description = description

        self._strategies = []
        self._tasks = []
        self._data_sources = []
        self._on_strategy_run_hooks = []
        self.metadata = metadata

        if data_sources is not None:
            self._data_sources = data_sources

        if strategies is not None:
            self.strategies = strategies

        if tasks is not None:
            self.tasks = tasks

        if strategy is not None:
            self.add_strategy(strategy, throw_exception=True)

        if on_strategy_run_hooks is not None:
            for hook in on_strategy_run_hooks:
                self.add_on_strategy_run_hook(hook)

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

    @property
    def on_strategy_run_hooks(self):
        return self._on_strategy_run_hooks

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

        strategy_ids = []

        for s in self._strategies:
            strategy_ids.append(s.strategy_id)

        # Check for duplicate strategy IDs
        if strategy.strategy_id in strategy_ids:
            raise OperationalException(
                "Can't add strategy, there already exists a strategy "
                "with the same id in the algorithm"
            )

        strategy.algorithm_id = self.algorithm_id
        self._strategies.append(strategy)

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        self._tasks.append(task)

    def add_on_strategy_run_hook(self, app_hook):
        """
        Function to add a hook that will be called when a strategy is run.

        Args:
            app_hook: The hook function to be added.
        """
        # Check if the app_hook inherits from AppHook
        if inspect.isclass(app_hook) and not issubclass(app_hook, AppHook):
            raise OperationalException(
                "App hook should be an instance of AppHook"
            )

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_strategy_run_hooks.append(app_hook)
