import inspect
import logging
from typing import Dict
import re

from investing_algorithm_framework.domain import MarketService, TimeUnit, \
    OperationalException, random_string
from investing_algorithm_framework.services import MarketCredentialService, \
    MarketDataSourceService, PortfolioService, PositionService, TradeService, \
    OrderService, ConfigurationService, StrategyOrchestratorService, \
    PortfolioConfigurationService
from .task import Task

logger = logging.getLogger("investing_algorithm_framework")


class Algorithm:
    """
    Class to represent an algorithm. An algorithm is a collection of
    strategies that are executed in a specific order. The algorithm
    class is responsible for managing the strategies and executing
    them in the correct order.

    Args:
        name (str): (Optional) The name of the algorithm
        description (str): The description of the algorithm
        context (dict): The context of the algorithm, for backtest
          references
        strategy: A single strategy to add to the algorithm
        data_sources: The list of data sources to add to the algorithm
    """
    def __init__(
        self,
        name: str = None,
        description: str = None,
        context: Dict = None,
        strategy=None,
        data_sources=None
    ):
        self._name = name
        self._context = {}

        if name is None:
            self._name = f"algorithm_{random_string(10)}"

        self._description = None

        if description is not None:
            self._description = description

        if context is not None:
            self.add_context(context)

        self._strategies = []
        self._tasks = []
        self.portfolio_service: PortfolioService
        self.position_service: PositionService
        self.order_service: OrderService
        self.market_service: MarketService
        self.configuration_service: ConfigurationService
        self.portfolio_configuration_service: PortfolioConfigurationService
        self.strategy_orchestrator_service: StrategyOrchestratorService = None
        self._data_sources = {}
        self._strategies = []
        self._market_credential_service: MarketCredentialService
        self._market_data_source_service: MarketDataSourceService
        self.trade_service: TradeService

        if strategy is not None:
            self.add_strategy(strategy)

        if data_sources is not None:
            self.add_data_sources(data_sources)

    def _validate_name(self, name):
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

    def initialize_services(
        self,
        context,
        configuration_service,
        portfolio_configuration_service,
        portfolio_service,
        position_service,
        order_service,
        market_service,
        strategy_orchestrator_service,
        market_credential_service,
        market_data_source_service,
        trade_service
    ):
        self.context = context
        self.portfolio_service: PortfolioService = portfolio_service
        self.position_service: PositionService = position_service
        self.order_service: OrderService = order_service
        self.market_service: MarketService = market_service
        self.configuration_service: ConfigurationService \
            = configuration_service
        self.portfolio_configuration_service: PortfolioConfigurationService \
            = portfolio_configuration_service
        self.strategy_orchestrator_service: StrategyOrchestratorService \
            = strategy_orchestrator_service
        self._data_sources = {}
        self._market_credential_service: MarketCredentialService \
            = market_credential_service
        self._market_data_source_service: MarketDataSourceService \
            = market_data_source_service
        self.trade_service: TradeService = trade_service

        # Add all registered strategies to the orchestrator
        self.strategy_orchestrator_service.add_strategies(
            self._strategies
        )

    def start(self, number_of_iterations: int = None):
        """
        Function to start the algorithm.
        This function will start the algorithm by scheduling all
        jobs in the strategy orchestrator service. The jobs are not
        run immediately, but are scheduled to run in the future by the
        app.

        Args:
            number_of_iterations (int): (Optional) The number of
              iterations to run the algorithm

        Returns:
            None
        """
        self.strategy_orchestrator_service.start(
            context=self.context,
            number_of_iterations=number_of_iterations
        )

    def stop(self) -> None:
        """
        Function to stop the algorithm. This function will stop the
        algorithm by stopping all jobs in the strategy orchestrator
        service.

        Returns:
            None
        """

        if self.strategy_orchestrator_service is not None:
            self.strategy_orchestrator_service.stop()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._validate_name(name)
        self._name = name

    @property
    def data_sources(self):
        return self._data_sources

    @property
    def config(self):
        """
        Function to get a config instance. This allows users when
        having access to the algorithm instance also to read the
        configs of the app.
        """
        return self.configuration_service.get_config()

    def get_config(self):
        """
        Function to get a config instance. This allows users when
        having access to the algorithm instance also to read the
        configs of the app.
        """
        return self.configuration_service.get_config()

    @property
    def description(self):
        """
        Function to get the description of the algorithm
        """
        return self._description

    @property
    def running(self) -> bool:
        """
        Returns True if the algorithm is running, False otherwise.

        The algorithm is considered to be running if has strategies
        scheduled to run in the strategy orchestrator service.
        """
        return self.strategy_orchestrator_service.running

    def run_jobs(self, context):
        """
        Function run all pending jobs in the strategy orchestrator
        """
        self.strategy_orchestrator_service.run_pending_jobs()

    def reset(self):
        self._workers = []
        self._running_workers = []

    def add_strategies(self, strategies):
        """
        Function to add multiple strategies to the algorithm.
        This function will check if there are any duplicate strategies
        with the same name and raise an exception if there are.
        """
        has_duplicates = False

        for strategy in strategies:
            from .strategy import TradingStrategy
            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            if inspect.isclass(strategy):
                strategy = strategy()

            assert isinstance(strategy, TradingStrategy), \
                OperationalException(
                    "Strategy object is not an instance of a TradingStrategy"
                )

        # Check if there are any duplicate strategies
        for i in range(len(strategies)):
            for j in range(i + 1, len(strategies)):
                if strategies[i].worker_id == strategies[j].worker_id:
                    has_duplicates = True
                    break

        if has_duplicates:
            raise OperationalException(
                "There are duplicate strategies with the same name"
            )

        self._strategies = strategies

    def add_strategy(self, strategy):
        """
        Function to add multiple strategies to the algorithm.
        This function will check if there are any duplicate strategies
        with the same name and raise an exception if there are.
        """
        has_duplicates = False
        from .strategy import TradingStrategy

        if inspect.isclass(strategy):

            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            strategy = strategy()

        assert isinstance(strategy, TradingStrategy), \
            OperationalException(
                "Strategy object is not an instance of a TradingStrategy"
            )

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

    @property
    def strategies(self):
        return self._strategies

    def get_strategy(self, strategy_id):
        for strategy in self.strategy_orchestrator_service.get_strategies():
            if strategy.worker_id == strategy_id:
                return strategy

        return None

    def add_tasks(self, tasks):
        self.strategy_orchestrator_service.add_tasks(tasks)

    def strategy(
        self,
        function=None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10,
        market_data_sources=None,
    ):
        from .strategy import TradingStrategy

        if function:
            strategy_object = TradingStrategy(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
                market_data_sources=market_data_sources
            )
            self.add_strategy(strategy_object)
        else:

            def wrapper(f):
                self.add_strategy(
                    TradingStrategy(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval,
                        market_data_sources=market_data_sources,
                        worker_id=f.__name__
                    )
                )
                return f

            return wrapper

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        assert isinstance(task, Task), \
            OperationalException(
                "Task object is not an instance of a Task"
            )

        self._tasks.append(task)

    def add_data_sources(self, data_sources):
        self._data_sources = data_sources

    @property
    def tasks(self):
        return self._tasks

    def get_trade_service(self):
        return self.trade_service

    def get_market_data_source_service(self):
        return self._market_data_source_service
