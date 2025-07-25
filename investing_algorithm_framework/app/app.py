import inspect
import logging
import os
import threading
from typing import List, Optional, Any, Dict

from flask import Flask

from investing_algorithm_framework.app.algorithm import Algorithm, \
    AlgorithmFactory
from investing_algorithm_framework.app.stateless import ActionHandler
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.app.task import Task
from investing_algorithm_framework.app.web import create_flask_app
from investing_algorithm_framework.domain import DATABASE_NAME, TimeUnit, \
    DATABASE_DIRECTORY_PATH, RESOURCE_DIRECTORY, ENVIRONMENT, Environment, \
    SQLALCHEMY_DATABASE_URI, OperationalException, StateHandler, \
    BACKTESTING_START_DATE, BACKTESTING_END_DATE, APP_MODE, MarketCredential, \
    AppMode, BacktestDateRange, DATABASE_DIRECTORY_NAME, \
    BACKTESTING_INITIAL_AMOUNT, SNAPSHOT_INTERVAL, Backtest, \
    MarketDataSource, PortfolioConfiguration, SnapshotInterval, \
    PortfolioProvider, OrderExecutor, ImproperlyConfigured, \
    BACKTESTING_INDEX_DATETIME, DataProvider, INDEX_DATETIME, \
    BACKTESTING_LAST_SNAPSHOT_DATETIME
from investing_algorithm_framework.infrastructure import setup_sqlalchemy, \
    create_all_tables, CCXTOrderExecutor, CCXTPortfolioProvider, \
    BacktestOrderExecutor, CCXTOHLCVDataProvider
from investing_algorithm_framework.services import OrderBacktestService, \
    BacktestPortfolioService, BacktestTradeOrderEvaluator, \
    DefaultTradeOrderEvaluator
from .app_hook import AppHook
from .eventloop import EventLoopService

logger = logging.getLogger("investing_algorithm_framework")
COLOR_RESET = '\033[0m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'


