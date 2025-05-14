import inspect
import logging
import os
import threading
from abc import abstractmethod
from time import sleep
from typing import List, Optional

from flask import Flask

from investing_algorithm_framework.app.algorithm import Algorithm
from investing_algorithm_framework.app.stateless import ActionHandler
from investing_algorithm_framework.app.task import Task
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.app.web import create_flask_app
from investing_algorithm_framework.domain import DATABASE_NAME, TimeUnit, \
    DATABASE_DIRECTORY_PATH, RESOURCE_DIRECTORY, ENVIRONMENT, Environment, \
    SQLALCHEMY_DATABASE_URI, OperationalException, StateHandler, \
    BACKTESTING_START_DATE, BACKTESTING_END_DATE, BacktestReport, \
    APP_MODE, MarketCredential, AppMode, BacktestDateRange, \
    DATABASE_DIRECTORY_NAME, BACKTESTING_INITIAL_AMOUNT, \
    MarketDataSource, APPLICATION_DIRECTORY, PortfolioConfiguration, \
    PortfolioProvider, OrderExecutor, ImproperlyConfigured
from investing_algorithm_framework.infrastructure import setup_sqlalchemy, \
    create_all_tables, CCXTOrderExecutor, CCXTPortfolioProvider
from investing_algorithm_framework.services import OrderBacktestService, \
    BacktestMarketDataSourceService, BacktestPortfolioService, \
    MarketDataSourceService, MarketCredentialService

logger = logging.getLogger("investing_algorithm_framework")
COLOR_RESET = '\033[0m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'


class AppHook:

    @abstractmethod
    def on_run(self, app, algorithm: Algorithm):
        raise NotImplementedError()


