import os
import logging
from random import randint
from time import sleep
from typing import List, Dict

from investing_algorithm_framework.core.models import db, Order, OrderType, \
    Position
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
            resources_directory: str,
            data_providers: List = None,
            portfolio_managers: List = None,
            order_executors: List = None,
            algorithm_id: str = None,
            initializer=None,
            config=None,
            cycles: int = None
    ):

        if not os.path.isdir(resources_directory):
            raise OperationalException(
                "Resources directory does not exist, make sure to provide "
                "an empty directory that can be used for storage of resources"
            )

        if algorithm_id is None:
            self.algorithm_id = str(randint(1000, 10000))
        else:
            self.algorithm_id = algorithm_id

        db.connect_sqlite(
            database_directory_path=resources_directory,
            database_name=self.algorithm_id
        )
        db.initialize_tables()

        if data_providers is None:
            data_providers = []

        if order_executors is None:
            order_executors = []

        if portfolio_managers is None:
            portfolio_managers = []

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

        self._order_executors = {}

        for order_executor in order_executors:
            assert isinstance(order_executor, AbstractOrderExecutor), (
                'Order executor must be an instance of the '
                'AbstractOrderExecutor class'
            )

            self.order_executors[order_executor.broker] = order_executor

            # Check if order executor is instance of AbstractOrderExecutor
        from investing_algorithm_framework.core.portfolio_managers \
            import AbstractPortfolioManager

        self._portfolio_managers = {}

        for portfolio_manager in portfolio_managers:
            assert isinstance(portfolio_manager, AbstractPortfolioManager), (
                'Portfolio manager must be an instance of the '
                'AbstractPortfolioManager class'
            )

            self._portfolio_managers[
                portfolio_manager.broker
            ] = portfolio_manager

        self._data_providers = data_providers
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

    @property
    def data_providers(self) -> List:
        return self._data_providers

    @property
    def portfolio_managers(self) -> Dict:
        return self._portfolio_managers

    def add_initializer(self, initializer):
        from investing_algorithm_framework.core.context \
            import AlgorithmContextInitializer

        assert isinstance(initializer, AlgorithmContextInitializer), (
            'Initializer must be an instance of the '
            'AlgorithmContextInitializer class'
        )

        self.initializer = initializer

    def add_data_provider(self, data_provider):
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

        self._data_providers.append(data_provider)

    def add_order_executor(self, order_executor):
        # Check if order executor is instance of AbstractOrderExecutor
        from investing_algorithm_framework.core.order_executors \
            import AbstractOrderExecutor

        assert isinstance(order_executor, AbstractOrderExecutor), (
            'Order executor must be an instance of the '
            'AbstractOrderExecutor class'
        )

        self.order_executors[order_executor.broker] = order_executor

    def add_portfolio_manager(self, portfolio_manager):
        # Check if order executor is instance of AbstractPortfolioManager
        from investing_algorithm_framework.core.portfolio_managers \
            import AbstractPortfolioManager

        assert isinstance(portfolio_manager, AbstractPortfolioManager), (
            'portfolio manager must be an instance of the '
            'AbstractPortfolioManager class'
        )

        self.portfolio_managers[portfolio_manager.broker] = portfolio_manager

    @property
    def order_executors(self) -> List:
        return self._order_executors

    def start(self, cycles: int = None) -> None:
        """
        Run the current state of the investing_algorithm_framework
        """
        self.cycles = cycles

        # Call initializer if set
        if self.initializer is not None:
            self.initializer.initialize(self)

        self._run()

    def _run(self) -> None:
        iteration = 0

        if len(self.data_providers) == 0:
            return

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
            trading_pair: str,
            amount: float,
            price: float,
            order_type: OrderType,
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
        requested_space = amount * price

        if OrderType.BUY.equals(order_type):
            free_space = portfolio_manager.get_free_portfolio_size(self)

            if free_space is None:
                raise OperationalException("Free space is not specified")

            if requested_space > free_space:
                raise OperationalException(
                    "Request order size exceeds free portfolio size"
                )

        if "/" not in trading_pair and "-" not in trading_pair:
            raise OperationalException(
                "Unsupported trading pair definition, only / and - are "
                "supported as delimiter"
            )

        if "/" in trading_pair:
            pairs = trading_pair.split("/")
        else:
            pairs = trading_pair.split("-")

        position = Position.query.filter_by(symbol=pairs[0]).first()

        if position is None:
            position = Position(symbol=pairs[0])
            position.save()

        order = Order(
            order_type=order_type.value,
            trading_pair=trading_pair,
            completed=False,
            price=price,
            amount=amount
        )

        order.save()
        position.orders.append(order)

        db.session.commit()

        order_executor.execute_limit_order(
            order.trading_pair, order.price, order.amount, self
        )

    def get_free_portfolio_size(self, broker):

        if broker not in self.portfolio_managers:
            raise OperationalException(
                "There is no portfolio manager linked to the given broker"
            )

        portfolio_manager = self.portfolio_managers[broker]
        return portfolio_manager.get_free_portfolio_size(self)
