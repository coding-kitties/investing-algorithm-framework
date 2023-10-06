import inspect
import logging
import os
import shutil
import threading
from distutils.sysconfig import get_python_lib
from time import sleep

from flask import Flask

from investing_algorithm_framework.app.algorithm import Algorithm
from investing_algorithm_framework.app.stateless import ActionHandler
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.app.task import Task
from investing_algorithm_framework.app.web import create_flask_app
from investing_algorithm_framework.domain import DATABASE_NAME, TimeUnit, \
    DATABASE_DIRECTORY_PATH, RESOURCE_DIRECTORY, ENVIRONMENT, Environment, \
    SQLALCHEMY_DATABASE_URI, Config, OperationalException
from investing_algorithm_framework.infrastructure import setup_sqlalchemy, \
    create_all_tables

logger = logging.getLogger("investing_algorithm_framework")


class App:

    def __init__(self, config=None, stateless=False, web=False):
        self._flask_app: Flask = None
        self.container = None
        self.config = Config.from_dict(config)
        self._stateless = stateless
        self._web = web
        self.algorithm: Algorithm = None
        self._started = False
        self._strategies = []
        self._tasks = []

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

        self.create_portfolios()

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

        self.algorithm.config = self.config
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
                name='Web App', target=self._flask_app.run
            )
            flask_thread.setDaemon(True)
            flask_thread.start()

        order_service = self.container.order_service()
        number_of_iterations_since_last_orders_check = 1
        order_service.check_pending_orders()

        try:
            while self.algorithm.running:
                if number_of_iterations_since_last_orders_check == 30:
                    logger.info("Checking pending orders")
                    order_service.check_pending_orders()
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
        return self._config

    @config.setter
    def config(self, config):

        if config is not None:
            self._config = config

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
        market=None,
        trading_data_type=None,
        trading_data_types=None,
        trading_time_frame=None,
        trading_time_frame_start_date=None,
        symbols=None,
    ):

        if function:
            strategy_object = TradingStrategy(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
                market=market,
                trading_data_type=trading_data_type,
                trading_data_types=trading_data_types,
                symbols=symbols,
                trading_time_frame=trading_time_frame,
                trading_time_frame_start_date=trading_time_frame_start_date
            )
            self.add_strategy(strategy_object)
        else:
            start_date = trading_time_frame_start_date

            def wrapper(f):
                self.add_strategy(
                    TradingStrategy(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval,
                        market=market,
                        trading_data_type=trading_data_type,
                        trading_data_types=trading_data_types,
                        symbols=symbols,
                        trading_time_frame=trading_time_frame,
                        trading_time_frame_start_date=start_date,
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

    def create_portfolios(self):
        logger.info("Creating portfolios")
        portfolio_configuration_service = self.container\
            .portfolio_configuration_service()
        market_service = self.container.market_service()
        portfolio_repository = self.container.portfolio_repository()
        position_repository = self.container.position_repository()

        for portfolio_configuration in \
                portfolio_configuration_service.get_all():
            market_service.initialize(portfolio_configuration)

            if portfolio_repository.exists(
                {"identifier": portfolio_configuration.identifier}
            ):
                continue

            balances = market_service.get_balance()
            if portfolio_configuration.trading_symbol.upper() not in balances:
                raise OperationalException(
                    f"Trading symbol balance not available "
                    f"in portfolio on market {portfolio_configuration.market}"
                )

            unallocated = float(
                balances[portfolio_configuration.trading_symbol.upper()]
                ["free"]
            )
            portfolio_repository.create(
                {
                    "unallocated": unallocated,
                    "identifier": portfolio_configuration.identifier,
                    "trading_symbol": portfolio_configuration.trading_symbol,
                    "market": portfolio_configuration.market,
                }
            )
            portfolio = portfolio_repository.find(
                {"identifier": portfolio_configuration.identifier}
            )
            portfolio = position_repository.create(
                {
                    "symbol": portfolio_configuration.trading_symbol,
                    "amount": unallocated,
                    "portfolio_id": portfolio.id
                }
            )
            logger.info(f"Created portfolio {portfolio}")

    def _initialize_web(self):
        resource_dir = self._config[RESOURCE_DIRECTORY]

        if resource_dir is None:
            self._config[SQLALCHEMY_DATABASE_URI] = "sqlite://"
        else:
            resource_dir = self._create_resource_directory_if_not_exists()
            self._config[DATABASE_DIRECTORY_PATH] = os.path.join(
                resource_dir, "databases"
            )
            self._config[DATABASE_NAME] = "prod-database.sqlite3"
            self._config[SQLALCHEMY_DATABASE_URI] = \
                "sqlite:///" + os.path.join(
                    self._config[DATABASE_DIRECTORY_PATH],
                    self._config[DATABASE_NAME]
                )
            self._create_database_if_not_exists()

        self._flask_app = create_flask_app(self._config)

    def _initialize_stateless(self):
        self._config[SQLALCHEMY_DATABASE_URI] = "sqlite://"

    def _initialize_standard(self):
        resource_dir = self._config[RESOURCE_DIRECTORY]

        if resource_dir is None:
            self._config[SQLALCHEMY_DATABASE_URI] = "sqlite://"
        else:
            resource_dir = self._create_resource_directory_if_not_exists()
            self._config[DATABASE_DIRECTORY_PATH] = os.path.join(
                resource_dir, "databases"
            )
            self._config[DATABASE_NAME] = "prod-database.sqlite3"
            self._config[SQLALCHEMY_DATABASE_URI] = \
                "sqlite:///" + os.path.join(
                    self._config[DATABASE_DIRECTORY_PATH],
                    self._config[DATABASE_NAME]
                )
            self._create_database_if_not_exists()

    def _create_resource_directory_if_not_exists(self):
        if self._stateless:
            return

        resource_dir = self._config.get(RESOURCE_DIRECTORY, None)

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

        database_dir = self._config.get(DATABASE_DIRECTORY_PATH, None)

        if database_dir is None:
            return

        database_name = self._config.get(DATABASE_NAME, None)

        if database_name is None:
            return

        database_path = os.path.join(database_dir, database_name)

        if not os.path.exists(database_dir):
            try:
                os.makedirs(database_dir)
                open(database_path, 'w').close()
            except OSError as e:
                logger.error(e)
                raise OperationalException(
                    "Could not create database directory"
                )
 
    def get_portfolio_configurations(self):
        return self.algorithm.get_portfolio_configurations()