class App:

    def __init__(self, state_handler=None, name=None):
        self._flask_app: Optional[Flask] = None
        self.container = None
        self._started = False
        self._tasks = []
        self._configuration_service = None
        self._market_data_source_service: \
            Optional[MarketDataSourceService] = None
        self._market_data_sources = []
        self._market_credential_service: \
            Optional[MarketCredentialService] = None
        self._on_initialize_hooks = []
        self._on_after_initialize_hooks = []
        self._state_handler = state_handler
        self._name = name
        self._algorithm = Algorithm(name=self.name)

    @property
    def algorithm(self) -> Algorithm:
        return self._algorithm

    @property
    def context(self):
        return self.container.context()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def started(self):
        return self._started

    @property
    def config(self):
        """
        Function to get a config instance. This allows users when
        having access to the app instance also to read the
        configs of the app.
        """
        configuration_service = self.container.configuration_service()
        return configuration_service.config

    @config.setter
    def config(self, config: dict):
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

    @property
    def running(self):
        return self.algorithm.running

    def add_algorithm(self, algorithm: Algorithm) -> None:
        """
        Method to add an algorithm to the app. This method should be called
        before running the application.
        """
        self._algorithm = algorithm

    def set_config(self, key, value) -> None:
        configuration_service = self.container.configuration_service()
        configuration_service.add_value(key, value)

    def set_config_with_dict(self, dictionary) -> None:
        configuration_service = self.container.configuration_service()
        configuration_service.add_dict(dictionary)

    def initialize_services(self) -> None:
        self._configuration_service = self.container.configuration_service()
        self._configuration_service.initialize()
        self._market_data_source_service = \
            self.container.market_data_source_service()
        self._market_credential_service = \
            self.container.market_credential_service()

    @algorithm.setter
    def algorithm(self, algorithm: Algorithm) -> None:
        self._algorithm = algorithm

    def initialize_config(self):
        """
        Function to initialize the configuration for the app. This method
        should be called before running the algorithm.
        """
        logger.info("Initializing configuration")
        configuration_service = self.container.configuration_service()
        config = configuration_service.get_config()

        # Check if the resource directory is set
        if RESOURCE_DIRECTORY not in config \
                or config[RESOURCE_DIRECTORY] is None:
            logger.info(
                "Resource directory not set, setting" +
                " to current working directory"
            )
            path = os.path.join(os.getcwd(), "resources")
            configuration_service.add_value(RESOURCE_DIRECTORY, path)

        config = configuration_service.get_config()
        logger.info(f"Resource directory set to {config[RESOURCE_DIRECTORY]}")

        if DATABASE_NAME not in config or config[DATABASE_NAME] is None:
            configuration_service.add_value(
                DATABASE_NAME, "prod-database.sqlite3"
            )

        # Set the database directory name
        if Environment.BACKTEST.equals(config[ENVIRONMENT]):
            configuration_service.add_value(
                DATABASE_DIRECTORY_NAME, "backtest_databases"
            )
            configuration_service.add_value(
                DATABASE_NAME, "backtest-database.sqlite3"
            )
        else:
            configuration_service.add_value(
                DATABASE_DIRECTORY_NAME, "databases"
            )

            if Environment.TEST.equals(config[ENVIRONMENT]):
                configuration_service.add_value(
                    DATABASE_NAME, "test-database.sqlite3"
                )
            elif Environment.PROD.equals(config[ENVIRONMENT]):
                configuration_service.add_value(
                    DATABASE_NAME, "prod-database.sqlite3"
                )
            else:
                configuration_service.add_value(
                    DATABASE_NAME, "dev-database.sqlite3"
                )

        config = configuration_service.get_config()
        resource_dir = config[RESOURCE_DIRECTORY]
        database_dir_name = config.get(DATABASE_DIRECTORY_NAME)
        configuration_service.add_value(
            DATABASE_DIRECTORY_PATH,
            os.path.join(resource_dir, database_dir_name)
        )
        config = configuration_service.get_config()

        if SQLALCHEMY_DATABASE_URI not in config \
                or config[SQLALCHEMY_DATABASE_URI] is None:
            path = "sqlite:///" + os.path.join(
                configuration_service.config[DATABASE_DIRECTORY_PATH],
                configuration_service.config[DATABASE_NAME]
            )
            configuration_service.add_value(SQLALCHEMY_DATABASE_URI, path)

        config = configuration_service.get_config()

        if APP_MODE not in config:
            configuration_service.add_value(APP_MODE, AppMode.DEFAULT.value)

    def initialize(self):
        """
        Method to initialize the app. This method should be called before
        running the algorithm. It initializes the services and the algorithm
        and sets up the database if it does not exist.

        Also, it initializes all required services for the algorithm.

        Returns:
            None
        """
        logger.info("Initializing app")
        self._initialize_default_order_executors()
        self._initialize_default_portfolio_providers()

        if self.algorithm is None:
            raise OperationalException("No algorithm registered")

        # Check if the algorithm has data sources registered
        if len(self.algorithm.data_sources) == 0:

            for data_source in self.algorithm.data_sources:
                self.add_market_data_source(data_source)

        # Ensure that all resource directories exist
        self._create_resources_if_not_exists()

        # Setup the database
        setup_sqlalchemy(self)
        create_all_tables()

        # Check if environment is in backtest mode
        config = self.container.configuration_service().get_config()

        # Initialize services in backtest
        if Environment.BACKTEST.equals(config[ENVIRONMENT]):

            configuration_service = self.container.configuration_service()
            portfolio_conf_service = self.container \
                .portfolio_configuration_service()
            portfolio_snap_service = self.container \
                .portfolio_snapshot_service()
            market_cred_service = self.container.market_credential_service()
            portfolio_provider_lookup = \
                self.container.portfolio_provider_lookup()
            # Override the portfolio service with the backtest
            # portfolio service
            self.container.portfolio_service.override(
                BacktestPortfolioService(
                    configuration_service=configuration_service,
                    market_credential_service=market_cred_service,
                    position_service=self.container.position_service(),
                    order_service=self.container.order_service(),
                    portfolio_repository=self.container.portfolio_repository(),
                    portfolio_configuration_service=portfolio_conf_service,
                    portfolio_snapshot_service=portfolio_snap_service,
                    portfolio_provider_lookup=portfolio_provider_lookup
                )
            )

            # Get all current market data sources
            market_data_sources = self._market_data_source_service \
                .get_market_data_sources()

            # Override the market data source service with the backtest market
            # data source service
            self.container.market_data_source_service.override(
                BacktestMarketDataSourceService(
                    market_service=self.container.market_service(),
                    market_credential_service=self.container
                    .market_credential_service(),
                    configuration_service=self.container
                    .configuration_service(),
                    market_data_sources=market_data_sources
                )
            )

            portfolio_conf_service = self.container.\
                portfolio_configuration_service()
            portfolio_snap_service = self.container.\
                portfolio_snapshot_service()
            configuration_service = self.container.configuration_service()
            market_data_source_service = self.container.\
                market_data_source_service()
            # Override the order service with the backtest order service
            self.container.order_service.override(
                OrderBacktestService(
                    trade_service=self.container.trade_service(),
                    order_repository=self.container.order_repository(),
                    position_service=self.container.position_service(),
                    portfolio_repository=self.container.portfolio_repository(),
                    portfolio_configuration_service=portfolio_conf_service,
                    portfolio_snapshot_service=portfolio_snap_service,
                    configuration_service=configuration_service,
                    market_data_source_service=market_data_source_service
                )
            )
        else:
            # Initialize all market credentials
            self._market_credential_service = self.container.\
                market_credential_service()
            self._market_credential_service.initialize()

        # Add all market data sources of the strategies to the market data
        # source service
        self._market_data_source_service = self.container.\
            market_data_source_service()
        self._market_data_source_service.market_data_sources = \
            self._market_data_sources

        for strategy in self.algorithm.strategies:

            if strategy.market_data_sources is not None:
                for market_data_source in strategy.market_data_sources:
                    self._market_data_source_service.add(market_data_source)

        # Initialize the market data source service
        self._market_data_source_service.initialize_market_data_sources()

        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()

        # Re-init the market service because the portfolio configuration
        # service is a singleton
        portfolio_configuration_service.market_service \
            = self.container.market_service()

        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        self.algorithm.initialize_services(
            context=self.container.context(),
            configuration_service=self.container.configuration_service(),
            market_data_source_service=self._market_data_source_service,
            market_credential_service=self.container
            .market_credential_service(),
            portfolio_service=self.container.portfolio_service(),
            position_service=self.container.position_service(),
            order_service=self.container.order_service(),
            portfolio_configuration_service=self.container
            .portfolio_configuration_service(),
            market_service=self.container.market_service(),
            strategy_orchestrator_service=self.container
            .strategy_orchestrator_service(),
            trade_service=self.container.trade_service(),
        )

        config = self.container.configuration_service().get_config()

        if config[APP_MODE] == AppMode.WEB.value:
            self._configuration_service.add_value(
                APP_MODE, AppMode.WEB.value
            )
            self._initialize_web()

        self._initialize_portfolios()

    def run(
        self,
        payload: dict = None,
        number_of_iterations: int = None,
    ):
        """
        Entry point to run the application. This method should be called to
        start the algorithm. This method can be called in three modes:

        - Without any params: In this mode, the app runs until a keyboard
        interrupt is received. This mode is useful when running the app in
        a loop.
        - With a payload: In this mode, the app runs only once with the
        payload provided. This mode is useful when running the app in a
        one-off mode, such as running the app from the command line or
        on a schedule. Payload is a dictionary that contains the data to
        handle for the algorithm. This data should look like this:
        {
            "action": "RUN_STRATEGY",
        }
        - With a number of iterations: In this mode, the app runs for the
        number of iterations provided. This mode is useful when running the
        app in a loop for a fixed number of iterations.

        This function first checks if there is an algorithm registered.
         If not, it raises an OperationalException. Then it
         initializes the algorithm with the services and the configuration.

        Args:
            payload (dict): The payload to handle for the algorithm
            number_of_iterations (int): The number of iterations to run the
            algorithm for

        Returns:
            None
        """
        try:
            configuration_service = self.container.configuration_service()
            config = configuration_service.get_config()

            # Run method should never be called with environment set to
            # backtest, if it is, then set the environment to prod
            if config[ENVIRONMENT] == Environment.BACKTEST.value:
                configuration_service.add_value(
                    ENVIRONMENT, Environment.PROD.value
                )

            self.initialize_config()

            # Load the state if a state handler is provided
            if self._state_handler is not None:
                logger.info("Detected state handler, loading state")
                self._state_handler.initialize()
                config = self.container.configuration_service().get_config()
                self._state_handler.load(config[RESOURCE_DIRECTORY])

            self.initialize()
            logger.info("App initialization complete")

            # Run all on_initialize hooks
            for hook in self._on_initialize_hooks:
                hook.on_run(self, self.algorithm)

            configuration_service = self.container.configuration_service()
            config = configuration_service.get_config()

            # Run in payload mode if payload is provided
            if payload is not None:
                logger.info("Running with payload")
                action_handler = ActionHandler.of(payload)
                response = action_handler.handle(
                    payload=payload, algorithm=self.algorithm
                )
                return response

            if AppMode.WEB.equals(config[APP_MODE]):
                logger.info("Running web")
                flask_thread = threading.Thread(
                    name='Web App',
                    target=self._flask_app.run,
                    kwargs={"port": 8080}
                )
                flask_thread.daemon = True
                flask_thread.start()

            self.algorithm.start(number_of_iterations=number_of_iterations)
            number_of_iterations_since_last_orders_check = 1

            try:
                while self.algorithm.running:
                    if number_of_iterations_since_last_orders_check == 30:
                        logger.info("Checking pending orders")
                        number_of_iterations_since_last_orders_check = 1

                    self.algorithm.run_jobs(context=self.container.context())
                    number_of_iterations_since_last_orders_check += 1
                    sleep(1)
            except KeyboardInterrupt:
                exit(0)
        except Exception as e:
            logger.error(e)
            raise e
        finally:

            try:
                self.algorithm.stop()

                # Upload state if state handler is provided
                if self._state_handler is not None:
                    logger.info("Detected state handler, saving state")
                    config = \
                        self.container.configuration_service().get_config()
                    self._state_handler.save(config[RESOURCE_DIRECTORY])
            except Exception as e:
                logger.error(e)

    def reset(self):
        self._started = False
        self.algorithm.reset()

    def add_portfolio_configuration(self, portfolio_configuration):
        """
        Function to add a portfolio configuration to the app. The portfolio
        configuration should be an instance of PortfolioConfiguration.

        Args:
            portfolio_configuration: Instance of PortfolioConfiguration

        Returns:
            None
        """
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_configuration_service.add(portfolio_configuration)

    def task(
        self,
        function=None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10,
    ):
        if function:
            task = Task(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
            )
            self.algorithm.add_task(task)
        else:
            def wrapper(f):
                self.algorithm.add_task(
                    Task(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval
                    )
                )
                return f

            return wrapper

    def _initialize_web(self):
        """
        Initialize the app for web mode by setting the configuration
        parameters for web mode and overriding the services with the
        web services equivalents.

        Web has the following implications:
        - db
            - sqlite
        - services
            - Flask app
            - Investing Algorithm Framework App
            - Algorithm
        """
        configuration_service = self.container.configuration_service()
        self._flask_app = create_flask_app(configuration_service)

    def _create_resources_if_not_exists(self):
        """
        Function to create the resources required by the app if they
          do not exist. This function will check if the resource directory
          exists and check if the database directory exists. If they do
          not exist, it will create them.

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        config = configuration_service.get_config()
        resource_dir = config[RESOURCE_DIRECTORY]
        database_dir = config[DATABASE_DIRECTORY_PATH]

        if resource_dir is None:
            raise OperationalException(
                "Resource directory is not specified in the config, please "
                "specify the resource directory in the config with the key "
                "RESOURCE_DIRECTORY"
            )

        if not os.path.isdir(resource_dir):
            try:
                os.makedirs(resource_dir)
            except OSError as e:
                logger.error(e)
                raise OperationalException(
                    "Could not create resource directory"
                )

        if not os.path.isdir(database_dir):
            try:
                os.makedirs(database_dir)
            except OSError as e:
                logger.error(e)
                raise OperationalException(
                    "Could not create database directory"
                )

    def get_portfolio_configurations(self):
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        return portfolio_configuration_service.get_all()

    def get_market_credentials(self):
        """
        Function to get all market credentials from the app. This method
        should be called when you want to get all market credentials.

        Returns:
            List of MarketCredential instances
        """
        market_credential_service = self.container \
            .market_credential_service()
        return market_credential_service.get_all()

    def run_backtest(
        self,
        backtest_date_range: BacktestDateRange,
        initial_amount=None,
        output_directory=None,
        algorithm: Algorithm = None,
        save_strategy=False,
        save_in_memory_strategies: bool = False,
        strategy_directory: str = None
    ) -> BacktestReport:
        """
        Run a backtest for an algorithm. This method should be called when
        running a backtest.

        Args:
            backtest_date_range: The date range to run the backtest for
                (instance of BacktestDateRange)
            initial_amount: The initial amount to start the backtest with.
                This will be the amount of trading currency that the backtest
                portfolio will start with.
            algorithm: The algorithm to run a backtest for (instance of
                Algorithm)
            output_directory: str - The directory to
              write the backtest report to
            save_strategy: bool - Whether to save the strategy
            save_strategies_directory: bool - Whether to save the
                strategies directory
            strategies_directory_name: str - The name of the directory
                that contains the strategies

        Returns:
            Instance of BacktestReport
        """
        if algorithm is not None:
            self.algorithm = algorithm

        if self.algorithm is None:
            raise OperationalException("No algorithm registered")

        if save_strategy:
            # Check if the strategies directory exists
            if not save_in_memory_strategies:

                if strategy_directory is None:
                    strategy_directory = os.path.join(
                        self.config[APPLICATION_DIRECTORY], "strategies"
                    )
                else:
                    strategy_directory = os.path.join(
                        self.config[APPLICATION_DIRECTORY], strategy_directory
                    )

                if not os.path.isdir(strategy_directory):
                    raise OperationalException(
                        "The backtest run is enabled with the "
                        "`include_strategy` flag  but the strategies"
                        " directory: "
                        f"{strategy_directory} does not exist. "
                        "Please create the strategies directory or set "
                        "include_strategy to False. If you want to save the "
                        "strategies in memory, set save_in_memory_strategies "
                        "to True. This can be helpfull when running your "
                        "strategies in a notebook environment."
                    )

        # Add backtest configuration to the config
        self.set_config_with_dict({
            ENVIRONMENT: Environment.BACKTEST.value,
            BACKTESTING_START_DATE: backtest_date_range.start_date,
            BACKTESTING_END_DATE: backtest_date_range.end_date,
            DATABASE_NAME: "backtest-database.sqlite3",
            DATABASE_DIRECTORY_NAME: "backtest_databases",
            BACKTESTING_INITIAL_AMOUNT: initial_amount
        })

        self.initialize_config()
        config = self._configuration_service.get_config()
        path = os.path.join(
            config[DATABASE_DIRECTORY_PATH],
            config[DATABASE_NAME]
        )
        # Remove the previous backtest db
        if os.path.exists(path):
            os.remove(path)

        self.initialize()

        backtest_service = self.container.backtest_service()

        # Run the backtest with the backtest_service and collect the report
        report = backtest_service.run_backtest(
            algorithm=self.algorithm,
            initial_amount=initial_amount,
            backtest_date_range=backtest_date_range
        )

        backtest_service.save_report(
            report=report,
            algorithm=self.algorithm,
            output_directory=output_directory,
            save_strategy=save_strategy,
            save_in_memory_strategies=save_in_memory_strategies,
            strategy_directory=strategy_directory
        )
        return report

    def run_backtests(
        self,
        algorithms,
        initial_amount=None,
        backtest_date_ranges: List[BacktestDateRange] = None,
        output_directory=None,
        checkpoint=False,
        save_strategy=False,
    ) -> List[BacktestReport]:
        """
        Run a backtest for a set algorithm. This method should be called when
        running a backtest.

        Args:
            Algorithms: List[Algorithm] - The algorithms to run backtests for
            backtest_date_ranges: List[BacktestDateRange] - The date ranges
                to run the backtests for
            initial_amount: The initial amount to start the backtest with.
            output_directory: str - The directory to write the backtest
              report to.
            checkpoint: bool - Whether to checkpoint the backtest,
              If True, then it will be checked if for a given algorithm name
                and date range, a backtest report already exists. If it does,
                then the backtest will not be run again. This is useful
                when running backtests for a large number of algorithms
                and date ranges where some of the backtests may fail
                and you want to re-run only the failed backtests.
            save_strategy: bool - Whether to save the strategy as part
                of the backtest report. You can only save in-memory strategies
                when running multiple backtests. This is because we can't
                differentiate between which folders belong to a specific
                strategy.

        Returns
            List of BacktestReport intances
        """
        logger.info("Initializing backtests")
        reports = []

        for date_range in backtest_date_ranges:
            print(
                f"{COLOR_YELLOW}Running backtests for date "
                f"range:{COLOR_RESET} {COLOR_GREEN}{date_range.name} "
                f"{date_range.start_date} - "
                f"{date_range.end_date} for a "
                f"total of {len(algorithms)} algorithms.{COLOR_RESET}"
            )

            for algorithm in algorithms:

                if checkpoint:
                    backtest_service = self.container.backtest_service()
                    report = backtest_service.get_report(
                        algorithm_name=algorithm.name,
                        backtest_date_range=date_range,
                        directory=output_directory
                    )

                    if report is not None:

                        print(
                            f"{COLOR_YELLOW}Backtest already exists "
                            f"for algorithm {algorithm.name} date "
                            f"range:{COLOR_RESET} {COLOR_GREEN} "
                            f"{date_range.name} "
                            f"{date_range.start_date} - "
                            f"{date_range.end_date}"
                        )
                        reports.append(report)
                        continue
                self.algorithm = algorithm
                self.set_config_with_dict({
                    ENVIRONMENT: Environment.BACKTEST.value,
                    BACKTESTING_START_DATE: date_range.start_date,
                    BACKTESTING_END_DATE: date_range.end_date,
                    DATABASE_NAME: "backtest-database.sqlite3",
                    DATABASE_DIRECTORY_NAME: "backtest_databases"
                })
                self.initialize_config()

                config = self._configuration_service.get_config()

                path = os.path.join(
                    config[DATABASE_DIRECTORY_PATH],
                    config[DATABASE_NAME]
                )
                # Remove the previous backtest db
                if os.path.exists(path):
                    os.remove(path)

                self.initialize()
                backtest_service = self.container.backtest_service()
                backtest_service.resource_directory = self.config[
                    RESOURCE_DIRECTORY
                ]

                # Run the backtest with the backtest_service
                # and collect the report
                report = backtest_service.run_backtest(
                    algorithm=self.algorithm,
                    initial_amount=initial_amount,
                    backtest_date_range=date_range
                )

                # Add date range name to report if present
                if date_range.name is not None:
                    report.date_range_name = date_range.name

                backtest_service.save_report(
                    report=report,
                    algorithm=algorithm,
                    output_directory=output_directory,
                    save_strategy=save_strategy,
                    save_in_memory_strategies=True,
                )
                reports.append(report)

        return reports

    def add_market_data_source(self, market_data_source):
        """
        Function to add a market data source to the app. The market data
        source should be an instance of MarketDataSource.

        This is a seperate function from the market data source service. This
        is because the market data source service can be re-initialized.
        Therefore we need a persistent list of market data sources in the app.

        Args:
            market_data_source: Instance of MarketDataSource

        Returns:
            None
        """

        # Check if the market data source is an instance of MarketDataSource
        if not isinstance(market_data_source, MarketDataSource):
            return

        # Check if there is already a market data source with the same
        # identifier
        for existing_market_data_source in self._market_data_sources:
            if existing_market_data_source.get_identifier() == \
                    market_data_source.get_identifier():
                return

        market_data_source.market_credential_service = \
            self._market_credential_service
        self._market_data_sources.append(market_data_source)

    def add_market_credential(self, market_credential: MarketCredential):
        market_credential.market = market_credential.market.upper()
        self._market_credential_service.add(market_credential)

    def on_initialize(self, app_hook: AppHook):
        """
        Function to add a hook that runs when the app is initialized. The hook
        should be an instance of AppHook.
        """

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_initialize_hooks.append(app_hook)

    def after_initialize(self, app_hook: AppHook):
        """
        Function to add a hook that runs after the app is initialized.
        The hook should be an instance of AppHook.
        """

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_after_initialize_hooks.append(app_hook)

    def add_strategy(self, strategy):
        """
        Function to add a strategy to the app. The strategy should be an
        instance of TradingStrategy.

        Args:
            strategy: Instance of TradingStrategy

        Returns:
            None
        """

        if inspect.isclass(strategy):
            strategy = strategy()

        if not isinstance(strategy, TradingStrategy):
            raise OperationalException(
                "Strategy should be an instance of TradingStrategy"
            )

        if self.algorithm is None:
            self.algorithm = Algorithm(name=self._name)

        self.algorithm.add_strategy(strategy)

    def add_state_handler(self, state_handler):
        """
        Function to add a state handler to the app. The state handler should
        be an instance of StateHandler.

        Args:
            state_handler: Instance of StateHandler

        Returns:
            None
        """

        if inspect.isclass(state_handler):
            state_handler = state_handler()

        if not isinstance(state_handler, StateHandler):
            raise OperationalException(
                "State handler should be an instance of StateHandler"
            )

        self._state_handler = state_handler

    def add_market(
        self,
        market,
        trading_symbol,
        api_key=None,
        secret_key=None,
        initial_balance=None
    ):
        """
        Function to add a market to the app. This function is a utility
        function to add a portfolio configuration and market credential
        to the app.

        Args:
            market: String representing the market name
            trading_symbol: Trading symbol for the portfolio
            api_key: API key for the market
            secret_key: Secret key for the market
            initial_balance: Initial balance for the market

        Returns:
            None
        """

        portfolio_configuration = PortfolioConfiguration(
            market=market,
            trading_symbol=trading_symbol,
            initial_balance=initial_balance
        )

        self.add_portfolio_configuration(portfolio_configuration)
        market_credential = MarketCredential(
            market=market,
            api_key=api_key,
            secret_key=secret_key
        )
        self.add_market_credential(market_credential)

    def add_order_executor(self, order_executor):
        """
        Function to add an order executor to the app. The order executor
        should be an instance of OrderExecutor.

        Args:
            order_executor: Instance of OrderExecutor

        Returns:
            None
        """

        if inspect.isclass(order_executor):
            order_executor = order_executor()

        if not isinstance(order_executor, OrderExecutor):
            raise OperationalException(
                "Order executor should be an instance of OrderExecutor"
            )

        order_executor_lookup = self.container.order_executor_lookup()
        order_executor_lookup.add_order_executor(
            order_executor=order_executor
        )

    def get_order_executors(self):
        """
        Function to get all order executors from the app. This method
        should be called when you want to get all order executors.

        Returns:
            List of OrderExecutor instances
        """
        order_executor_lookup = self.container.order_executor_lookup()
        return order_executor_lookup.get_all()

    def add_portfolio_provider(self, portfolio_provider):
        """
        Function to add a portfolio provider to the app. The portfolio
        provider should be an instance of PortfolioProvider.

        Args:
            portfolio_provider: Instance of PortfolioProvider

        Returns:
            None
        """

        if inspect.isclass(portfolio_provider):
            portfolio_provider = portfolio_provider()

        if not isinstance(portfolio_provider, PortfolioProvider):
            raise OperationalException(
                "Portfolio provider should be an instance of "
                "PortfolioProvider"
            )

        portfolio_provider_lookup = self.container.portfolio_provider_lookup()
        portfolio_provider_lookup.add_portfolio_provider(
            portfolio_provider=portfolio_provider
        )

    def get_portfolio_providers(self):
        """
        Function to get all portfolio providers from the app. This method
        should be called when you want to get all portfolio providers.

        Returns:
            List of PortfolioProvider instances
        """
        portfolio_provider_lookup = self.container.portfolio_provider_lookup()
        return portfolio_provider_lookup.get_all()

    def _initialize_portfolios(self):
        """
        Function to initialize the portfolios. This function will
        first check if the app is running in backtest mode or not. If it is
        running in backtest mode, it will create the portfolios with the
        initial amount specified in the config. If it is not running in
        backtest mode, it will check if there are

        """
        logger.info("Initializing portfolios")
        config = self.config

        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_service = self.container.portfolio_service()

        # Throw an error if no portfolios are configured
        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        if Environment.BACKTEST.equals(config[ENVIRONMENT]):
            logger.info("Setting up backtest portfolios")
            initial_backtest_amount = config.get(
                BACKTESTING_INITIAL_AMOUNT, None
            )

            for portfolio_configuration \
                    in portfolio_configuration_service.get_all():

                if not portfolio_service.exists(
                    {"identifier": portfolio_configuration.identifier}
                ):
                    portfolio = (
                        portfolio_service.create_portfolio_from_configuration(
                            portfolio_configuration,
                            initial_amount=initial_backtest_amount,
                        )
                    )
        else:
            # Check if there are already existing portfolios
            portfolios = portfolio_service.get_all()
            portfolio_configurations = portfolio_configuration_service\
                .get_all()

            if len(portfolios) > 0:

                # Check if there are matching portfolio configurations
                for portfolio in portfolios:
                    logger.info(
                        f"Checking if there is an matching portfolio "
                        "configuration "
                        f"for portfolio {portfolio.identifier}"
                    )
                    portfolio_configuration = \
                        portfolio_configuration_service.get(
                            portfolio.market
                        )

                    if portfolio_configuration is None:
                        raise ImproperlyConfigured(
                            f"No matching portfolio configuration found for "
                            f"existing portfolio {portfolio.market}, "
                            f"please make sure that you have configured your "
                            f"app with the right portfolio configurations "
                            f"for the existing portfolios."
                            f"If you want to create a new portfolio, please "
                            f"remove the existing database (WARNING!!: this "
                            f"will remove all existing history of your "
                            f"trading bot.)"
                        )

                    # Check if the portfolio configuration is still inline
                    # with the initial balance

                    if portfolio_configuration.initial_balance != \
                            portfolio.initial_balance:
                        logger.warning(
                            "The initial balance of the portfolio "
                            "configuration is different from the existing "
                            "portfolio. Checking if the existing portfolio "
                            "can be updated..."
                        )

                        portfolio_provider_lookup = \
                            self.container.portfolio_provider_lookup()
                        # Register a portfolio provider for the portfolio
                        portfolio_provider_lookup \
                            .register_portfolio_provider_for_market(
                                portfolio_configuration.market
                            )
                        initial_balance = portfolio_configuration\
                            .initial_balance

                        if initial_balance != portfolio.initial_balance:
                            raise ImproperlyConfigured(
                                "The initial balance of the portfolio "
                                "configuration is different then that of "
                                "the existing portfolio. Please make sure "
                                "that the initial balance of the portfolio "
                                "configuration is the same as that of the "
                                "existing portfolio. "
                                f"Existing portfolio initial balance: "
                                f"{portfolio.initial_balance}, "
                                f"Portfolio configuration initial balance: "
                                f"{portfolio_configuration.initial_balance}"
                                "If this is intentional, please remove "
                                "the database and re-run the app. "
                                "WARNING!!: this will remove all existing "
                                "history of your trading bot."
                            )

            portfolio_provider_lookup = \
                self.container.portfolio_provider_lookup()
            order_executor_lookup = self.container.order_executor_lookup()

            # Register portfolio providers and order executors
            for portfolio_configuration in portfolio_configurations:

                # Register a portfolio provider for the portfolio
                portfolio_provider_lookup\
                    .register_portfolio_provider_for_market(
                        portfolio_configuration.market
                    )

                # Register an order executor for the portfolio
                order_executor_lookup.register_order_executor_for_market(
                    portfolio_configuration.market
                )

                market_credential = \
                    self._market_credential_service.get(
                        portfolio_configuration.market
                    )

                if market_credential is None:
                    raise ImproperlyConfigured(
                        f"No market credential found for existing "
                        f"portfolio {portfolio_configuration.market} "
                        "with market "
                        "Cannot initialize portfolio configuration."
                    )

                if not portfolio_service.exists(
                    {"identifier": portfolio_configuration.identifier}
                ):
                    portfolio_service.create_portfolio_from_configuration(
                        portfolio_configuration
                    )

            logger.info("Portfolio configurations complete")
            logger.info("Syncing portfolios")
            portfolio_service = self.container.portfolio_service()
            portfolio_sync_service = self.container.portfolio_sync_service()

            for portfolio in portfolio_service.get_all():
                logger.info(f"Syncing portfolio {portfolio.identifier}")
                portfolio_sync_service.sync_unallocated(portfolio)
                portfolio_sync_service.sync_orders(portfolio)

    def _initialize_default_portfolio_providers(self):
        """
        Function to initialize the default portfolio providers.
        This function will create a default portfolio provider for
        each market that is configured in the app. The default portfolio
        provider will be used to create portfolios for the app.

        Returns:
            None
        """
        logger.info("Adding default portfolio providers")
        portfolio_provider_lookup = self.container.portfolio_provider_lookup()
        portfolio_provider_lookup.add_portfolio_provider(
            CCXTPortfolioProvider()
        )

    def _initialize_default_order_executors(self):
        """
        Function to initialize the default order executors.
        This function will create a default order executor for
        each market that is configured in the app. The default order
        executor will be used to create orders for the app.

        Returns:
            None
        """
        logger.info("Adding default order executors")
        order_executor_lookup = self.container.order_executor_lookup()
        order_executor_lookup.add_order_executor(
            CCXTOrderExecutor()
        )
