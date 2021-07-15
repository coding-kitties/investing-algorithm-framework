from flask import Flask

from investing_algorithm_framework.configuration import Config, create_app
from investing_algorithm_framework.context import Singleton
from investing_algorithm_framework.core.context import algorithm
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import create_all_tables, \
    initialize_db
from investing_algorithm_framework.extensions import scheduler


class App(metaclass=Singleton):
    _algorithm = algorithm
    _flask_app: Flask = None
    _configured: bool
    _started = False
    _config = None

    def __init__(
            self, resources_directory: str = None, config=None, arg=None
    ):
        pass

    def initialize(
            self, resources_directory: str = None, config=None, arg=None
    ):
        if not self.started:

            if config is not None:
                assert issubclass(config, Config), (
                    "Config is not an instance of config"
                )
                self._config = config()

            if resources_directory is not None:
                self.config.RESOURCES_DIRECTORY = resources_directory

    def _initialize_algorithm(self):
        self._algorithm.initialize(config=self.config)

    def _initialize_config(self):

        if self.config is None:
            self._config = Config()

    def _initialize_flask_app(self):
        self._flask_app = create_app(self.config)

    def start(self):
        self._initialize_config()
        self._initialize_algorithm()
        self._initialize_flask_app()
        self.start_database()
        self.start_scheduler()
        self.start_algorithm()

        # Start the app
        self._flask_app.run(
            debug=True,
            threaded=True,
            use_reloader=False
        )

    def start_database(self):
        initialize_db(self._flask_app)
        create_all_tables()

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
