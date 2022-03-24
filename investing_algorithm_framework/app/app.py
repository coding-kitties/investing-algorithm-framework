import logging
import os
import shutil
from distutils.sysconfig import get_python_lib

from flask import Flask

from investing_algorithm_framework.configuration import create_app, \
    setup_config, Environment
from investing_algorithm_framework.configuration.constants import \
    RESOURCE_DIRECTORY, DATABASE_DIRECTORY_PATH, DATABASE_NAME, \
    DATABASE_CONFIG, DEFAULT_DATABASE_NAME, ENVIRONMENT
from investing_algorithm_framework.configuration.settings import Config
from investing_algorithm_framework.context import Singleton
from investing_algorithm_framework.core.context \
    import AlgorithmContextConfiguration
from investing_algorithm_framework.core.context import algorithm
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import create_all_tables, \
    initialize_db
from investing_algorithm_framework.extensions import scheduler

logger = logging.getLogger(__name__)


class App(metaclass=Singleton):
    _algorithm = algorithm
    _flask_app: Flask = None
    _started = False
    _config = AlgorithmContextConfiguration()
    _blueprints = []

    def __init__(self, resource_directory: str = None, config=None):

        if self.config is None:
            self.config = AlgorithmContextConfiguration()
            self.config.load(Config())

        if not self.config.application_configured() and \
                resource_directory is not None:
            self.config.set_resource_directory(resource_directory)

        if not self.config.application_configured() and config is not None:
            self.config.load(config)

    def initialize(
        self, resource_directory: str = None, config=None
    ):
        if self.config is None:
            self.config = AlgorithmContextConfiguration()
            self.config.load(Config())

        if not self.config.application_configured() \
                and resource_directory is not None:
            self.config.set_resource_directory(resource_directory)

        if not self.config.application_configured() and config is not None:
            self.config.load(config)

    def _initialize_flask_app(self):

        if self._flask_app is None:
            self._flask_app = create_app()

    def _initialize_flask_sql_alchemy(self):

        if self.config.sqlite_enabled() and self.config.sqlite_configured():
            initialize_db(self._flask_app)
            create_all_tables()
            self.config.set_sql_alchemy_configured()

    def _initialize_flask_config(self):
        setup_config(self._flask_app, self.config)

    def _initialize_database(self):

        if self.config.sqlite_enabled() \
                and self.config.sqlite_required() \
                and not self.config.sqlite_configured() \
                and self.config.resource_directory_configured():
            database_config = self.config.get(DATABASE_CONFIG)

            if database_config is None:
                database_path = os.path.join(
                    self.config.get(RESOURCE_DIRECTORY),
                    '{}.sqlite3'.format(DEFAULT_DATABASE_NAME)
                )
                self.config.set_database_name(DEFAULT_DATABASE_NAME)
                self.config.set_database_directory(
                    self.config.get(RESOURCE_DIRECTORY)
                )
                self.config.set_sql_alchemy_uri(database_path)
            else:
                database_directory_path = database_config.get(
                    DATABASE_DIRECTORY_PATH, None
                )
                database_name = database_config.get(DATABASE_NAME, None)

                if database_name is None:
                    database_name = DEFAULT_DATABASE_NAME
                    self.config.set_database_name(database_name)

                if database_directory_path is None:
                    database_directory_path = self.config\
                        .get(RESOURCE_DIRECTORY)
                    self.config.set_database_directory(
                        database_directory_path)

                database_path = os.path.join(
                    database_directory_path, f'{database_name}.sqlite3'
                )

            self.config.set_sql_alchemy_uri(f'sqlite:////{database_path}')

            # Create the database if it not exist
            if not os.path.isfile(database_path):
                open(database_path, 'w').close()

            self.config.validate_database_configuration()
            self.config.set_sqlite_configured()

    def _initialize_management_commands(self):

        if self.config.resource_directory_configured() and \
                not Environment.TEST.equals(self.config.get(ENVIRONMENT)):
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

    def register_blueprint(self, blueprint):
        self._blueprints.append(blueprint)

    def _initialize_blueprints(self):

        for blueprint in self._blueprints:
            self._flask_app.register_blueprint(blueprint)

    def start(self, algorithm_only=False):

        if not self.config.resource_directory_configured():
            raise OperationalException("Resource directory not configured")

        self.config.add_portfolio_configuration(
            self.algorithm.portfolio_managers
        )

        self._initialize_flask_app()
        self._initialize_blueprints()
        self._initialize_database()
        self._initialize_flask_config()
        self._initialize_flask_sql_alchemy()
        self._initialize_management_commands()

        self.algorithm.config = self.config
        self._algorithm.initialize_portfolio_managers()

        self.start_scheduler()
        self.start_algorithm()

        if not algorithm_only:
            self._flask_app.run(
                debug=False,
                threaded=True,
                use_reloader=False
            )

        if not scheduler.running:
            raise OperationalException(
                "Could not start algorithm because the scheduler "
                "is not running"
            )

    def start_scheduler(self):

        # Initialize the schedulers
        if not scheduler.running:
            scheduler.init_app(self._flask_app)
            scheduler.start()

    def start_algorithm(self):

        # Start the algorithm
        self._algorithm.start()

    def stop_algorithm(self):

        if self._algorithm.running:
            self._algorithm.stop()

    @property
    def algorithm(self):
        return self._algorithm

    @property
    def started(self):
        return self._started

    @property
    def config(self) -> AlgorithmContextConfiguration:
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    def reset(self):
        self._started = False
        scheduler.remove_all_jobs()
        self.algorithm.reset()

    def add_initializer(self, initializer):
        self.algorithm.add_initializer(initializer)

    def add_order_executor(self, order_executor):
        self.algorithm.add_order_executor(order_executor)

    def add_data_provider(self, data_provider):
        self.algorithm.add_data_provider(data_provider)

    def add_portfolio_manager(self, portfolio_manager):
        self.algorithm.add_portfolio_manager(portfolio_manager)
