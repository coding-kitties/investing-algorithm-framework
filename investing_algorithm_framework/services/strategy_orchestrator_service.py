import schedule
from datetime import datetime
from investing_algorithm_framework.domain import StoppableThread, TimeUnit, \
    OperationalException


class StrategyOrchestratorService:

    def __init__(self, market_data_service):
        self.history = {}
        self.strategies = []
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

        if sync:
            strategy.run_strategy(
                market_data=market_data,
                algorithm=algorithm
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

    def start(self, algorithm, number_of_iterations=None):
        self.max_iterations = number_of_iterations

        for strategy in self.strategies:

            if TimeUnit.SECOND.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .seconds.do(
                        self.run_strategy, strategy, algorithm
                    )
            elif TimeUnit.MINUTE.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .minutes.do(
                        self.run_strategy, strategy, algorithm
                    )
            elif TimeUnit.HOUR.equals(strategy.time_unit):
                schedule.every(strategy.interval)\
                    .hours.do(
                        self.run_strategy, strategy, algorithm
                    )

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

    def run_pending_strategies(self):

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

    @property
    def strategies(self):
        return self._strategies

    @strategies.setter
    def strategies(self, strategies):
        self._strategies = strategies

    @property
    def running(self):
        if len(self.strategies) == 0:
            return False

        if self.max_iterations == -1:
            return True

        return self.max_iterations is None \
            or self.iterations < self.max_iterations

    def has_run(self, worker_id):
        return worker_id in self.history
