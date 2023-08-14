import logging
import schedule
from datetime import datetime
from investing_algorithm_framework.domain import StoppableThread, TimeUnit, \
    OperationalException

logger = logging.getLogger("investing_algorithm_framework")


class StrategyOrchestratorService:

    def __init__(self, market_data_service):
        self.history = {}
        self._strategies = []
        self._tasks = []
        self.threads = []
        self.iterations = 0
        self.max_iterations = -1
        self.clear()
        self.market_data_service = market_data_service

    def cleanup_threads(self):

        for stoppable in self.threads:
            if not stoppable.is_alive():
                # get results from thread
                stoppable.done = True
        self.threads = [t for t in self.threads if not t.done]

    def run_strategy(self, strategy, algorithm, sync=False):
        self.cleanup_threads()

        matching_thread = next(
            (t for t in self.threads if t.name == strategy.worker_id),
            None
        )

        # Don't run a strategy that is already running
        if matching_thread:
            return

        market_data = self.market_data_service.get_data_for_strategy(strategy)

        logger.info(f"Running strategy {strategy.worker_id}")

        if sync:
            strategy.run_strategy(
                market_data=market_data, algorithm=algorithm
            )
        else:
            self.iterations += 1
            thread = StoppableThread(
                target=strategy.run_strategy,
                kwargs={
                    "market_data": market_data,
                    "algorithm": algorithm
                }
            )
            thread.name = strategy.worker_id
            thread.start()
            self.threads.append(thread)

        self.history[strategy.worker_id] = {"last_run": datetime.utcnow()}

    def run_task(self, task, algorithm, sync=False):
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
            task.run(algorithm=algorithm)
        else:
            self.iterations += 1
            thread = StoppableThread(
                target=task.run,
                kwargs={"algorithm": algorithm}
            )
            thread.name = task.worker_id
            thread.start()
            self.threads.append(thread)

        self.history[task.worker_id] = {"last_run": datetime.utcnow()}

    def start(self, algorithm, number_of_iterations=None):
        self.max_iterations = number_of_iterations

        for strategy in self.strategies:

            if TimeUnit.SECOND.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .seconds.do(self.run_strategy, strategy, algorithm)
            elif TimeUnit.MINUTE.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .minutes.do(self.run_strategy, strategy, algorithm)
            elif TimeUnit.HOUR.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .hours.do(self.run_strategy, strategy, algorithm)

        for task in self.tasks:
            
            if TimeUnit.SECOND.equals(task.time_unit):
                schedule.every(task.interval)\
                    .seconds.do(self.run_task, task, algorithm)
            elif TimeUnit.MINUTE.equals(task.time_unit):
                schedule.every(task.interval)\
                    .minutes.do(self.run_task, task, algorithm)
            elif TimeUnit.HOUR.equals(task.time_unit):
                schedule.every(task.interval)\
                    .hours.do(self.run_task, task, algorithm)

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

    def add_strategy(self, strategy):

        if strategy.worker_id not in self._strategies:
            self._strategies.append(strategy)
        else:
            raise OperationalException(
                "Strategy already exists with the same name"
            )

    def add_strategies(self, strategies):
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

        self.strategies = strategies

    def add_tasks(self, tasks):
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

        self.tasks = tasks

    @property
    def strategies(self):
        return self._strategies

    @strategies.setter
    def strategies(self, strategies):
        self._strategies = strategies

    @property
    def tasks(self):
        return self._tasks

    @tasks.setter
    def tasks(self, tasks):
        self._tasks = tasks

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
