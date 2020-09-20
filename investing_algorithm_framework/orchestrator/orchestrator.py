from abc import ABC, abstractmethod
from typing import List, Dict
from threading import Thread
from time import sleep

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.context import AlgorithmContext


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
    registered_algorithms = {}
    _running_algorithms = {}

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
        print('stopping all algorithms')

    def stop_algorithm(self, algorithm_id: str) -> None:
        print('stopping algorithm {}'.format(algorithm_id))

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
                algorithm_thread = Thread(
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
    def running_algorithms(self) -> Dict[str, Thread]:
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

