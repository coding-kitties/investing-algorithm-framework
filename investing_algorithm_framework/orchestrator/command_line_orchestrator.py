from cmd import Cmd
from typing import List

from pyfiglet import Figlet

from .orchestrator import Orchestrator, OrchestratorInterface
from ..core.context import AlgorithmContext


class CommandLineOrchestrator(Cmd, OrchestratorInterface):

    def __init__(self, orchestrator: Orchestrator) -> None:
        super(CommandLineOrchestrator, self).__init__()
        self._orchestrator = orchestrator

    # Adapter call to Orchestrator instance
    def start_all_algorithms(self, cycles: int = -1, **kwargs) -> None:
        """
        Delegates 'start_all_algorithms' functionality to an
        Orchestrator instance
        """
        self._orchestrator.start_all_algorithms(cycles, False)

    # Adapter call to Orchestrator instance
    def start_algorithm(
            self, algorithm_id: str, cycles: int = -1, **kwargs
    ) -> None:
        """
        Delegates 'start_algorithm' functionality to an Orchestrator instance
        """
        self._orchestrator.start_algorithm(algorithm_id, cycles, False)

    # Adapter call to Orchestrator instance
    def stop_all_algorithms(self) -> None:
        """
        Delegates 'stop_all_algorithms' functionality to an
        Orchestrator instance
        """
        self._orchestrator.stop_all_algorithms()

    # Adapter call to Orchestrator instance
    def stop_algorithm(self, algorithm_id: str) -> None:
        """
        Delegates 'stop_algorithm' functionality to an
        Orchestrator instance
        """
        self._orchestrator.stop_algorithm(algorithm_id)

    def register_algorithms(self, algorithms: List[AlgorithmContext]) -> None:
        """
        Delegates 'register_algorithms' functionality to an
        Orchestrator instance
        """
        self._orchestrator.register_algorithms(algorithms)

    def register_algorithm(self, algorithm: AlgorithmContext) -> None:
        """
        Delegates 'register_algorithm' functionality to an
        Orchestrator instance
        """
        self._orchestrator.register_algorithm(algorithm)

    @staticmethod
    def do_exit(inp):
        return True

    def do_start_algorithms(self, inp):
        """
        start_algorithms <algorithm_id> optional <cycles>

            <algorithm_id> Optional unique id that identifies your algorithm
            <cycles> Optional parameter that will specify how many cycles
            your algorithm will run.

            This command will start all algorithms.
        """

        # Extract all the algorithm ID's
        algorithm_ids = list(set(inp.split()))

        # Start all algorithms if nothing is specified
        if len(algorithm_ids) < 1:
            self.start_all_algorithms()

        # Check if algorithms are registered
        for algorithm_id in algorithm_ids:

            if algorithm_id not in self._orchestrator.registered_algorithms:
                print(
                    "There is no registered algorithm "
                    "belonging to the ID: {}".format(algorithm_id)
                )
                return

        # After checks start the given algorithms
        for algorithm_id in algorithm_ids:
            print('Starting algorithm {}'.format(algorithm_id))
            self.start_algorithm(algorithm_id)

    def do_list_running_algorithms(self, inp) -> None:

        if len(self._orchestrator.running_algorithms.keys()) == 0:
            print("Currently there are no algorithms running")
            return

        print("Currently running algorithms: ")
        for algorithm in self._orchestrator.running_algorithms.keys():
            print(algorithm)

    def complete_start_algorithms(self, text, line, begidx, endidx):
        """
        Tab completion for start algorithm
        """
        if len(self._orchestrator.registered_algorithms.keys()) < 0:
            return "No algorithms registered"

        if len(self._orchestrator.registered_algorithms.keys()) == 1:
            return list(self._orchestrator.registered_algorithms.keys())

        return [
            algo for algo in self._orchestrator.registered_algorithms.keys()
            if str(algo).startswith(text)
        ]

    def do_EOF(self, line):
        return True

    def start(self):
        """
        Main loop for the command line orchestrator
        """
        figlet = Figlet(font='slant')
        print(figlet.renderText('Orchestrator'))
        self.cmdloop()
