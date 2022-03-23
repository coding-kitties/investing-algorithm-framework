import os

from investing_algorithm_framework.configuration import Environment
from investing_algorithm_framework.configuration.constants import \
    CCXT_ENABLED, MARKET, PORTFOLIOS, RESOURCE_DIRECTORY, \
    DATABASE_DIRECTORY_PATH, DATABASE_NAME, ENVIRONMENT
from investing_algorithm_framework.configuration.settings import DevConfig, \
    Config
from investing_algorithm_framework.core.context import \
    AlgorithmContextConfiguration
from investing_algorithm_framework.core.exceptions import OperationalException
from tests.resources import TestBase
from tests.resources.utils import random_string


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()

    def test_config_initialization(self):
        self.algo_app._config = AlgorithmContextConfiguration()
        self.algo_app.initialize(config=DevConfig())

        dev_config = DevConfig()

        for attribute_key in dev_config:
            self.assertEqual(
                self.algo_app.config.get(attribute_key),
                dev_config[attribute_key]
            )

    def test_config_initialization_with_portfolios(self):
        config = Config()
        config[PORTFOLIOS] = {
            "TEST": {
                "API_KEY": random_string(10),
                "SECRET_KEY": random_string(10),
                "MARKET": "TEST",
                "TRADING_SYMBOL": "USDT"
            },
            "TEST_TWO": {
                "API_KEY": random_string(10),
                "SECRET_KEY": random_string(10),
                "MARKET": "TEST",
                "TRADING_SYMBOL": "USDT",
                "SQLITE": False
            },
            "TEST_THREE": {
                "API_KEY": random_string(10),
                "SECRET_KEY": random_string(10),
                "MARKET": "TEST",
                "TRADING_SYMBOL": "USDT",
                "CCXT": False
            },
        }
        config[RESOURCE_DIRECTORY] = self.resources_dir
        config[ENVIRONMENT] = Environment.TEST.value

        self.algo_app.config = None
        self.algo_app.initialize(config=config)

    def test_config_initialization_without_config(self):
        self.algo_app.config = None
        self.algo_app.initialize()

        config = Config()

        for attribute_key in config:
            self.assertEqual(
                self.algo_app.config.get(attribute_key),
                config[attribute_key]
            )

        self.assertFalse(self.algo_app.config.sql_alchemy_configured())
        self.assertFalse(self.algo_app.config.sqlite_configured())
        self.assertFalse(self.algo_app.config.resource_directory_configured())

        with self.assertRaises(OperationalException) as exc:
            self.algo_app.start()

        self.assertEqual(
            "Resource directory not configured", exc.exception.error_message
        )

    def test_sqlite_database_initialization(self):
        config = Config()
        config[PORTFOLIOS] = {
            "TEST": {
                "API_KEY": random_string(10),
                "SECRET_KEY": random_string(10),
                "MARKET": "TEST",
                "TRADING_SYMBOL": "USDT"
            },
        }
        config[RESOURCE_DIRECTORY] = self.resources_dir

        self.algo_app.config = None
        self.algo_app.initialize(config=config)
        self.algo_app._initialize_database()

        database_config = self.algo_app.config.get_database_config()

        database_name = database_config[DATABASE_NAME]
        database_directory_path = database_config[DATABASE_DIRECTORY_PATH]

        self.assertIsNotNone(database_name)
        self.assertIsNotNone(database_directory_path)

        database_path = os.path.join(
            database_directory_path,
            "{}.sqlite3".format(database_name)
        )

        self.assertTrue(os.path.isfile(database_path))
        self.assertFalse(self.algo_app.config.sql_alchemy_configured())
        self.assertTrue(self.algo_app.config.sqlite_configured())
        self.assertTrue(self.algo_app.config.resource_directory_configured())

    def test_sql_alchemy_initialization(self):
        config = Config()
        config[PORTFOLIOS] = {
            "TEST": {
                "API_KEY": random_string(10),
                "SECRET_KEY": random_string(10),
                "MARKET": "TEST",
                "TRADING_SYMBOL": "USDT"
            },
        }
        config[RESOURCE_DIRECTORY] = self.resources_dir

        self.algo_app.config = None
        self.algo_app.initialize(config=config)
        self.algo_app._initialize_database()
        self.algo_app._initialize_flask_app()
        self.algo_app._initialize_flask_sql_alchemy()

        database_config = self.algo_app.config.get_database_config()

        database_name = database_config[DATABASE_NAME]
        database_directory_path = database_config[DATABASE_DIRECTORY_PATH]

        self.assertIsNotNone(database_name)
        self.assertIsNotNone(database_directory_path)

        database_path = os.path.join(
            database_directory_path,
            "{}.sqlite3".format(database_name)
        )

        self.assertTrue(os.path.isfile(database_path))
        self.assertTrue(self.algo_app.config.sql_alchemy_configured())
        self.assertTrue(self.algo_app.config.sqlite_configured())
        self.assertTrue(self.algo_app.config.resource_directory_configured())

    def test_initialization_minimal_base(self):
        config = Config()
        config[PORTFOLIOS] = {
            "TEST": {
                "API_KEY": random_string(10),
                "SECRET_KEY": random_string(10),
                "MARKET": "TEST",
                "TRADING_SYMBOL": "USDT",
                "SQLITE": False
            },
        }
        config[RESOURCE_DIRECTORY] = self.resources_dir
        config[ENVIRONMENT] = Environment.TEST.value

        self.algo_app.config = None
        self.algo_app.initialize(config=config)

        self.assertFalse(self.algo_app.config.sql_alchemy_configured())
        self.assertFalse(self.algo_app.config.sqlite_configured())
        self.assertTrue(self.algo_app.config.resource_directory_configured())
        self.assertIsNone(self.algo_app.config.get_database_config())

    def test_ccxt_enabled(self):
        config = DevConfig()
        config.set(CCXT_ENABLED, True)
        context_config = AlgorithmContextConfiguration()
        context_config.load(config)

        for attribute_key in config:
            self.assertEqual(
                context_config.get(attribute_key), config[attribute_key]
            )

        self.assertFalse(context_config.ccxt_enabled())

        config.set(MARKET, "binance")
        context_config = AlgorithmContextConfiguration()
        context_config.load(config)
        self.assertTrue(context_config.ccxt_enabled())
