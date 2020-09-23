import sys
from abc import ABC, abstractmethod
from typing import List, Dict
from threading import Thread
from time import sleep

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.context import AlgorithmContext


class AlgorithmThread(Thread):
    """
    Algorithm thread functions primarily as a normal thread, but implements
    utils functions to stop, start and check if the thread is alive.
    """

    def __init__(self, *args, **keywords):
        Thread.__init__(self, *args, **keywords)
        self.killed = False
        self.__run_backup = self.run
        self.run = self.__run

    def start(self):
        Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    """
    Trace to check if AlgorithmThread needs to be killed.
    If killed is true it will stop the current thread.
    """
    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    """
    Function to kill a given AlgorithmThread
    """
    def kill(self):
        self.killed = True


class OrchestratorInterface(ABC):

    @abstractmethod
    def start_all_algorithms(self, cycles: int = -1, **kwargs) -> None:
        pass

    @abstractmethod
    def start_algorithm(self, algorithm_id: str, cycles: int = -1, **kwargs) \
            -> None:
        pass

    @abstractmethod
    def stop_all_algorithms(self) -> None:
        pass

    @abstractmethod
    def stop_algorithm(self, algorithm_id: str) -> None:
        pass

    @abstractmethod
    def register_algorithms(self, algorithms: List[AlgorithmContext]) -> None:
        pass

    @abstractmethod
    def register_algorithm(self, algorithm: AlgorithmContext) -> None:
        pass


class Orchestrator(OrchestratorInterface):
    """
    Orchestrator is an instance of the OrchestratorInterface. This is the
    standard concrete implementation of the OrchestratorInterface.

    The AlgorithmContext instances that are registered at the Orchestrator
    will be run in a AlgorithmThread.

    If a AlgorithmContext instance is run it will be added to the
    _running_algorithms attribute.
    """
    registered_algorithms = {}
    _running_algorithms: Dict[str, AlgorithmThread] = {}

    def start_all_algorithms(
            self, cycles: int = -1, forced_idle: bool = True
    ) -> None:

        if self.registered_algorithms is None \
                or len(self.registered_algorithms.keys()) < 1:
            raise OperationalException(
                "Orchestrator doesn't have any algorithms configured"
            )

        # run all algorithms
        self._run_algorithms(
            list(self.registered_algorithms.keys()), cycles, forced_idle
        )

    def start_algorithm(
            self, algorithm_id: str, cycles: int = -1, forced_idle: bool = True
    ) -> None:

        if self.registered_algorithms is None \
                or len(self.registered_algorithms) < 1:
            raise OperationalException(
                "Orchestrator doesn't have any algorithms configured"
            )

        self._run_algorithms([algorithm_id], cycles, forced_idle)

    def stop_all_algorithms(self) -> None:

        for algorithm_id in self.running_algorithms:
            self._stop_algorithm(algorithm_id)

    def stop_algorithm(self, algorithm_id: str) -> None:
        self._stop_algorithm(algorithm_id)

    def _stop_algorithm(self, algorithm_id: str) -> None:
        algorithm_thread = self._running_algorithms.get(algorithm_id)

        if algorithm_thread is None:
            return

        # Kill the algorithm
        algorithm_thread.kill()
        algorithm_thread.join()

        # Remove the algorithm from the running algorithms
        self._running_algorithms.pop(algorithm_id)

    def _run_algorithms(
            self,
            algorithm_ids: List,
            cycles: int = -1,
            forced_idle: bool = True,
    ) -> None:

        # Retrieve the algorithm
        for algo_id in algorithm_ids:

            # Throw exception when algorithm is not registered
            if algo_id not in self.registered_algorithms:
                raise OperationalException(
                    "There is algorithm registered with ID: {}".format(algo_id)
                )

            # If algorithm is already running
            if algo_id in self._running_algorithms:
                return

            algo = self.registered_algorithms[algo_id]

            if algo:
                algorithm_thread = AlgorithmThread(
                    target=algo.start,
                    args=(cycles, )
                )
                algorithm_thread.setDaemon(True)
                algorithm_thread.start()
                self._running_algorithms[algo.get_id()] = algorithm_thread

        # Only in forced idle mode. When a decorator is used such as
        # the CommandLineOrchestrator this flag should be set to false.
        if forced_idle:

            while True:
                finished = True
                sleep(1)

                # Check if algorithms are still running
                for running_algo_key in self._running_algorithms:

                    if self._running_algorithms[running_algo_key].is_alive():
                        finished = False

                # All algorithms stopped
                if finished:
                    return

    @property
    def running_algorithms(self) -> Dict[str, AlgorithmThread]:
        return self._running_algorithms

    def register_algorithms(self, algorithms: List[AlgorithmContext]) -> None:

        if Orchestrator.registered_algorithms is None:
            Orchestrator.registered_data_providers = {}

        for algo in algorithms:

            if algo.get_id() in Orchestrator.registered_algorithms:
                raise OperationalException(
                    "There is already an algorithm registered with the given "
                    "ID. Make sure that the IDs do not conflict"
                )

            Orchestrator.registered_algorithms[algo.get_id()] = algo

    def register_algorithm(self, algorithm: AlgorithmContext) -> None:

        if Orchestrator.registered_algorithms is None:
            Orchestrator.registered_algorithms = {}

        if algorithm.get_id() in Orchestrator.registered_algorithms:
            raise OperationalException(
                "There is already an algorithm registered with the same "
                "ID. Make sure that the IDs do not conflict"
            )

        Orchestrator.registered_algorithms[algorithm.get_id()] = algorithm

