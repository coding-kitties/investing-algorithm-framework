import logging
from datetime import datetime, timezone

import schedule

from investing_algorithm_framework.domain import StoppableThread, TimeUnit, \
    OperationalException
from investing_algorithm_framework.services.market_data_source_service \
    import MarketDataSourceService

logger = logging.getLogger("investing_algorithm_framework")


class StrategyOrchestratorService:
    """
    Service that orchestrates the execution of strategies and tasks

    Attributes:
    - history: dict
        A dictionary that keeps track of the last time a strategy or task was
        run
    - _strategies: list
        A list of strategies
    - _tasks: list
        A list of tasks
    - threads: list
        A list of threads that are currently running
    - iterations: int
        The number of iterations that have been run
    - max_iterations: int
        The maximum number of iterations that can be run
    - market_data_source_service: MarketDataSourceService
        The service that provides market data
    """

    def __init__(
        self,
        market_data_source_service: MarketDataSourceService,
        configuration_service,
    ):
        self._app_hooks = []
        self.history = {}
        self._strategies = []
        self._tasks = []
        self.threads = []
        self.iterations = 0
        self.max_iterations = -1
        self.clear()
        self.market_data_source_service: MarketDataSourceService \
            = market_data_source_service
        self.configuration_service = configuration_service

    def initialize(self, algorithm) -> None:
        """
        Initialize the strategy orchestrator service with an algorithm.
        With the provided algorithm, the service will set the
        strategies, tasks, and on_strategy_run_hooks.

        Args:
            algorithm (Algorithm): The algorithm to initialize the service with

        Returns:
            None
        """
        self._app_hooks = algorithm.on_strategy_run_hooks or []
        self._add_strategies(algorithm.strategies)
        self._add_tasks(algorithm.tasks)

    def cleanup_threads(self):

        for stoppable in self.threads:
            if not stoppable.is_alive():
                # get results from thread
                stoppable.done = True
        self.threads = [t for t in self.threads if not t.done]

    def run_strategy(self, strategy, context, sync=False):
        self.cleanup_threads()
        matching_thread = next(
            (t for t in self.threads if t.name == strategy.worker_id),
            None
        )

        # Don't run a strategy that is already running
        if matching_thread:
            return

        market_data = \
            self.market_data_source_service.get_data_for_strategy(strategy)

        logger.info(f"Running strategy {strategy.worker_id}")

        # Run the app hooks
        for app_hook in self._app_hooks:
            app_hook.on_run(context=context)

        if sync:
            strategy.run_strategy(
                market_data=market_data,
                context=context,
            )
        else:
            self.iterations += 1
            thread = StoppableThread(
                target=strategy.run_strategy,
                kwargs={
                    "market_data": market_data,
                    "context": context,
                }
            )
            thread.name = strategy.worker_id
            thread.start()
            self.threads.append(thread)

        self.history[strategy.worker_id] = \
            {"last_run": datetime.now(tz=timezone.utc)}

    def run_backtest_strategy(self, strategy, context, config):
        data = self.market_data_source_service.get_data_for_strategy(strategy)
        strategy.run_strategy(
            market_data=data,
            context=context,
        )

    def run_task(self, task, context, sync=False):
        self.cleanup_threads()

        matching_thread = next(
            (t for t in self.threads if t.name == task.worker_id),
            None
        )

        # Don't run a strategy that is already running
        if matching_thread:
            return

        logger.info(f"Running task {task.worker_id}")

        if sync:
            task.run(context=context)
        else:
            self.iterations += 1
            thread = StoppableThread(
                target=task.run,
                kwargs={"context": context}
            )
            thread.name = task.worker_id
            thread.start()
            self.threads.append(thread)

        self.history[task.worker_id] = \
            {"last_run": datetime.now(tz=timezone.utc)}

    def start(self, context, number_of_iterations=None) -> None:
        """
        Function to start and schedule the strategies and tasks. This
        function will not start the strategies, but will calculate the
        schedule and queue the jobs.

        Args:
            context (Context): The application context
            number_of_iterations (int): The number of iterations that the
                strategies and tasks will run. If None, the
                strategies and tasks

        Returns:
            None
        """
        self.max_iterations = number_of_iterations

        for strategy in self.strategies:
            if TimeUnit.SECOND.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .seconds.do(self.run_strategy, strategy, context)
            elif TimeUnit.MINUTE.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .minutes.do(self.run_strategy, strategy, context)
            elif TimeUnit.HOUR.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .hours.do(self.run_strategy, strategy, context)

        for task in self.tasks:
            if TimeUnit.SECOND.equals(task.time_unit):
                schedule.every(task.interval)\
                    .seconds.do(self.run_task, task, context)
            elif TimeUnit.MINUTE.equals(task.time_unit):
                schedule.every(task.interval)\
                    .minutes.do(self.run_task, task, context)
            elif TimeUnit.HOUR.equals(task.time_unit):
                schedule.every(task.interval)\
                    .hours.do(self.run_task, task, context)

    def stop(self):
        for thread in self.threads:
            thread.stop()

        schedule.clear()

    def clear(self):
        self.threads = []
        schedule.clear()

    def get_strategies(self, identifiers=None):
        if identifiers is None:
            return self.strategies

        strategies = []
        for strategy in self.strategies:
            if strategy.worker_id in identifiers:
                strategies.append(strategy)

        return strategies

    def get_tasks(self):
        return self._tasks

    def get_jobs(self):
        return schedule.jobs

    def run_pending_jobs(self):
        if self.max_iterations is not None and \
                self.max_iterations != -1 and \
                self.iterations >= self.max_iterations:
            self.clear()
        else:
            schedule.run_pending()

    def _add_strategies(self, strategies):
        has_duplicates = False

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

    def _add_tasks(self, tasks):
        has_duplicates = False

        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                if tasks[i].worker_id == tasks[j].worker_id:
                    has_duplicates = True
                    break

        if has_duplicates:
            raise OperationalException(
                "There are duplicate tasks with the same name"
            )

        self._tasks = tasks

    @property
    def strategies(self):
        return self._strategies

    @property
    def app_hooks(self):
        return self._app_hooks

    @property
    def tasks(self):
        return self._tasks

    @property
    def running(self):
        if len(self.strategies) == 0 and len(self.tasks) == 0:
            return False

        if self.max_iterations == -1:
            return True

        return self.max_iterations is None \
            or self.iterations < self.max_iterations

    def has_run(self, worker_id):
        return worker_id in self.history

    def reset(self):
        """
        Reset the strategy orchestrator service
        """
        self.clear()
        self.history = {}
        self.iterations = 0
        self.max_iterations = -1
        self._strategies = []
        self._tasks = []
        self._app_hooks = []
