import logging
from typing import List

from investing_algorithm_framework.configuration import Config
from investing_algorithm_framework.configuration.constants import \
    TRADING_SYMBOL
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import TimeUnit, OrderType, \
    db, OrderSide, OrderStatus
from investing_algorithm_framework.core.models.data_provider import \
    TradingDataTypes
from investing_algorithm_framework.core.workers import Worker, StrategyWorker
from investing_algorithm_framework.extensions import scheduler
from investing_algorithm_framework.core.data_providers import\
    DefaultDataProviderFactory, DataProvider
from investing_algorithm_framework.configuration.constants import \
    RESERVED_IDENTIFIERS
from investing_algorithm_framework.core.market_services import \
    DefaultMarketServiceFactory
from investing_algorithm_framework.core.portfolio_managers import \
    DefaultPortfolioManagerFactory
from investing_algorithm_framework.core.order_executors import \
    DefaultOrderExecutorFactory, OrderExecutor

logger = logging.getLogger(__name__)


class AlgorithmContext:
    """
    The AlgorithmContext defines the context of an algorithm.

    An algorithm consist out of an data_provider provider and a set of
    strategies that belong to the data_provider provider.
    """
    _config = None
    _workers = []
    _running_workers = []
    _data_providers = {}
    _order_executors = {}
    _portfolio_managers = {}
    _market_services = {}
    _initializer = None
    _initialized = False

    # Decorator for worker to allow for deferred calling
    @staticmethod
    def schedule(
        function=None,
        worker_id: str = None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10
    ):

        if function:
            return Worker(function, worker_id, time_unit, interval)
        else:
            def wrapper(f):
                return Worker(f, worker_id, time_unit, interval)
            return wrapper

    # Decorator for strategy worker to allow for deferred calling
    @staticmethod
    def strategy(
        function=None,
        worker_id: str = None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10,
        data_provider_identifier=None,
        trading_data_type=None,
        trading_data_types=None,
        target_symbol=None,
        target_symbols=None,
        trading_symbol=None
    ):

        if function:
            return StrategyWorker(
                function,
                worker_id,
                time_unit,
                interval,
                data_provider_identifier,
                trading_data_type,
                trading_data_types,
                target_symbol,
                target_symbols,
                trading_symbol
            )
        else:
            def wrapper(f):
                return StrategyWorker(
                    f,
                    worker_id,
                    time_unit,
                    interval,
                    data_provider_identifier,
                    trading_data_type,
                    trading_data_types,
                    target_symbol,
                    target_symbols,
                    trading_symbol
                )

            return wrapper

    def initialize(self, config=None):

        if config is not None:
            assert isinstance(config, Config), (
                "Config is not an instance of config"
            )
            self._config = config
        else:
            self._config = Config()

    def start(self):

        # Initialize the algorithm context
        if not self._initialized:

            # Run the initializer
            if self._initializer is not None:
                self._initializer.initialize(self)

        # Initialize the portfolio managers
        for portfolio_manager_key in self._portfolio_managers:
            portfolio_manager = self._portfolio_managers[portfolio_manager_key]
            portfolio_manager.initialize(self)

        for order_executor_key in self._order_executors:
            order_executor = self._order_executors[order_executor_key]
            order_executor.initialize(self)

        self._initialized = True

        # Start the workers
        self.start_workers()

    def stop(self):
        self.stop_all_workers()

    def start_workers(self):

        if not self.running:
            # Start functional workers
            for worker in self._workers:
                worker.add_to_scheduler(scheduler)
                self._running_workers.append(worker)

    def start_strategies(self):

        if not self.running:
            # Start functional workers
            for worker in self._workers:
                worker.add_to_scheduler(scheduler)
                self._running_workers.append(worker)

    def stop_all_workers(self):
        scheduler.remove_all_jobs()
        self._running_workers = []

    def add_worker(self, worker):
        """
        Function to ad an worker to list of workers of the
        algorithm context.
        """

        assert isinstance(worker, Worker), OperationalException(
            "Worker is not an instance of an Worker"
        )

        for installed_worker in self._workers:

            if installed_worker.worker_id == worker.worker_id:
                return

        self._workers.append(worker)

    def add_strategy(self, strategy_worker):

        assert isinstance(strategy_worker, StrategyWorker), \
            OperationalException(
                "Strategy worker is not an instance of an StrategyWorker"
            )

        for installed_worker in self._workers:

            if installed_worker.worker_id == strategy_worker.worker_id:
                return

        self._workers.append(strategy_worker)

    @property
    def running(self) -> bool:
        """
            An utility property to check if there are active workers for the
            algorithm.
        """

        return len(self._running_workers) != 0

    @property
    def workers(self) -> List:
        return self._workers

    @property
    def running_workers(self) -> List:
        return self._running_workers

    @property
    def running_strategies(self) -> List:
        strategies = []

        for worker in self._workers:
            if isinstance(worker, StrategyWorker):
                strategies.append(worker)

        return strategies

    @property
    def config(self) -> Config:
        return self._config

    def add_order_executor(self, order_executor):
        from investing_algorithm_framework.core.order_executors \
            import OrderExecutor

        if order_executor in RESERVED_IDENTIFIERS:
            raise OperationalException(
                "Identifier of order executor is reserved"
            )

        assert isinstance(order_executor, OrderExecutor), (
            'Provided object must be an instance of the OrderExecutor class'
        )

        if order_executor.identifier in self._order_executors:
            raise OperationalException("Order executor id already exists")

        self._order_executors[order_executor.identifier] = order_executor

    @property
    def order_executors(self) -> List:
        order_executors = []

        for order_executor in self._order_executors:
            order_executors.append(order_executor)

        return order_executors

    def get_order_executor(
        self, identifier=None, throw_exception: bool = True
    ) -> OrderExecutor:

        if identifier is None:

            if len(self._order_executors.keys()) == 0:
                raise OperationalException(
                    "Algorithm has no order executors registered"
                )

            return self._order_executors[
                list(self._order_executors.keys())[0]
            ]

        if identifier not in self._order_executors:

            if identifier in RESERVED_IDENTIFIERS:
                order_executor = DefaultOrderExecutorFactory\
                    .of_market(identifier)
                order_executor.initialize(self)
                self._order_executors[order_executor.identifier] = \
                    order_executor
                return order_executor

            if throw_exception:
                raise OperationalException(
                    f"No corresponding order executor found for "
                    f"identifier {identifier}"
                )

            return None

        return self._order_executors[identifier]

    def add_data_provider(self, data_provider):
        from investing_algorithm_framework.core.data_providers \
            import DataProvider

        if data_provider in RESERVED_IDENTIFIERS:
            raise OperationalException(
                "Identifier of data provider is reserved"
            )

        assert isinstance(data_provider, DataProvider), (
            'Provided object must be an instance of the DataProvider class'
        )

        if data_provider.identifier in self._data_providers:
            raise OperationalException("DataProvider id already exists")

        self._data_providers[data_provider.identifier] = data_provider

    @property
    def data_providers(self) -> List:
        data_providers = []

        for data_provider in self._data_providers:
            data_providers.append(data_provider)

        return data_providers

    def get_data_provider(
            self, identifier=None, throw_exception: bool = True
    ) -> DataProvider:

        if identifier is None:

            if len(self._data_providers.keys()) == 0:
                raise OperationalException(
                    "Algorithm has no data providers registered"
                )

            return self._data_providers[
                list(self._data_providers.keys())[0]
            ]

        if identifier not in self._data_providers:

            if identifier in RESERVED_IDENTIFIERS:
                data_provider = DefaultDataProviderFactory\
                    .of_identifier(identifier)

                if data_provider is not None:
                    self._data_providers[identifier.upper()] = data_provider
                    return data_provider

            if throw_exception:
                raise OperationalException(
                    f"No corresponding data provider found for "
                    f"identifier {identifier}"
                )

            return None

        return self._data_providers[identifier]

    def add_initializer(self, initializer):
        from investing_algorithm_framework.core.context \
            import AlgorithmContextInitializer

        assert isinstance(initializer, AlgorithmContextInitializer), (
            'Provided object must be an instance of the '
            'AlgorithmContextInitializer class'
        )

        self._initializer = initializer

    def add_portfolio_manager(self, portfolio_manager):
        # Check if order executor is instance of AbstractPortfolioManager
        from investing_algorithm_framework.core.portfolio_managers \
            import PortfolioManager

        assert isinstance(portfolio_manager, PortfolioManager), (
            'Provided object must be an instance of the '
            'AbstractPortfolioManager class'
        )

        if portfolio_manager.identifier in self._portfolio_managers:
            raise OperationalException(
                f"Portfolio manager identifier {portfolio_manager.identifier} "
                f"already exists"
            )

        self._portfolio_managers[portfolio_manager.identifier] \
            = portfolio_manager

    @property
    def portfolio_managers(self) -> List:
        portfolio_managers = []

        for key in self._portfolio_managers:
            portfolio_managers.append(self._portfolio_managers[key])

        return portfolio_managers

    def get_portfolio_manager(
        self, identifier: str = None, throw_exception: bool = True
    ):

        if identifier is None:

            if len(self._portfolio_managers.keys()) == 0:
                raise OperationalException(
                    "Algorithm has no portfolio managers registered"
                )

            return self._portfolio_managers[
                list(self._portfolio_managers.keys())[0]
            ]

        if identifier not in self._portfolio_managers:

            if identifier in RESERVED_IDENTIFIERS:
                portfolio_manager = DefaultPortfolioManagerFactory\
                    .of_market(identifier)

                portfolio_manager.initialize(self)
                self._portfolio_managers[portfolio_manager.identifier] \
                    = portfolio_manager

                return portfolio_manager

            if throw_exception:
                raise OperationalException(
                    f"No corresponding portfolio manager found for "
                    f"identifier {identifier}"
                )

            return None

        return self._portfolio_managers[identifier]

    def add_market_service(self, market_service):
        from investing_algorithm_framework.core.market_services \
            import MarketService

        assert isinstance(market_service, MarketService), (
            'Provided object must be an instance of the MarketService class'
        )

        if market_service.market in self._market_services:
            raise OperationalException("Market service market already exists")

        self._market_services[market_service.market] = market_service

    @property
    def market_services(self) -> List:
        market_services = []

        for market_service in self._market_services:
            market_services.append(market_service)

        return market_services

    def get_market_service(
            self, market: str, throw_exception: bool = True
    ):
        if market not in self._market_services:

            if market in RESERVED_IDENTIFIERS:
                market_service = DefaultMarketServiceFactory\
                    .of_market(market)
                market_service.initialize(self)

                if market_service is not None:
                    self._market_services[market.upper()] = market_service
                    return market_service

            if throw_exception:
                raise OperationalException(
                    f"No corresponding market service found for "
                    f"market {market}"
                )

            return None

        return self._market_services[market]

    def set_algorithm_context_initializer(
            self, algorithm_context_initializer
    ) -> None:

        # Check if initializer is an instance of AlgorithmContextInitializer
        from investing_algorithm_framework.core.context import \
            AlgorithmContextInitializer

        assert isinstance(
            algorithm_context_initializer, AlgorithmContextInitializer
        ), (
            'Initializer must be an instance of AlgorithmContextInitializer'
        )
        self._initializer = algorithm_context_initializer

    def deposit(self, amount, identifier: str = None):
        portfolio = self.get_portfolio_manager(identifier).get_portfolio()
        portfolio.deposit(amount)

    def withdraw(self, amount, identifier: str = None):
        portfolio = self.get_portfolio_manager(identifier).get_portfolio()
        portfolio.withdraw(amount)

    def add_order(self, order, identifier: str = None):
        portfolio_manager = self.get_portfolio_manager(identifier)
        portfolio_manager.add_order(order)

    def create_limit_buy_order(
            self,
            identifier: str,
            symbol: str,
            price: float,
            amount: float,
            execute=False
    ):
        portfolio_manager = self.get_portfolio_manager(identifier)
        order = portfolio_manager.create_order(
            symbol=symbol,
            price=price,
            amount_target_symbol=amount,
            order_type=OrderType.LIMIT.value
        )

        if execute:
            portfolio_manager.add_order(order)
            self.execute_limit_buy_order(identifier, order)
            order.set_pending()
            db.session.commit()

        return order

    def create_limit_sell_order(
            self, identifier, symbol, price, amount, execute=False
    ):
        portfolio_manager = self.get_portfolio_manager(identifier)
        order = portfolio_manager.create_order(
            symbol=symbol,
            price=price,
            amount_target_symbol=amount,
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value
        )

        if execute:
            # Execute order and set to pending state
            portfolio_manager.add_order(order)
            self.execute_limit_sell_order(identifier, order)
            order.set_pending()

        return order

    def create_market_sell_order(
        self,
        symbol,
        amount_target_symbol,
        identifier: str = None,
        execute=False
    ):
        portfolio_manager = self.get_portfolio_manager(identifier)
        order = portfolio_manager.create_order(
            symbol=symbol,
            amount_target_symbol=amount_target_symbol,
            order_type=OrderType.MARKET.value,
            order_side=OrderSide.SELL.value
        )

        if execute:
            portfolio_manager.add_order(order)
            self.execute_market_sell_order(identifier, order)
            order.set_pending()

        return order

    def execute_limit_sell_order(self, identifier, order):
        order_executor = self.get_order_executor(identifier)
        order_executor.execute_limit_order(order, self)

    def execute_limit_buy_order(self, identifier, order):
        order_executor = self.get_order_executor(identifier)
        order_executor.execute_limit_order(order, self)

    def execute_market_sell_order(self, identifier, order):
        order_executor = self.get_order_executor(identifier)
        order_executor.execute_market_order(order, self)

    def execute_market_buy_order(self, identifier, order):
        order_executor = self.get_order_executor(identifier)
        order_executor.execute_market_order(order, self)

    def check_order_status(self, identifier=None, symbol: str = None):
        portfolio_manager = self.get_portfolio_manager(identifier)
        orders = portfolio_manager\
            .get_orders(symbol, status=OrderStatus.PENDING)
        order_executor = self.get_order_executor(identifier)

        for order in orders:
            status = order_executor.get_order_status(order, self)
            order.update(db, {"status": status}, True)

    def get_pending_orders(
            self, identifier=None, symbol: str = None, lazy=False
    ):
        portfolio_manager = self.get_portfolio_manager(identifier)
        return portfolio_manager.get_orders(symbol, OrderStatus.PENDING, lazy)

    def check_pending_orders(self, identifier=None, symbol: str = None):

        if identifier is not None:

            portfolio_manager = self.get_portfolio_manager(identifier)

            order_executor = \
                self.get_order_executor(portfolio_manager.identifier)

            pending_orders = portfolio_manager.get_pending_orders(symbol)

            for pending_order in pending_orders:
                status = order_executor.get_order_status(
                    pending_order, self
                )

                if OrderStatus.SUCCESS.equals(status):
                    pending_order.set_executed()
                else:
                    pending_order.update(db, {status: status.value})
        else:

            for portfolio_manager_key in self._portfolio_managers:
                portfolio_manager = self._portfolio_managers[
                    portfolio_manager_key
                ]

                pending_orders = portfolio_manager.get_pending_orders(symbol)

                order_executor = self.get_order_executor(
                    portfolio_manager.identifier
                )

                for pending_order in pending_orders:
                    status = order_executor.get_order_status(
                        pending_order, self
                    )

                    if OrderStatus.SUCCESS.equals(status):
                        pending_order.set_executed()
                    else:
                        pending_order.update(db, {status: status.value})

    def get_data(
            self,
            identifier,
            trading_data_type=None,
            target_symbol=None,
            trading_symbol=None,
            target_symbols: List = None
    ):
        data_provider = self.get_data_provider(identifier)

        # Check if trading symbol is specified
        if trading_symbol is None:
            trading_symbol = self.config.get(TRADING_SYMBOL, None)

            if trading_symbol is None:
                raise OperationalException(
                    "Trading symbol is not set. Either provide a "
                    "'trading_symbol' param in the method or set "
                    "the 'trading_symbol' attribute in the algorithm "
                    "config."
                )

        if target_symbols is None and target_symbol is None \
                and trading_data_type is not None:
            raise OperationalException(
                "You must either set the target symbol param or "
                "target symbols param for this trading data type"
            )

        if TradingDataTypes.TICKER.equals(trading_data_type):

            if target_symbols is not None:
                tickers = []

                for target_symbol in target_symbols:
                    tickers.append(
                        data_provider.provide_ticker(
                            target_symbol=target_symbol,
                            trading_symbol=trading_symbol,
                            algorithm_context=self
                        )
                    )

                return tickers

            return data_provider.provide_ticker(
                target_symbol=target_symbol,
                trading_symbol=trading_symbol,
                algorithm_context=self
            )

        if TradingDataTypes.ORDER_BOOK.equals(trading_data_type):

            if target_symbols is not None:
                tickers = []

                for target_symbol in target_symbols:
                    tickers.append(
                        data_provider.provide_order_book(
                            target_symbol=target_symbol,
                            trading_symbol=trading_symbol,
                            algorithm_context=self
                        )
                    )

                return tickers

            return data_provider.provide_order_book(
                target_symbol=target_symbol,
                trading_symbol=trading_symbol,
                algorithm_context=self
            )

        if trading_data_type is None:

            if target_symbols is not None:
                raw_data = []

                for target_symbol in target_symbols:
                    raw_data.append(
                        data_provider.provide_raw_data(
                            target_symbol=target_symbol,
                            trading_symbol=trading_symbol,
                            algorithm_context=self
                        )
                    )

                return raw_data

            if target_symbol is not None:
                return data_provider.provide_raw_data(
                    target_symbol=target_symbol,
                    trading_symbol=trading_symbol,
                    algorithm_context=self
                )

            return data_provider.provide_raw_data(self)

    def get_unallocated_size(self, identifier):
        portfolio_manager = self.get_portfolio_manager(identifier)
        return portfolio_manager.unallocated

    def reset(self):
        self._workers = []
        self._running_workers = []
        self._data_providers = {}
        self._order_executors = {}
        self._portfolio_managers = {}
        self._market_services = {}
        self._initializer = None
        self._initialized = False
