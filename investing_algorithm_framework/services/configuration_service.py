import os
import inspect
from investing_algorithm_framework.domain import Environment, \
    SNAPSHOT_INTERVAL, DATA_DIRECTORY, INDEX_DATETIME, AppMode, \
    SnapshotInterval, DATETIME_FORMAT_FILE_NAME

caller_file = inspect.stack()[-1].filename
caller_dir = os.path.dirname(os.path.abspath(caller_file))

DEFAULT_CONFIGURATION = {
    "ENVIRONMENT": Environment.PROD.value,
    "LOG_LEVEL": 'DEBUG',
    "APP_DIR": os.path.abspath(os.path.dirname(__file__)),
    "PROJECT_ROOT": os.path.abspath(
        os.path.join(os.path.abspath(os.path.dirname(__file__)), os.pardir)
    ),
    "RESOURCE_DIRECTORY": os.getenv("RESOURCE_DIRECTORY")
    or os.path.join(caller_dir, "resources"),
    "APP_MODE": AppMode.DEFAULT.value,
    "CHECK_PENDING_ORDERS": True,
    "BACKTEST_DATA_DIRECTORY_NAME": "backtest_data",
    "SYMBOLS": None,
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "DATABASE_DIRECTORY_PATH": None,
    "DATABASE_DIRECTORY_NAME": "databases",
    DATA_DIRECTORY: "data",
    INDEX_DATETIME: None,
    SNAPSHOT_INTERVAL: SnapshotInterval.DAILY.value,
    DATETIME_FORMAT_FILE_NAME: "%Y-%m-%d-%H-%M"
}

DEFAULT_FLASK_CONFIGURATION = {
    "DEBUG_TB_INTERCEPT_REDIRECTS": False,
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "CACHE_TYPE": 'simple',
    "CORS_ORIGIN_WHITELIST": [
        'http://0.0.0.0:4100',
        'http://localhost:4100',
        'http://0.0.0.0:8000',
        'http://localhost:8000',
        'http://0.0.0.0:4200',
        'http://localhost:4200',
        'http://0.0.0.0:4000',
        'http://localhost:4000',
    ],
    "SCHEDULER_API_ENABLED": True,
}


class ConfigurationService:

    def __init__(self):
        self._config = DEFAULT_CONFIGURATION.copy()
        self._flask_config = DEFAULT_FLASK_CONFIGURATION.copy()

    def initialize(self):
        self._config = DEFAULT_CONFIGURATION.copy()
        self._flask_config = DEFAULT_FLASK_CONFIGURATION.copy()

    @property
    def config(self):
        # Make a copy of the config to prevent external modifications
        copy = self._config.copy()
        return copy

    def get_config(self):
        copy = self._config.copy()
        return copy

    def get_flask_config(self):
        # Make a copy of the config to prevent external modifications
        copy = self._flask_config.copy()
        return copy

    def add_value(self, key, value):
        self._config[key] = value

    def add_dict(self, dictionary):
        self._config.update(dictionary)

    def remove_value(self, key):
        self._config.pop(key)

    def initialize_from_dict(self, data: dict):
        """
        Initialize the configuration from a dictionary.

        Args:
            data (dict): The dictionary containing the configuration values.

        Returns:
            None
        """

        self._config.update(data)
