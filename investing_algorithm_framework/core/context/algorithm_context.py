from time import sleep

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.workers import Worker
from .algorithm_context_configuration import AlgorithmContextConfiguration


class AlgorithmContext:
    """
    The AlgorithmContext defines the context of an algorithm.

    An algorithm consist out of an data provider and a set of
    strategies that belong to the data provider.
    """

    def __init__(
            self,
            algorithm_id: str,
            data_provider,
            initializer=None,
            config: AlgorithmContextConfiguration = None,
            cycles: int = None
    ):

        # Check if data_provider is instance of AbstractDataProvider and
        # Worker
        from investing_algorithm_framework.core.data_providers \
            import AbstractDataProvider
        assert isinstance(data_provider, AbstractDataProvider), (
            'Data provider must be an instance of the '
            'AbstractDataProvider class'
        )

        assert isinstance(data_provider, Worker), (
            'Data provider must be an instance of the Worker class'
        )

        self.algorithm_id = algorithm_id
        self.data_provider = data_provider
        self.cycles = cycles

        if initializer is not None:
            # Check if initializer is an instance of
            # AlgorithmContextInitializer
            from . import AlgorithmContextInitializer
            assert isinstance(initializer, AlgorithmContextInitializer), (
                'Initializer must be an instance of '
                'AlgorithmContextInitializer'
            )

        self.initializer = initializer

        self._config = config

        if config is None:
            self._config = AlgorithmContextConfiguration()

        # Validate initialization
        self.__check_initialization()

    def __check_initialization(self):
        """
        Utils function to check the necessary attributes of the
        AlgorithmContext instance
        """

        if self.algorithm_id is None:
            raise OperationalException("AlgorithmContext Id is not set")

    def start(self) -> None:
        """
        Run the current state of the investing_algorithm_framework
        """

        # Call initializer if set
        if self.initializer is not None:
            self.initializer.initialize(self)

        self._run()

    def _run(self) -> None:
        iteration = 0
        self.data_provider.start(algorithm_context=self)
        iteration += 1

        while self.check_context(iteration):
            sleep(1)
            self.data_provider.start(algorithm_context=self)
            iteration += 1

    def check_context(self, iteration) -> bool:

        if self.cycles and self.cycles > 0:
            return self.cycles > iteration

        return True

    def set_algorithm_context_initializer(
            self, algorithm_context_initializer
    ) -> None:

        # Check if initializer is an instance of AlgorithmContextInitializer
        from . import AlgorithmContextInitializer
        assert isinstance(
            algorithm_context_initializer, AlgorithmContextInitializer
        ), (
            'Initializer must be an instance of AlgorithmContextInitializer'
        )
        self.initializer = algorithm_context_initializer

    @property
    def config(self) -> AlgorithmContextConfiguration:
        return self._config
