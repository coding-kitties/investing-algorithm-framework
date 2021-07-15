import logging
from typing import List, Dict

from investing_algorithm_framework.configuration import Config
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import TimeUnit
from investing_algorithm_framework.core.portfolio_managers import \
    AbstractPortfolioManager
from investing_algorithm_framework.core.workers import Scheduler
from investing_algorithm_framework.extensions import scheduler

logger = logging.getLogger(__name__)


class AlgorithmContext:
    """
    The AlgorithmContext defines the context of an algorithm.

    An algorithm consist out of an data provider and a set of
    strategies that belong to the data provider.
    """
    _config = None
    _workers = []
    _running_workers = []
    _order_executors = {}
    _portfolio_managers = {}
    _initializer = None
    _initialized = False

    # wrap Scheduler to allow for deferred calling
    @staticmethod
    def schedule(
        function=None,
        worker_id: str = None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10
    ):

        if function:
            return Scheduler(function, worker_id, time_unit, interval)
        else:
            def wrapper(f):
                return Scheduler(f, worker_id, time_unit, interval)
            return wrapper

    def initialize(self, config=None):

        if config is not None:
            assert isinstance(config, Config), (
                "Config is not an instance of config"
            )
            self._config = config
        else:
            self._config = Config()

    def start(self):

        # Initialize the algorithm context
        if not self._initialized:

            # Run the initializer
            if self._initializer is not None:
                self._initializer.initialize(self)

            # Initialize the portfolio managers
            for portfolio_manager_key in self._portfolio_managers:
                portfolio_manager = self._portfolio_managers[
                    portfolio_manager_key
                ]
                portfolio_manager.initialize()

        self._initialized = True

        # Start the workers
        self.start_workers()

    def stop(self):
        self.stop_all_workers()

    def start_workers(self):

        if not self.running:
            # Start functional workers
            for worker in self._workers:
                worker.add_to_scheduler(scheduler)
                self._running_workers.append(worker)

    def stop_all_workers(self):
        scheduler.remove_all_jobs()
        self._running_workers = []

    def add_worker(self, worker):
        """
        Function to ad an worker to list of workers of the
        algorithm context.
        """

        assert isinstance(worker, Scheduler), OperationalException(
            "Worker is not an instance of an Scheduler"
        )

        for installed_worker in self._workers:

            if installed_worker.worker_id == worker.worker_id:
                return

        self._workers.append(worker)

    @property
    def portfolio_managers(self) -> Dict:
        portfolio_managers = []

        for key in self._portfolio_managers:
            portfolio_managers.append(self._portfolio_managers[key])

        return self._portfolio_managers

    @property
    def running(self) -> bool:
        """
            An utility property to check if there are active workers for the
            algorithm.
        """

        return len(self._running_workers) != 0

    @property
    def workers(self) -> List:
        return self._workers

    @property
    def running_workers(self) -> List:
        return self._running_workers

    @property
    def config(self) -> Config:
        return self._config

    @property
    def order_executors(self) -> List:
        order_executors = []

        for order_executor in self.order_executors:
            order_executors.append(order_executor)

        return order_executors

    def add_initializer(self, initializer):
        from investing_algorithm_framework.core.context \
            import AlgorithmContextInitializer

        assert isinstance(initializer, AlgorithmContextInitializer), (
            'Initializer must be an instance of the '
            'AlgorithmContextInitializer class'
        )

        self._initializer = initializer

    def add_portfolio_manager(self, portfolio_manager):
        # Check if order executor is instance of AbstractPortfolioManager
        from investing_algorithm_framework.core.portfolio_managers \
            import AbstractPortfolioManager

        assert isinstance(portfolio_manager, AbstractPortfolioManager), (
            'portfolio manager must be an instance of the '
            'AbstractPortfolioManager class'
        )

        self._portfolio_managers[portfolio_manager.broker] = portfolio_manager

    def set_algorithm_context_initializer(
            self, algorithm_context_initializer
    ) -> None:

        # Check if initializer is an instance of AlgorithmContextInitializer
        from investing_algorithm_framework.core.context import \
            AlgorithmContextInitializer

        assert isinstance(
            algorithm_context_initializer, AlgorithmContextInitializer
        ), (
            'Initializer must be an instance of AlgorithmContextInitializer'
        )
        self._initializer = algorithm_context_initializer

    def get_free_portfolio_size(self, broker):

        if broker not in self.portfolio_managers:
            raise OperationalException(
                "There is no portfolio manager linked to the given broker"
            )

        portfolio_manager = self.portfolio_managers[broker]
        return portfolio_manager.get_free_portfolio_size(self)

    def get_portfolio_manager(
            self, broker_id: str, throw_exception: bool = False
    ) -> AbstractPortfolioManager:
        matching_portfolio_manager = self.portfolio_managers[broker_id]

        if matching_portfolio_manager is None and throw_exception:
            raise OperationalException(
                "No corresponding portfolio manager found for broker"
            )

        return matching_portfolio_manager
