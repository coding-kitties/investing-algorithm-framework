from time import sleep
from typing import List
from threading import Thread

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.context import AlgorithmContext


class Orchestrator:
    registered_algorithms: List[AlgorithmContext] = None

    def start(self):

        if self.registered_algorithms is None \
                or len(self.registered_algorithms) < 1:
            raise OperationalException(
                "Orchestrator doesn't have any algorithms configured."
            )

        for algorithm in self.registered_algorithms:
            worker = Thread(
                name=algorithm.algorithm_id,
                target=algorithm.start
            )
            worker.setDaemon(True)
            worker.start()

        while True:
            sleep(1)

    def stop(self):
        pass

    @staticmethod
    def register_algorithms(algorithms: List[AlgorithmContext]) -> None:

        if Orchestrator.registered_algorithms is None:
            Orchestrator.registered_data_providers = []

        Orchestrator.registered_algorithms += algorithms

    @staticmethod
    def register_algorithm(algorithm: AlgorithmContext) -> None:

        if Orchestrator.registered_algorithms is None:
            Orchestrator.registered_algorithms = []

        Orchestrator.registered_algorithms.append(algorithm)
