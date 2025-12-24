import inspect
import logging
import re
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
        _name: The name of the algorithm. It should be a string and
            can only contain letters and numbers.
        _description: The description of the algorithm. It should be a string.
        _strategies: A list of strategies that are part of the algorithm.
        _tasks: A list of tasks that are part of the algorithm.
        _data_sources: A list of data sources that are part of the algorithm.
        _on_strategy_run_hooks: A list of hooks that will be called when a
    """
    def __init__(
        self,
        id: str = None,
        name: str = None,
        description: str = None,
        strategy=None,
        strategies=None,
        tasks: List = None,
        data_sources: List[DataSource] = None,
        on_strategy_run_hooks=None,
        metadata=None
    ):
        self.id = id
        self._name = name
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
