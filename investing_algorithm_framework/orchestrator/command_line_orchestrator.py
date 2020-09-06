from cmd import Cmd
from pyfiglet import Figlet

from .orchestrator import Orchestrator, OrchestratorInterface


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

    @staticmethod
    def do_exit(inp):
        return True

    def do_start_algorithms(self, inp):
        """
        start_algorithms <algorithm_id> optional <cycles>

            description
        """
        self.start_all_algorithms()

    def do_start_algorithm(self, inp):
        """start_algorithm <algorithm_id> optional <cycles> """
        self.start_algorithm(inp)

    def complete_start_algorithm(self, text, line, begidx, endidx):

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
        figlet = Figlet(font='slant')
        print(figlet.renderText('Orchestrator'))
        self.cmdloop()
