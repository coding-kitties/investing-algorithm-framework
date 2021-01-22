import logging
from random import randint
from time import sleep
from typing import List


from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.workers import Worker
from .algorithm_context_configuration import AlgorithmContextConfiguration

logger = logging.getLogger(__name__)


class AlgorithmContext:
    """
    The AlgorithmContext defines the context of an algorithm.

    An algorithm consist out of an data provider and a set of
    strategies that belong to the data provider.
    """

    def __init__(
            self,
            data_providers: List,
            portfolio_managers: List,
            order_executors: List,
            algorithm_id: str = None,
            initializer=None,
            config=None,
            cycles: int = None
    ):

        if algorithm_id is None:
            self.algorithm_id = randint(1000, 10000)
        else:
            self.algorithm_id = algorithm_id

        if data_providers is None:
            raise OperationalException("No data providers provided")

        if order_executors is None:
            raise OperationalException("No order executors provided")

        if portfolio_managers is None:
            raise OperationalException("No portfolio managers provided")

        # Check if data_provider is instance of AbstractDataProvider and
        # Worker
        from investing_algorithm_framework.core.data_providers \
            import AbstractDataProvider

        for data_provider in data_providers:
            assert isinstance(data_provider, AbstractDataProvider), (
                'Data provider must be an instance of the '
                'AbstractDataProvider class'
            )

            assert isinstance(data_provider, Worker), (
                'Data provider must be an instance of the Worker class'
            )

        # Check if order executor is instance of AbstractOrderExecutor
        from investing_algorithm_framework.core.order_executors \
            import AbstractOrderExecutor

        self.order_executors = {}

        for order_executor in order_executors:
            assert isinstance(order_executor, AbstractOrderExecutor), (
                'Order executor must be an instance of the '
                'AbstractOrderExecutor class'
            )

            self.order_executors[order_executor.broker] = order_executor

            # Check if order executor is instance of AbstractOrderExecutor
        from investing_algorithm_framework.core.portfolio_managers \
            import AbstractPortfolioManager

        self.portfolio_managers = {}

        for portfolio_manager in portfolio_managers:
            assert isinstance(portfolio_manager, AbstractPortfolioManager), (
                'Portfolio manager must be an instance of the '
                'AbstractPortfolioManager class'
            )

            self.portfolio_managers[
                portfolio_manager.broker
            ] = portfolio_manager

        self.data_providers = data_providers
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
        elif not isinstance(config, dict) \
                and not isinstance(config, AlgorithmContextConfiguration):
            raise OperationalException("Given config object is not supported")


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
        
        while self.check_context(iteration):

            for data_provider in self.data_providers:
                data_provider.start(algorithm_context=self)

            iteration += 1
            sleep(1)

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

    def perform_limit_order(
            self,
            broker: str,
            asset: str,
            max_price: float,
            quantity: int,
            commission: float,
            **kwargs
    ):

        if broker not in self.portfolio_managers:
            raise OperationalException(
                "There is no portfolio manager linked to the given broker"
            )

        if broker not in self.order_executors:
            raise OperationalException(
                "There is no order executor linked to the given broker"
            )

        portfolio_manager = self.portfolio_managers[broker]
        order_executor = self.order_executors[broker]

        free_space = portfolio_manager.get_free_portfolio_size(self)

        if (max_price * quantity) + commission > free_space:
            logger.warning(
                "Cannot execute order because not enough free "
                "space in portfolio, your current free space is {}".format(
                    free_space
                )
            )
            return

        order_executor.execute_limit_order(
            asset, max_price, quantity, self, **kwargs
        )

        # Notify the portfolio manager that
        # the order was executed
        try:
            portfolio_manager.order_executed_notification(
                asset, max_price, quantity, commission, **kwargs
            )
        except OperationalException:
            pass

    def get_space_portfolio_size(self, broker):

        if broker not in self.portfolio_managers:
            raise OperationalException(
                "There is no portfolio manager linked to the given broker"
            )

        portfolio_manager = self.portfolio_managers[broker]
        return portfolio_manager.get_free_portfolio_size(self)
