from time import sleep
from investing_algorithm_framework.core.data_providers import \
    AbstractDataProvider
from investing_algorithm_framework.core.workers import Worker


class AlgorithmContext:
    """
    The AlgorithmContext defines the context of an algorithm.

    An algorithm consist out of an data provider and a set of
    strategies that belong to the data provider.
    """

    def __init__(self, data_provider, cycles: int = None):

        assert isinstance(data_provider, AbstractDataProvider), (
            'Data provider must be an instance of the '
            'AbstractDataProvider class'
        )

        assert isinstance(data_provider, Worker), (
            'Data provider must be an instance of the Worker class'
        )

        self.data_provider = data_provider
        self.cycles = cycles

    def start(self) -> None:
        """
        Run the current state of the investing_algorithm_framework
        """
        self._run()

    def _run(self) -> None:
        iteration = 0
        self.data_provider.start()
        iteration += 1

        while self.check_context(iteration):
            sleep(1)
            self.data_provider.start()
            iteration += 1

    def check_context(self, iteration):

        if self.cycles and self.cycles > 0:
            return self.cycles > iteration

        return True
