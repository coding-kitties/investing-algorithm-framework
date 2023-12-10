import inspect
import logging
import os
import shutil
import threading
from distutils.sysconfig import get_python_lib
from time import sleep
from datetime import datetime

from flask import Flask

from investing_algorithm_framework.app.algorithm import Algorithm
from investing_algorithm_framework.app.stateless import ActionHandler
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.app.task import Task
from investing_algorithm_framework.app.web import create_flask_app
from investing_algorithm_framework.domain import DATABASE_NAME, TimeUnit, \
    DATABASE_DIRECTORY_PATH, RESOURCE_DIRECTORY, ENVIRONMENT, Environment, \
    SQLALCHEMY_DATABASE_URI, OperationalException, PortfolioConfiguration, \
    BACKTESTING_FLAG, BACKTESTING_START_DATE, BACKTEST_DATA_DIRECTORY_NAME
from investing_algorithm_framework.infrastructure import setup_sqlalchemy, \
    create_all_tables, BacktestMarketService, MarketService, CCXTMarketService
from investing_algorithm_framework.services import OrderBacktestService, \
    OrderService

logger = logging.getLogger("investing_algorithm_framework")


class App:

    def __init__(self, stateless=False, web=False):
        self._flask_app: Flask = None
        self.container = None
        self._stateless = stateless
        self._web = web
        self.algorithm: Algorithm = None
        self._started = False
        self._strategies = []
        self._tasks = []
        self._market_data_sources = []

    def set_config(self, config: dict):
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

    def initialize(self):

        if self._web:
            self._initialize_web()
        elif self._stateless:
            self._initialize_stateless()
        else:
            self._initialize_standard()

        setup_sqlalchemy(self)
        create_all_tables()
        self.algorithm = self.container.algorithm()
        self.algorithm.add_strategies(self.strategies)
        self.algorithm.add_tasks(self.tasks)
        portfolio_configuration_service = self.container\
            .portfolio_configuration_service()

        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        # Create all portfolios
        portfolio_configurations = portfolio_configuration_service.get_all()
        portfolio_service = self.container.portfolio_service()

        for portfolio_configuration in portfolio_configurations:
            portfolio_service.create_portfolio_from_configuration(
                portfolio_configuration
            )
        self.algorithm.set_market_data_sources(self._market_data_sources)

    def initialize_backtest(self, backtest_start_date):
        configuration_service = self.container.configuration_service()
        resource_dir = configuration_service.config[RESOURCE_DIRECTORY]
        configuration_service.config[BACKTESTING_FLAG] = True
        configuration_service.config[BACKTESTING_START_DATE] = \
            backtest_start_date

        if resource_dir is None:
            raise OperationalException(
                "Resource directory is not specified. "
                "A resource directory is required for running a backtest."
            )

        resource_dir = self._create_resource_directory_if_not_exists()
        configuration_service.config[DATABASE_DIRECTORY_PATH] = \
            os.path.join(resource_dir, "databases")
        configuration_service.config[DATABASE_NAME] = \
            "backtest-database.sqlite3"
        database_path = os.path.join(
            configuration_service.config[DATABASE_DIRECTORY_PATH],
            configuration_service.config[DATABASE_NAME]
        )

        if os.path.exists(database_path):
            os.remove(database_path)

        configuration_service.config[SQLALCHEMY_DATABASE_URI] = \
            "sqlite:///" + os.path.join(
                configuration_service.config[DATABASE_DIRECTORY_PATH],
                configuration_service.config[DATABASE_NAME]
            )
        self._create_database_if_not_exists()
        setup_sqlalchemy(self)
        create_all_tables()

        # Convert the market data sources to backtest market data sources
        market_data_sources = self.get_market_data_sources()
        backtest_market_data_sources = []

        for market_data_source in market_data_sources:
            backtest_market_data_source = \
                market_data_source.to_backtest_market_data_source()
            backtest_market_data_sources.append(backtest_market_data_source)

        # Override the market service with the backtest market service
        self.container.market_service.override(
            BacktestMarketService(
                backtest_market_data_sources=backtest_market_data_sources,
                configuration_service=self.container.configuration_service()
            )
        )
        # Override the order service with the backtest order service
        self.container.order_service.override(OrderBacktestService(
            order_repository=self.container.order_repository(),
            order_fee_repository=self.container.order_fee_repository(),
            market_service=self.container.market_service(),
            position_repository=self.container.position_repository(),
            portfolio_repository=self.container.portfolio_repository(),
            portfolio_configuration_service=self.container
            .portfolio_configuration_service(),
            portfolio_snapshot_service=self.container
            .portfolio_snapshot_service(),
            configuration_service=self.container.configuration_service(),
        ))

        portfolio_configuration_service = self.container \
            .portfolio_configuration_service()

        # Re-init the market service because the portfolio configuration
        # service is a singleton
        portfolio_configuration_service.market_service \
            = self.container.market_service()
        if portfolio_configuration_service.count() == 0:
            raise OperationalException("No portfolios configured")

        # Create all portfolios
        portfolio_configurations = portfolio_configuration_service.get_all()
        portfolio_service = self.container.portfolio_service()

        for portfolio_configuration in portfolio_configurations:
            portfolio_service.create_portfolio_from_configuration(
                portfolio_configuration
            )

        self.algorithm = self.container.algorithm()
        self.algorithm.set_market_data_sources(backtest_market_data_sources)
        self.algorithm.add_strategies(self.strategies)

    def _initialize_management_commands(self):

        if not Environment.TEST.equals(self.config.get(ENVIRONMENT)):
            # Copy the template manage.py file to the resource directory of the
            # algorithm
            management_commands_template = os.path.join(
                get_python_lib(),
                "investing_algorithm_framework/templates/manage.py"
            )
            destination = os.path.join(
                self.config.get(RESOURCE_DIRECTORY), "manage.py"
            )

            if not os.path.exists(destination):
                shutil.copy(management_commands_template, destination)

    def run(
        self,
        payload: dict = None,
        number_of_iterations: int = None,
        sync=True
    ):
        self.initialize()
        portfolio_service = self.container.portfolio_service()

        if sync:
            portfolio_service.sync_portfolios()

        self.algorithm.start(
            number_of_iterations=number_of_iterations,
            stateless=self.stateless
        )

        if self.stateless:
            logger.info("Running stateless")
            action_handler = ActionHandler.of(payload)
            return action_handler.handle(
                payload=payload, algorithm=self.algorithm
            )
        elif self._web:
            logger.info("Running web")
            flask_thread = threading.Thread(
                name='Web App',
                target=self._flask_app.run,
                kwargs={"port": 8080}
            )
            flask_thread.setDaemon(True)
            flask_thread.start()

        number_of_iterations_since_last_orders_check = 1
        self.algorithm.check_pending_orders()

        try:
            while self.algorithm.running:
                if number_of_iterations_since_last_orders_check == 30:
                    logger.info("Checking pending orders")
                    self.algorithm.check_pending_orders()
                    number_of_iterations_since_last_orders_check = 1

                self.algorithm.run_jobs()
                number_of_iterations_since_last_orders_check += 1
                sleep(1)
        except KeyboardInterrupt:
            exit(0)

    def start_algorithm(self):
        self.algorithm.start()

    def stop_algorithm(self):

        if self.algorithm.running:
            self.algorithm.stop()

    @property
    def started(self):
        return self._started

    @property
    def config(self):
        configuration_service = self.container.configuration_service()
        return configuration_service.config

    @config.setter
    def config(self, config: dict):
        configuration_service = self.container.configuration_service()
        configuration_service.initialize_from_dict(config)

    def reset(self):
        self._started = False
        self.algorithm.reset()

    def add_portfolio_configuration(self, portfolio_configuration):
        portfolio_configuration_service = self.container\
            .portfolio_configuration_service()
        portfolio_configuration_service.add(portfolio_configuration)

    @property
    def stateless(self):
        return self._stateless

    @property
    def web(self):
        return self._web

    @property
    def running(self):
        return self.algorithm.running

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
            self.add_task(task)
        else:
            def wrapper(f):
                self.add_task(
                    Task(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval
                    )
                )
                return f

            return wrapper

    def strategy(
        self,
        function=None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10,
        market_data_sources=None,
    ):

        if function:
            strategy_object = TradingStrategy(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
                market_data_sources=market_data_sources
            )
            self.add_strategy(strategy_object)
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

    def add_strategies(self, strategies):

        for strategy in strategies:
            self.add_strategy(strategy)

    def add_strategy(self, strategy):

        if inspect.isclass(strategy):
            strategy = strategy()

        assert isinstance(strategy, TradingStrategy), \
            OperationalException(
                "Strategy object is not an instance of a Strategy"
            )

        self._strategies.append(strategy)

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        assert isinstance(task, Task), \
            OperationalException(
                "Task object is not an instance of a Task"
            )

        self._tasks.append(task)

    @property
    def strategies(self):
        return self._strategies

    @property
    def tasks(self):
        return self._tasks

    def sync_portfolios(self):
        portfolio_configuration_service = self.container\
            .portfolio_configuration_service()
        portfolio_configuration_service.create_portfolios()
        portfolio_service = self.container.portfolio_service()
        portfolio_service.sync_portfolios()

    def _initialize_web(self):
        configuration_service = self.container.configuration_service()
        resource_dir = configuration_service.config[RESOURCE_DIRECTORY]

        if resource_dir is None:
            configuration_service.config[SQLALCHEMY_DATABASE_URI] = "sqlite://"
        else:
            resource_dir = self._create_resource_directory_if_not_exists()
            configuration_service.config[DATABASE_DIRECTORY_PATH] = os.path.join(
                resource_dir, "databases"
            )
            configuration_service.config[DATABASE_NAME] = "prod-database.sqlite3"
            configuration_service.config[SQLALCHEMY_DATABASE_URI] = \
                "sqlite:///" + os.path.join(
                    configuration_service.config[DATABASE_DIRECTORY_PATH],
                    configuration_service.config[DATABASE_NAME]
                )
            self._create_database_if_not_exists()

        self._flask_app = create_flask_app(configuration_service.config)

    def _initialize_stateless(self):
        configuration_service = self.container.configuration_service()
        configuration_service.config[SQLALCHEMY_DATABASE_URI] = "sqlite://"

    def _initialize_standard(self):
        configuration_service = self.container.configuration_service()
        resource_dir = configuration_service.config[RESOURCE_DIRECTORY]

        if resource_dir is None:
            configuration_service.config[SQLALCHEMY_DATABASE_URI] = "sqlite://"
        else:
            resource_dir = self._create_resource_directory_if_not_exists()
            configuration_service.config[DATABASE_DIRECTORY_PATH] = \
                os.path.join(resource_dir, "databases")
            configuration_service.config[DATABASE_NAME] \
                = "prod-database.sqlite3"
            configuration_service.config[SQLALCHEMY_DATABASE_URI] = \
                "sqlite:///" + os.path.join(
                    configuration_service.config[DATABASE_DIRECTORY_PATH],
                    configuration_service.config[DATABASE_NAME]
                )
            self._create_database_if_not_exists()

    def _create_resource_directory_if_not_exists(self):

        if self._stateless:
            return

        configuration_service = self.container.configuration_service()
        resource_dir = configuration_service.config.get(RESOURCE_DIRECTORY, None)

        if resource_dir is None:
            return

        if not os.path.exists(resource_dir):
            try:
                os.makedirs(resource_dir)
                open(resource_dir, 'w').close()
            except OSError as e:
                logger.error(e)
                raise OperationalException(
                    "Could not create resource directory"
                )

        return resource_dir

    def _create_database_if_not_exists(self):

        if self._stateless:
            return

        configuration_service = self.container.configuration_service()
        database_dir = configuration_service.config\
            .get(DATABASE_DIRECTORY_PATH, None)

        if database_dir is None:
            return

        database_name = configuration_service.config.get(DATABASE_NAME, None)

        if database_name is None:
            return

        database_path = os.path.join(database_dir, database_name)

        if not os.path.exists(database_path):

            if not os.path.isdir(database_dir):
                os.makedirs(database_dir)

            try:
                open(database_path, 'w').close()
            except OSError as e:
                logger.error(e)
                raise OperationalException(
                    "Could not create database directory"
                )

    def get_portfolio_configurations(self):
        return self.algorithm.get_portfolio_configurations()

    def backtest(
        self, start_date, end_date
    ):
        logger.info("Initializing backtest")
        self.initialize_backtest(backtest_start_date=start_date)
        backtest_service = self.container.backtest_service()
        backtest_service.resource_directory = self.config.get(
            RESOURCE_DIRECTORY
        )
        report = backtest_service.backtest(
            self.algorithm, start_date, end_date
        )
        return report

    def add_market_data_source(self, market_data_source):
        self._market_data_sources.append(market_data_source)

    def get_market_data_sources(self):
        return self._market_data_sources
