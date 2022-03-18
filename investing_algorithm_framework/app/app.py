import inspect
import logging
import os
import shutil
from distutils.sysconfig import get_python_lib

from flask import Flask

from investing_algorithm_framework.configuration import create_app, \
    setup_config, setup_database, setup_logging
from investing_algorithm_framework.configuration.constants import \
    LOG_LEVEL
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
    _configured: bool = False
    _database_configured: bool = False
    _started = False
    _config = None
    _resource_directory = None
    _blueprints = []

    def __init__(
        self, resources_directory: str = None, config=None, arg=None
    ):
        if resources_directory is not None:
            self._resource_directory = resources_directory

        if config is not None:
            self._initialize_config(config)

    def initialize(
        self, resources_directory: str = None, config=None, arg=None
    ):
        if not self._configured:

            if resources_directory is not None:
                self._resource_directory = resources_directory

            if config is not None:
                self._initialize_config(config)
                self._config.set_resource_directory(self._resource_directory)

    def _initialize_config(self, config=None):

        if not self._configured:

            if config is not None:
                if inspect.isclass(config):
                    config = config()

                self._config = AlgorithmContextConfiguration()
                self._config.load(config)

            if self._config is None:
                raise OperationalException("No config object set")

            self._algorithm.config = self._config
            setup_logging(self.config.get(LOG_LEVEL, "INFO"))
            self._configured = True

    def _initialize_flask_app(self):

        if self._flask_app is None:
            self._flask_app = create_app()

    def _initialize_flask_sql_alchemy(self):

        if self._configured and self._database_configured:
            initialize_db(self._flask_app)
            create_all_tables()

    def _initialize_flask_config(self):

        if self._configured:
            setup_config(self._flask_app, self._config)

    def _initialize_database(self):

        if self._configured and not self._database_configured:
            setup_database(self._config)
            self._config.validate_database_configuration()
            self._database_configured = True

    def _initialize_management_commands(self):
        # Copy the template manage.py file to the resource directory of the
        # algorithm
        management_commands_template = os.path.join(
            get_python_lib(),
            "investing_algorithm_framework/templates/manage.py"
        )

        destination = os.path.join(self._resource_directory, "manage.py")

        if not os.path.exists(destination):
            shutil.copy(management_commands_template, destination)

    def register_blueprint(self, blueprint):
        self._blueprints.append(blueprint)

    def _initialize_blueprints(self):

        for blueprint in self._blueprints:
            self._flask_app.register_blueprint(blueprint)

    def start(self):
        self._initialize_config()

        if not self._config.resource_directory_configured():
            raise OperationalException(
                "Resource directory is not configured"
            )

        if not self._config.can_write_to_resource_directory():
            raise OperationalException("Can't write to resource directory")

        self._initialize_flask_app()
        self._initialize_blueprints()
        self._initialize_database()
        self._initialize_flask_config()
        self._initialize_flask_sql_alchemy()
        self._initialize_management_commands()
        self._algorithm.initialize_portfolio_managers()
        self.start_scheduler()
        self.start_algorithm()

        # Start the app
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
    def config(self):
        return self._config

    def reset(self):
        self._configured = False
        self._database_configured: bool = False
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