class App:
    """
    Class to represent the app. This class is used to initialize the
    application and run your trading bot.

    Attributes:
        container: The dependency container for the app. This is used
            to store all the services and repositories for the app.
        algorithm: The algorithm to run. This is used to run the
            trading bot.
        _flask_app: The flask app instance. This is used to run the
            web app.
        _state_handler: The state handler for the app. This is used
            to save and load the state of the app.
        _name: The name of the app. This is used to identify the app
            in logs and other places.
        _started: A boolean value that indicates if the app has been
            started or not.
        _tasks (List[Task]): List of task that need to be run by the
            application.
    """

    def __init__(self, state_handler=None, name=None):
        self._flask_app: Optional[Flask] = None
        self.container = None
        self._started = False
        self._tasks = []
        self._strategies = []
        self._data_providers = []
        self._on_initialize_hooks = []
        self._on_strategy_run_hooks = []
        self._on_after_initialize_hooks = []
        self._trade_order_evaluator = None
        self._state_handler = state_handler
        self._run_history = None
        self._name = name

    @property
    def context(self):
        return self.container.context()

    @property
    def resource_directory_path(self):
        """
        Returns the resource directory path from the configuration.
        This directory is used to store resources such as market data,
        database files, and other resources required by the app.
        """
        config = self.config
        resource_directory_path = config.get(RESOURCE_DIRECTORY, None)

        # Check if the resource directory is set
        if resource_directory_path is None:
            logger.info(
                "Resource directory not set, setting" +
                " to current working directory"
            )
            resource_directory_path = os.path.join(os.getcwd(), "resources")
            configuration_service = self.container.configuration_service()
            configuration_service.add_value(
                RESOURCE_DIRECTORY, resource_directory_path
            )

        return resource_directory_path

    @property
    def database_directory_path(self):
        """
        Returns the database directory path from the configuration.
        This directory is used to store database files required by the app.
        """
        config = self.config
        database_directory_path = config.get(DATABASE_DIRECTORY_PATH, None)

        # Check if the database directory is set
        if database_directory_path is None:
            logger.info(
                "Database directory not set, setting" +
                " to current working directory"
            )
            resource_directory_path = self.resource_directory_path
            database_directory_path = os.path.join(
                resource_directory_path, "databases"
            )
            configuration_service = self.container.configuration_service()
            configuration_service.add_value(
                DATABASE_DIRECTORY_PATH, database_directory_path
            )

        return database_directory_path

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
        """
        Function to set the configuration for the app.
        Args:
            config (dict): A dictionary containing the configuration

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

    def add_algorithm(self, algorithm: Algorithm) -> None:
        """
        Method to add an algorithm to the app. This method should be called
        before running the application.

        When adding an algorithm, it will automatically register all
        strategies, data sources, and tasks of the algorithm. The
        algorithm itself is not registered.

        Args:
            algorithm (Algorithm): The algorithm to add to the app.
                This should be an instance of Algorithm.

        Returns:
            None
        """
        self.add_strategies(algorithm.strategies)
        self.add_data_sources(algorithm.data_sources)
        self.add_tasks(algorithm.tasks)

    def add_trade_order_evaluator(self, trade_order_evaluator):
        """
        Function to add a trade order evaluator to the app. This is used
        to evaluate trades and orders based on OHLCV data.

        Args:
            trade_order_evaluator: The trade order evaluator to add to the app.
                This should be an instance of TradeOrderEvaluator.

        Returns:
            None
        """
        self._trade_order_evaluator = trade_order_evaluator

    def set_config(self, key: str, value: Any) -> None:
        """
        Function to add a key-value pair to the app's configuration.

        Args:
            key (string): The key to add to the configuration
            value (any): The value to add to the configuration

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        configuration_service.add_value(key, value)

    def set_config_with_dict(self, config: dict) -> None:
        """
        Function to set the configuration for the app with a dictionary.
        This is useful for setting multiple configuration values at once.

        Args:
            config (dict): A dictionary containing the configuration

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

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

    def initialize_backtest_config(
        self,
        backtest_date_range: BacktestDateRange,
        initial_amount=None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY
    ):
        """
        Function to initialize the configuration for the app in backtest mode.
        This method should be called before running the algorithm in backtest
        mode. It sets the environment to BACKTEST and initializes the
        configuration accordingly.

        Args:
            backtest_date_range (BacktestDateRange): The date range for the
                backtest. This should be an instance of BacktestDateRange.
            initial_amount (float): The initial amount to start the backtest
                with. This will be the amount of trading currency that the
                backtest portfolio will start with.
            snapshot_interval (SnapshotInterval): The snapshot interval to
                use for the backtest. This is used to determine how often the
                portfolio snapshot should be taken during the backtest.

        Returns:
            None
        """
        logger.info("Initializing backtest configuration")
        data = {
            ENVIRONMENT: Environment.BACKTEST.value,
            BACKTESTING_START_DATE: backtest_date_range.start_date,
            BACKTESTING_END_DATE: backtest_date_range.end_date,
            DATABASE_NAME: "backtest-database.sqlite3",
            DATABASE_DIRECTORY_NAME: "backtest_databases",
            BACKTESTING_INITIAL_AMOUNT: initial_amount,
            SNAPSHOT_INTERVAL: SnapshotInterval.from_value(
                snapshot_interval
            ).value,
            INDEX_DATETIME: backtest_date_range.start_date,
            BACKTESTING_INDEX_DATETIME: backtest_date_range.start_date,
            BACKTESTING_LAST_SNAPSHOT_DATETIME: None
        }
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(data)

    def initialize_storage(self, remove_database_if_exists: bool = False):
        """
        Function to initialize the storage for the app. The given
        resource directory will be created if it does not exist.
        The database directory will also be created if it does not
        exist.
        """
        resource_directory_path = self.resource_directory_path

        if not os.path.exists(resource_directory_path):
            os.makedirs(resource_directory_path)
            logger.info(
                f"Resource directory created at {resource_directory_path}"
            )

        database_directory_path = self.database_directory_path

        if not os.path.exists(database_directory_path):
            os.makedirs(database_directory_path)
            logger.info(
                f"Database directory created at {database_directory_path}"
            )

        database_path = os.path.join(
            database_directory_path, self.config[DATABASE_NAME]
        )

        if remove_database_if_exists:

            if os.path.exists(database_path):
                logger.info(
                    f"Removing existing database at {database_path}"
                )
                os.remove(database_path)

        # Create the sqlalchemy database uri
        path = f"sqlite:///{database_path}"
        self.set_config(SQLALCHEMY_DATABASE_URI, path)

        # Setup sql if needed
        setup_sqlalchemy(self)
        create_all_tables()

    def initialize_data_sources(self, algorithm):
        """
        Function to initialize the data sources for the app. This method
        should be called before running the algorithm. This method
        initializes all data sources so that they are ready to be used.

        Args:
            algorithm (Algorithm): The algorithm to initialize the data
                sources for. This should be an instance of Algorithm.

        Returns:
            None
        """
        logger.info("Initializing data sources")
        data_provider_service = self.container.data_provider_service()
        data_provider_service.reset()

        for data_provider in self._data_providers:
            data_provider_service.add_data_provider(data_provider)

        # Add the default data providers
        data_provider_service.add_data_provider(CCXTOHLCVDataProvider())

        # Initialize all data sources
        data_provider_service.index_data_providers(algorithm.data_sources)

    def initialize_data_sources_backtest(
        self,
        algorithm,
        backtest_date_range: BacktestDateRange
    ):
        """
        Function to initialize the data sources for the app in backtest mode.
        This method should be called before running the algorithm in backtest
        mode. It initializes all data sources so that they are
        ready to be used.

        Args:
            algorithm (Algorithm): The algorithm to initialize the data
                sources for. This should be an instance of Algorithm.
            backtest_date_range (BacktestDateRange): The date range for the
                backtest. This should be an instance of BacktestDateRange.

        Returns:
            None
        """
        logger.info("Initializing data sources for backtest")
        data_provider_service = self.container.data_provider_service()
        data_provider_service.reset()

        for data_provider in self._data_providers:
            data_provider_service.add_data_provider(data_provider)

        # Add the default data providers
        data_provider_service.add_data_provider(CCXTOHLCVDataProvider())

        # Initialize all data sources
        data_provider_service.index_backtest_data_providers(
            algorithm.data_sources, backtest_date_range
        )

        # Prepare the backtest data for each data provider
        for data_source, data_provider in \
                data_provider_service.data_provider_index.get_all():
            data_provider.prepare_backtest_data(
                backtest_date_range.start_date,
                backtest_date_range.end_date
            )

    def initialize_backtest_services(self):
        """
        Function to initialize the backtest services for the app. This method
        should be called before running the algorithm in backtest mode.
        It initializes the backtest services so that they are ready to be used.

        Returns:
            None
        """
        configuration_service = self.container.configuration_service()
        self.initialize_order_executors()
        self.initialize_portfolio_providers()
        portfolio_conf_service = self.container \
            .portfolio_configuration_service()
        portfolio_snap_service = self.container \
            .portfolio_snapshot_service()
        market_cred_service = self.container.market_credential_service()
        portfolio_provider_lookup = \
            self.container.portfolio_provider_lookup()
        # Override the portfolio service with the backtest portfolio service
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

        portfolio_conf_service = self.container. \
            portfolio_configuration_service()
        portfolio_snap_service = self.container. \
            portfolio_snapshot_service()
        configuration_service = self.container.configuration_service()
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
            )
        )

    def initialize_services(self):
        """
        Method to initialize the app. This method should be called before
        running the algorithm. It initializes the services and the algorithm
        and sets up the database if it does not exist.

        Also, it initializes all required services for the algorithm.

        Returns:
            None
        """
        logger.info("Initializing app")
        self.initialize_order_executors()
        self.initialize_portfolio_providers()

        # Initialize all market credentials
        market_credential_service = self.container.market_credential_service()
        market_credential_service.initialize()
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()

        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        configuration_service = self.container.configuration_service()
        config = configuration_service.get_config()

        if AppMode.WEB.equals(config[APP_MODE]):
            configuration_service.add_value(APP_MODE, AppMode.WEB.value)
            self._initialize_web()


    def run(self, payload: dict = None, number_of_iterations: int = None):
        """
        Entry point to run the application. This method should be called to
        start the trading bot. This method can be called in three modes:

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
                hook.on_run(self.context)

            configuration_service = self.container.configuration_service()
            config = configuration_service.get_config()

            algorithm_factory: AlgorithmFactory = \
                self.container.algorithm_factory()
            algorithm = algorithm_factory.create_algorithm(
                name=self._name,
                strategies=self._strategies,
                tasks=self._tasks,
                on_strategy_run_hooks=self._on_strategy_run_hooks,
            )
            self.initialize_data_sources(algorithm)

            # Run in payload mode if payload is provided
            if payload is not None:
                logger.info("Running with payload")
                context = self.container.context()
                action_handler = ActionHandler.of(payload)
                response = action_handler.handle(
                    payload=payload,
                    context=context,
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

            event_loop_service = EventLoopService(
                configuration_service=self.container.configuration_service(),
                portfolio_snapshot_service=self.container
                .portfolio_snapshot_service(),
                context=self.context,
                order_service=self.container.order_service(),
                portfolio_service=self.container.portfolio_service(),
                data_provider_service=self.container.data_provider_service(),
                trade_service=self.container.trade_service(),
                trade_order_evaluator=self._trade_order_evaluator
            )

            try:
                event_loop_service.start(
                    number_of_iterations=number_of_iterations
                )
            except KeyboardInterrupt:
                exit(0)
        except Exception as e:
            logger.error(e)
            raise e
        finally:

            try:
                # Upload state if state handler is provided
                if self._state_handler is not None:
                    logger.info("Detected state handler, saving state")
                    config = \
                        self.container.configuration_service().get_config()
                    self._state_handler.save(config[RESOURCE_DIRECTORY])
            except Exception as e:
                logger.error(e)

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
        """
        Function to add a task to the application.

        Args:
            function:
            time_unit:
            interval:

        Returns:
            Union(Task, Function): the task
        """

        if function:
            task = Task(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
            )
            self._tasks.append(task)
            return task
        else:
            def wrapper(f):
                self._tasks.append(
                    Task(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval
                    )
                )
                return f

            return wrapper

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        assert isinstance(task, Task), \
            OperationalException(
                "Task object is not an instance of a Task"
            )

        self._tasks.append(task)

    def add_tasks(self, tasks: List[Task]):
        """
        Function to add a list of tasks to the app. The tasks should be
        instances of Task.

        Args:
            tasks: List of Task instances

        Returns:
            None
        """
        for task in tasks:
            self.add_task(task)

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

    def get_portfolio_configurations(self):
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        return portfolio_configuration_service.get_all()

    def get_market_credential(self, market: str) -> MarketCredential:
        """
        Function to get a market credential from the app. This method
        should be called when you want to get a market credential.

        Args:
            market (str): The market to get the credential for

        Returns:
            MarketCredential: Instance of MarketCredential
        """

        market_credential_service = self.container \
            .market_credential_service()
        market_credential = market_credential_service.get(market)
        if market_credential is None:
            raise OperationalException(
                f"Market credential for {market} not found"
            )
        return market_credential

    def get_market_credentials(self) -> List[MarketCredential]:
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
        name: str = None,
        initial_amount=None,
        output_directory=None,
        algorithm=None,
        strategy=None,
        strategies: List = None,
        save=True,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        strategy_directory_path: Optional[str] = None,
        backtest_directory_name: Optional[str] = None,
        risk_free_rate: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Backtest:
        """
        Run a backtest for an algorithm.

        Args:
            backtest_date_range: The date range to run the backtest for
                (instance of BacktestDateRange)
            name: The name of the backtest. This is used to identify the
                backtest report in the output directory.
            initial_amount: The initial amount to start the backtest with.
                This will be the amount of trading currency that the backtest
                portfolio will start with.
            strategy (TradingStrategy) (Optional): The strategy object
                that needs to be backtested.
            strategies (List[TradingStrategy]) (Optional): List of strategy
                objects that need to be backtested
            algorithm (Algorithm) (Optional): The algorithm object that needs
                to be backtested. If this is provided, then the strategies
                and tasks of the algorithm will be used for the backtest.
            output_directory (str) (Optional): The directory to write
                the backtest report to
            snapshot_interval (SnapshotInterval): The snapshot
                interval to use for the backtest. This is used to determine
                how often the portfolio snapshot should be taken during the
                backtest. The default is TRADE_CLOSE, which means that the
                portfolio snapshot will be taken at the end of each trade.
            strategy_directory_path (Optional[str]): The directory path
                where the strategy is located. This is used to save the
                strategy if save_strategy is True. If not provided,
                the framework tries to determine the path via the
                algorithm or strategy object.
            backtest_directory_name (Optional[str]): If not
                provided, the framework will generate a name based on the
                algorithm name and the backtest date range and the current
                date and time.
            risk_free_rate (Optional[float]): The risk-free rate to use for
                the backtest. This is used to calculate the Sharpe ratio
                and other performance metrics. If not provided, the default
                risk-free rate will be tried to be fetched from the
                US Treasury website.
            save (bool): Whether to save the backtest report to the output
                directory. If True, then the backtest report will be saved
                to the output directory.
            metadata (Optional[Dict[str, str]]): Metadata to attach to the
                backtest report. This can be used to store additional
                information about the backtest, such as the author, version,
                parameters or any other relevant information.

        Returns:
            Backtest: Instance of Backtest
        """
        self.initialize_backtest_config(
            backtest_date_range=backtest_date_range,
            snapshot_interval=snapshot_interval,
            initial_amount=initial_amount
        )
        self.initialize_storage(remove_database_if_exists=True)
        self.initialize_backtest_services()
        self.initialize_backtest_portfolios()

        algorithm = self.container.algorithm_factory().create_algorithm(
            name=name if name else self._name,
            strategies=(
                self._strategies if strategies is None else strategies
            ),
            algorithm=algorithm,
            strategy=strategy,
            tasks=self._tasks,
            on_strategy_run_hooks=self._on_strategy_run_hooks,
        )
        self.initialize_data_sources_backtest(algorithm, backtest_date_range)
        backtest_service = self.container.backtest_service()

        # Create backtest schedule
        schedule = backtest_service.generate_schedule(
            algorithm.strategies,
            algorithm.tasks,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Initialize event loop
        event_loop_service = EventLoopService(
            configuration_service=self.container.configuration_service(),
            portfolio_snapshot_service=self.container
            .portfolio_snapshot_service(),
            context=self.context,
            order_service=self.container.order_service(),
            portfolio_service=self.container.portfolio_service(),
            data_provider_service=self.container.data_provider_service(),
            trade_service=self.container.trade_service(),
            trade_order_evaluator=self._trade_order_evaluator
        )
        trade_order_evaluator = BacktestTradeOrderEvaluator(
            trade_service=self.container.trade_service(),
            order_service=self.container.order_service()
        )
        event_loop_service.initialize(
            algorithm=algorithm,
            trade_order_evaluator=trade_order_evaluator
        )
        event_loop_service.start(schedule=schedule, show_progress=True)

        # Convert the current run to a backtest and save it if needed
        backtest = backtest_service.create_backtest(
            algorithm=algorithm,
            number_of_runs=event_loop_service.total_number_of_runs,
            backtest_date_range=backtest_date_range,
            risk_free_rate=risk_free_rate,
        )
        backtest.metadata = metadata if metadata is not None else {}
        # backtest_service.save_backtest(backtest)
        return backtest

            # strategy_orchestrator_service = \
        #     self.container.strategy_orchestrator_service()
        # strategy_orchestrator_service.initialize(algorithm)
        # backtest_service = self.container.backtest_service()
        #
        # # Setup snapshot service as observer
        # backtest_service.clear_observers()
        # portfolio_snapshot_service = \
        #     self.container.portfolio_snapshot_service()
        # backtest_service.add_observer(portfolio_snapshot_service)
        # context = self.container.context()
        # order_service = self.container.order_service()
        # order_service.clear_observers()
        # order_service.add_observer(portfolio_snapshot_service)
        # portfolio_service = self.container.portfolio_service()
        # portfolio_service.clear_observers()
        # portfolio_service.add_observer(portfolio_snapshot_service)
        # backtest = backtest_service.run_backtest(
        #     algorithm=algorithm,
        #     context=context,
        #     strategy_orchestrator_service=strategy_orchestrator_service,
        #     initial_amount=initial_amount,
        #     backtest_date_range=backtest_date_range,
        #     risk_free_rate=risk_free_rate,
        #     strategy_directory_path=strategy_directory_path
        # )
        # backtest.metadata = metadata if metadata is not None else {}
        #
        # if output_directory is None:
        #     output_directory = os.path.join(
        #         config[RESOURCE_DIRECTORY], "backtest_reports"
        #     )
        #
        # if backtest_directory_name is None:
        #     backtest_directory_name = BacktestService\
        #         .create_report_directory_name(backtest)
        #
        # output_directory = os.path.join(
        #     output_directory, backtest_directory_name
        # )
        #
        # if save:
        #     backtest.save(directory_path=output_directory)
        #
        # return backtest

    def run_backtests(
        self,
        algorithms=None,
        strategies: List[TradingStrategy] = None,
        initial_amount=None,
        backtest_date_ranges: List[BacktestDateRange] = None,
        snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY,
        risk_free_rate: Optional[float] = None,
        save=True,
        output_directory=None,
        checkpoint=False,
    ) -> List[Backtest]:
        """
        Run a set of backtests for the provided algorithms or strategies
        with the given date ranges.

        Args:
            algorithms (List[Algorithm]) (Optional): The algorithms to run
                backtests for. This param is optional. Either algorithms or
                strategies should be provided. If both are provided, then the
                algorithms will be used.
            strategies (List[TradingStrategy]) (Optional): The strategies to
                run backtests for. This param is optional. Either algorithms
                or strategies should be provided. If both are provided, then
                the algorithms will be used.
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
            save (bool): Whether to save the backtest report
                to the output directory. If True, then the backtest report
                will be saved to the output directory.
            snapshot_interval (SnapshotInterval): The snapshot interval to
                use for the backtest. This is used to determine how often
                the portfolio snapshot should be taken during the backtest.

        Returns
            List[Backtest]: List of Backtest instances
        """
        logger.info("Initializing backtests")
        reports = []

        if algorithms is None and strategies is None:
            raise OperationalException(
                "No algorithms or strategies provided for backtest"
            )

        # Create or validate all algorithms with the algorithm factory
        algorithm_factory = self.container.algorithm_factory()

        if algorithms is not None:
            to_be_validated_algorithms = algorithms
            algorithms = []

            for algorithm in to_be_validated_algorithms:
                algorithm = algorithm_factory.create_algorithm(
                    algorithm=algorithm
                )
                algorithms.append(algorithm)
        else:
            algorithms = []

        if strategies is not None:
            for strategy in strategies:
                algorithms.append(
                    algorithm_factory.create_algorithm(strategy=strategy)
                )

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

                report = self.run_backtest(
                    backtest_date_range=date_range,
                    initial_amount=initial_amount,
                    output_directory=output_directory,
                    algorithm=algorithm,
                    save=save,
                    snapshot_interval=snapshot_interval,
                    risk_free_rate=risk_free_rate
                )
                reports.append(report)

        return reports

    def add_data_provider(self, data_provider) -> None:
        """
        Function to add a data provider to the app. The data provider should
        be an instance of DataProvider or a DataProviderClass.

        Args:
            data_provider: Instance or class of DataProvider

        Returns:
            None
        """
        if inspect.isclass(data_provider):
            if not issubclass(data_provider, DataProvider):
                raise OperationalException(
                    "Data provider should be an instance of DataProvider"
                )

            data_provider = data_provider()

        self._data_providers.append(data_provider)

    def add_data_providers(self, data_providers: List) -> None:
        """
        Function to add a list of data providers to the app.

        Args:
            data_providers: List of DataProvider instances or classes

        Returns:
            None
        """
        for data_provider in data_providers:
            self.add_data_provider(data_provider)

    def add_market_data_source(self, market_data_source):
        """
        Function to add a market data source to the app. The market data
        source should be an instance of MarketDataSource.

        This is a seperate function from the market data source service. This
        is because the market data source service can be re-initialized.
        Therefore, we need a persistent list of market data sources in the app.

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

        self._market_data_sources.append(market_data_source)

    def add_market_credential(
        self, market_credential: MarketCredential
    ) -> None:
        """
        Function to add a market credential to the app. The market
        credential should be an instance of MarketCredential.

        Args:
            market_credential:

        Returns:
            None
        """
        market_credential.market = market_credential.market.upper()
        market_credential_service = self.container \
            .market_credential_service()
        market_credential_service.add(market_credential)

    def on_initialize(self, app_hook):
        """
        Function to add a hook that runs when the app is initialized. The hook
        should be an instance of AppHook.

        Args:
            app_hook: Instance of AppHook

        Returns:
            None
        """

        # Check if the app_hook inherits from AppHook
        if not issubclass(app_hook, AppHook):
            raise OperationalException(
                "App hook should be an instance of AppHook"
            )

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_initialize_hooks.append(app_hook)

    def on_strategy_run(self, app_hook):
        """
        Function to add a hook that runs when a strategy is run. The hook
        should be an instance of AppHook.
        """

        # Check if the app_hook inherits from AppHook
        if inspect.isclass(app_hook) and not issubclass(app_hook, AppHook):
            raise OperationalException(
                "App hook should be an instance of AppHook"
            )

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_strategy_run_hooks.append(app_hook)

    def after_initialize(self, app_hook: AppHook):
        """
        Function to add a hook that runs after the app is initialized.
        The hook should be an instance of AppHook.
        """

        if inspect.isclass(app_hook):
            app_hook = app_hook()

        self._on_after_initialize_hooks.append(app_hook)

    def strategy(
        self,
        function=None,
        time_unit=TimeUnit.MINUTE,
        interval=10,
        market_data_sources=None
    ):
        """
        Decorator for registering a strategy. This decorator can be used
        to define a trading strategy function and register it in your
        application.

        Args:
            function: The wrapped function to should be converted to
                a TradingStrategy
            time_unit (TimeUnit): instance of TimeUnit Enum
            interval (int): interval of the schedule ( interval - TimeUnit )
            market_data_sources (List): List of data sources that the
                trading strategy function uses.

        Returns:
            Function
        """
        from .strategy import TradingStrategy

        if function:
            strategy_object = TradingStrategy(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
                market_data_sources=market_data_sources
            )
            self.add_strategy(strategy_object)
            return strategy_object
        else:

            def wrapper(f):
                self.add_strategy(
                    TradingStrategy(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval,
                        market_data_sources=market_data_sources,
                        worker_id=f.__name__
                    )
                )
                return f

            return wrapper

    def add_strategies(self, strategies, throw_exception=True) -> None:
        """
        Function to add strategies to the app
        Args:
            strategies (List(TradingStrategy)): List of trading strategies that
                need to be registered.
            throw_exception (boolean): Flag to specify if an exception
                can be thrown if the strategies are not in the format or type
                that the application expects

        Returns:
            None
        """

        if strategies is not None:
            for strategy in strategies:
                self.add_strategy(strategy, throw_exception=throw_exception)

    def add_strategy(self, strategy, throw_exception=True) -> None:
        """
        Function to add a strategy to the app. The strategy should be an
        instance of TradingStrategy or a subclass based on the TradingStrategy
        class.

        Args:
            strategy: Instance of TradingStrategy
            throw_exception: Flag to allow for throwing an exception when
                the provided strategy is not inline with what the application
                expects.

        Returns:
            None
        """

        logger.info("Adding strategy")

        if inspect.isclass(strategy):

            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            strategy = strategy()

        if not isinstance(strategy, TradingStrategy):

            if throw_exception:
                raise OperationalException(
                    "Strategy should be an instance of TradingStrategy"
                )
            else:
                return

        has_duplicates = False

        for i in range(len(self._strategies)):
            for j in range(i + 1, len(self._strategies)):
                if self._strategies[i].worker_id == strategy.worker_id:
                    has_duplicates = True
                    break

        if has_duplicates:
            raise OperationalException(
                "Can't add strategy, there already exists a strategy "
                "with the same id in the algorithm"
            )

        if strategy.market_data_sources is not None:
            logger.info("Adding market data sources from strategy")
            self.add_data_sources(strategy.market_data_sources)

        self._strategies.append(strategy)

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

    def initialize_order_executors(self):
        """
        Function to initialize the order executors. This function will
        first check if the app is running in backtest mode or not. If it is
        running in backtest mode, all order executors will be removed and
        a single BacktestOrderExecutor will be added to the order executors.

        If it is not running in backtest mode, it will add the default
        CCXTOrderExecutor with a priority 3.
        """
        logger.info("Adding order executors")
        order_executor_lookup = self.container.order_executor_lookup()
        environment = self.config[ENVIRONMENT]

        if Environment.BACKTEST.equals(environment):
            # If the app is running in backtest mode, remove all order executors
            # and add a single BacktestOrderExecutor
            order_executor_lookup.reset()
            order_executor_lookup.add_order_executor(
                BacktestOrderExecutor(priority=1)
            )
        else:
            order_executor_lookup.add_order_executor(
                CCXTOrderExecutor(priority=3)
            )

        for order_executor in order_executor_lookup.get_all():
            order_executor.config = self.config

    def initialize_portfolios(self):
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
        market_credential_service = \
            self.container.market_credential_service()
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
                market_credential_service.get(
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

    def initialize_backtest_portfolios(self):
        """
        Function to initialize the backtest portfolios. This function will
        create a default portfolio provider for each market that is configured
        in the app. The default portfolio provider will be used to create
        portfolios for the app.

        Returns:
            None
        """
        logger.info("Initializing backtest portfolios")
        config = self.config
        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()
        portfolio_service = self.container.portfolio_service()

        # Throw an error if no portfolios are configured
        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        logger.info("Setting up backtest portfolios")
        initial_backtest_amount = config.get(
            BACKTESTING_INITIAL_AMOUNT, None
        )

        for portfolio_configuration \
                in portfolio_configuration_service.get_all():

            if not portfolio_service.exists(
                {"identifier": portfolio_configuration.identifier}
            ):
                portfolio_service.create_portfolio_from_configuration(
                    portfolio_configuration,
                    initial_amount=initial_backtest_amount,
                )

    def initialize_portfolio_providers(self):
        """
        Function to initialize the default portfolio providers.
        This function will create a default portfolio provider for
        each market that is configured in the app. The default portfolio
        provider will be used to create portfolios for the app.

        Returns:
            None
        """
        logger.info("Adding portfolio providers")
        portfolio_provider_lookup = self.container.portfolio_provider_lookup()
        environment = self.config[ENVIRONMENT]

        if Environment.BACKTEST.equals(environment):
            # If the app is running in backtest mode, remove all order executors
            # and add a single BacktestOrderExecutor
            portfolio_provider_lookup.reset()
        else:
            portfolio_provider_lookup.add_portfolio_provider(
                CCXTPortfolioProvider(priority=3)
            )

        for portfolio_provider in portfolio_provider_lookup.get_all():
            portfolio_provider.config = self.config

    def get_run_history(self):
        """
        Function to get the run history of the app. This function will
        return the history of the run schedule of all the strategies,
        and tasks that have been registered in the app.

        Returns:
            dict: The run history of the app
        """
        return self._run_history

    def has_run(self, worker_id) -> bool:
        """
        Function to check if a worker has run in the app. This function
        will check if the worker_id is present in the run history of the app.

        Args:
            worker_id:

        Returns:
            Boolean: True if the worker has run, False otherwise
        """
        if self._run_history is None:
            return False

        return worker_id in self._run_history

    def get_algorithm(self):
        """
        Function to get the algorithm that is currently running in the app.
        This function will return the algorithm that is currently running
        in the app.

        Returns:
            Algorithm: The algorithm that is currently running in the app
        """
        algorithm_factory = self.container.algorithm_factory()
        return algorithm_factory.create_algorithm(
            name=self._name,
            strategies=self._strategies,
            tasks=self._tasks,
            data_sources=self._market_data_sources,
            on_strategy_run_hooks=self._on_strategy_run_hooks,
        )
