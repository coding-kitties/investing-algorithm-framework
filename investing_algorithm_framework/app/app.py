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
from investing_algorithm_framework.app.web import create_flask_app
from investing_algorithm_framework.domain import DATABASE_NAME, TimeUnit, \
    DATABASE_DIRECTORY_PATH, RESOURCE_DIRECTORY, ENVIRONMENT, Environment, \
    SQLALCHEMY_DATABASE_URI, OperationalException, \
    BACKTESTING_START_DATE, BACKTESTING_END_DATE, BacktestReport, \
    BACKTESTING_PENDING_ORDER_CHECK_INTERVAL, APP_MODE, MarketCredential, \
    AppMode, BacktestDateRange, DATABASE_DIRECTORY_NAME, \
    BACKTESTING_INITIAL_AMOUNT, MarketDataSource
from investing_algorithm_framework.infrastructure import setup_sqlalchemy, \
    create_all_tables
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
        self._algorithm = Algorithm()

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
            # Override the portfolio service with the backtest
            # portfolio service
            self.container.portfolio_service.override(
                BacktestPortfolioService(
                    configuration_service=configuration_service,
                    market_credential_service=market_cred_service,
                    market_service=self.container.market_service(),
                    position_service=self.container.position_service(),
                    order_service=self.container.order_service(),
                    portfolio_repository=self.container.portfolio_repository(),
                    portfolio_configuration_service=portfolio_conf_service,
                    portfolio_snapshot_service=portfolio_snap_service
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
                    position_repository=self.container.position_repository(),
                    portfolio_repository=self.container.portfolio_repository(),
                    portfolio_configuration_service=portfolio_conf_service,
                    portfolio_snapshot_service=portfolio_snap_service,
                    configuration_service=configuration_service,
                    market_data_source_service=market_data_source_service
                )
            )

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

        # Initialize all portfolios that are registered
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_service = self.container.portfolio_service()

        # Throw an error if no portfolios are configured
        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        if Environment.BACKTEST.equals(config[ENVIRONMENT]):
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
            synced_portfolios = []

            for portfolio_configuration \
                    in portfolio_configuration_service.get_all():

                if not portfolio_service.exists(
                    {"identifier": portfolio_configuration.identifier}
                ):
                    portfolio = portfolio_service\
                        .create_portfolio_from_configuration(
                            portfolio_configuration
                        )

            portfolios = portfolio_service.get_all()

            for portfolio in portfolios:

                if portfolio not in synced_portfolios:
                    self.sync(portfolio)

    def sync(self, portfolio):
        """
        Sync the portfolio with the exchange. This method should be called
        before running the algorithm. It syncs the portfolio with the
        exchange by syncing the unallocated balance, positions, orders, and
        trades.

        Args:
            portfolio (Portfolio): The portfolio to sync

        Returns:
            None
        """
        logger.info(f"Syncing portfolio {portfolio.identifier}")
        portfolio_sync_service = self.container.portfolio_sync_service()

        # Sync unallocated balance
        portfolio_sync_service.sync_unallocated(portfolio)

        # Sync all orders from exchange with current order history
        portfolio_sync_service.sync_orders(portfolio)

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
                config = self.container.configuration_service().get_config()
                self._state_handler.load(config[RESOURCE_DIRECTORY])

            self.initialize()
            logger.info("Initialization complete")

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
        finally:
            self.algorithm.stop()

            # Upload state if state handler is provided
            if self._state_handler is not None:
                logger.info("Detected state handler, saving state")
                config = self.container.configuration_service().get_config()
                self._state_handler.save(config[RESOURCE_DIRECTORY])

    def reset(self):
        self._started = False
        self.algorithm.reset()

    def add_portfolio_configuration(self, portfolio_configuration):
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
        return self.algorithm.get_portfolio_configurations()

    def run_backtest(
        self,
        backtest_date_range: BacktestDateRange,
        initial_amount=None,
        pending_order_check_interval=None,
        output_directory=None,
        algorithm: Algorithm = None
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
            pending_order_check_interval: str - pending_order_check_interval:
              The interval at which to check pending orders (e.g. 1h, 1d, 1w)
            output_directory: str - The directory to
              write the backtest report to

        Returns:
            Instance of BacktestReport
        """
        if algorithm is not None:
            self.algorithm = algorithm

        if self.algorithm is None:
            raise OperationalException("No algorithm registered")

        # Add backtest configuration to the config
        self.set_config_with_dict({
            ENVIRONMENT: Environment.BACKTEST.value,
            BACKTESTING_START_DATE: backtest_date_range.start_date,
            BACKTESTING_END_DATE: backtest_date_range.end_date,
            DATABASE_NAME: "backtest-database.sqlite3",
            DATABASE_DIRECTORY_NAME: "backtest_databases",
            BACKTESTING_PENDING_ORDER_CHECK_INTERVAL: (
                pending_order_check_interval
            ),
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
        config = self.container.configuration_service().get_config()

        if output_directory is None:
            output_directory = os.path.join(
                config[RESOURCE_DIRECTORY], "backtest_reports"
            )

        backtest_service.write_report_to_json(
            report=report, output_directory=output_directory
        )
        return report

    def run_backtests(
        self,
        algorithms,
        initial_amount=None,
        date_ranges: List[BacktestDateRange] = None,
        pending_order_check_interval=None,
        output_directory=None,
        checkpoint=False
    ) -> List[BacktestReport]:
        """
        Run a backtest for a set algorithm. This method should be called when
        running a backtest.

        Args:
            Algorithms: List[Algorithm] - The algorithms to run backtests for
            date_ranges: List[BacktestDateRange] - The date ranges to run the
                backtests for
            initial_amount: The initial amount to start the backtest with.
            pending_order_check_interval: str - The interval at which to check
                pending orders
            output_directory: str - The directory to write the backtest
              report to.
            checkpoint: bool - Whether to checkpoint the backtest,
              If True, then it will be checked if for a given algorithm name
                and date range, a backtest report already exists. If it does,
                then the backtest will not be run again. This is useful
                when running backtests for a large number of algorithms
                and date ranges where some of the backtests may fail
                and you want to re-run only the failed backtests.

        Returns
            List of BacktestReport intances
        """
        logger.info("Initializing backtests")
        reports = []

        for date_range in date_ranges:
            date_range: BacktestDateRange = date_range
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
                    DATABASE_DIRECTORY_NAME: "backtest_databases",
                    BACKTESTING_PENDING_ORDER_CHECK_INTERVAL: (
                        pending_order_check_interval
                    )
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

                if output_directory is None:
                    output_directory = os.path.join(
                        self.config[RESOURCE_DIRECTORY], "backtest_reports"
                    )

                backtest_service.write_report_to_json(
                    report=report, output_directory=output_directory
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
        """
        if self.algorithm is None:
            self.algorithm = Algorithm(name=self._name)

        self.algorithm.add_strategy(strategy)
