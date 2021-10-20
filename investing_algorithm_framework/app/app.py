import inspect

from flask import Flask

from investing_algorithm_framework.configuration import Config, create_app, \
    setup_config, setup_database, setup_logging
from investing_algorithm_framework.context import Singleton
from investing_algorithm_framework.core.context import algorithm
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import create_all_tables, \
    initialize_db
from investing_algorithm_framework.extensions import scheduler
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY, SQLALCHEMY_DATABASE_URI, DATABASE_DIRECTORY_PATH, \
    DATABASE_NAME, DATABASE_CONFIG, LOG_LEVEL


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
            self._config = config

    def initialize(
            self, resources_directory: str = None, config=None, arg=None
    ):
        if not self.started:

            if resources_directory is not None:
                self._resource_directory = resources_directory

            if config is not None:
                self._config = config

    def _initialize_algorithm(self):
        self._algorithm.initialize(config=self.config)

    def _initialize_config(self, config=None):

        if not self._configured:

            if config is not None:
                self._config = config

            if self._config is None:
                raise OperationalException("No config object set")

            if inspect.isclass(self._config) \
                    and issubclass(self._config, Config):
                self._config = self._config()
            elif type(self._config) is dict:
                self._config = Config.from_dict(self._config)
            else:
                raise OperationalException("Config object not supported")

            if self._resource_directory is not None:
                self._config[RESOURCES_DIRECTORY] = self._resource_directory

            if RESOURCES_DIRECTORY not in self._config \
                    or self._config[RESOURCES_DIRECTORY] is None:
                raise OperationalException("Resource directory not specified")

            self._configured = True
            setup_logging(self.config.get(LOG_LEVEL, "INFO"))

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
            setup_database(self.config)

            if self.config[DATABASE_CONFIG][DATABASE_DIRECTORY_PATH] is None:
                raise OperationalException(
                    f"{DATABASE_DIRECTORY_PATH} is not set in config"
                )

            if self.config[DATABASE_CONFIG][DATABASE_NAME] is None:
                raise OperationalException(
                    f"{DATABASE_NAME} is not set in config"
                )

            if self.config[SQLALCHEMY_DATABASE_URI] is None:
                raise OperationalException(
                    f"{SQLALCHEMY_DATABASE_URI} is not set in config"
                )

            self._database_configured = True

    def register_blueprint(self, blueprint):
        self._blueprints.append(blueprint)

    def _initialize_blueprints(self):

        for blueprint in self._blueprints:
            self._flask_app.register_blueprint(blueprint)

    def start(self):

        # Setup config if it is not set
        if self._config is None:
            self._config = Config

        self._initialize_flask_app()
        self._initialize_blueprints()
        self._initialize_config()
        self._initialize_database()
        self._initialize_flask_config()
        self._initialize_flask_sql_alchemy()
        self._initialize_algorithm()

        self.start_scheduler()
        self.start_algorithm()

        # Start the app
        self._flask_app.run(
            debug=True,
            threaded=True,
            use_reloader=False
        )

    def start_scheduler(self):

        # Initialize the schedulers
        if not scheduler.running:
            scheduler.init_app(self._flask_app)
            scheduler.start()

    def start_algorithm(self):

        if not scheduler.running:
            raise OperationalException(
                "Could not start algorithm because the scheduler "
                "is not running"
            )

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
